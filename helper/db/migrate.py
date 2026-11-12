"""Operations on a database that is given as settings rather than taken from `.env`: its tables, and copying all
of its data to a database of another engine."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import MetaData, func, inspect, select, text

from helper.db.initialise_database import Base, User, create_database
from helper.db.settings import DatabaseSettings, TransferError

if TYPE_CHECKING:
    from collections.abc import Callable

BATCH_ROWS = 500
BATCH_TEXT = (
    1024 * 1024
)  # characters per insert: MySQL refuses statements over its max_allowed_packet (4 MB on old servers)


def create_tables(settings: DatabaseSettings) -> None:
    """Create the tables that are missing; the ones that exist are left alone."""
    engine = settings.make_engine()
    try:
        Base.metadata.create_all(engine)
    finally:
        engine.dispose()


def drop_tables(settings: DatabaseSettings) -> None:
    """Drop every table of the database, including ones that this version of the application does not know."""
    engine = settings.make_engine()
    try:
        metadata = MetaData()
        metadata.reflect(engine)
        metadata.drop_all(engine)
    finally:
        engine.dispose()


def has_data(settings: DatabaseSettings) -> bool:
    """Whether any of the application's tables holds a row."""
    engine = settings.make_engine()
    try:
        existing = set(inspect(engine).get_table_names())
        with engine.connect() as connection:
            return any(
                connection.execute(select(func.count()).select_from(table)).scalar_one() > 0
                for table in Base.metadata.sorted_tables
                if table.name in existing
            )
    finally:
        engine.dispose()


def copy_database(
    source: DatabaseSettings,
    target: DatabaseSettings,
    *,
    with_users: bool = False,
    force: bool = False,
    say: Callable[[str], None] = print,
) -> None:
    """Copy every record from `source` to `target`, which may be of another engine.

    The target database and its tables are created if needed. It must not hold any data, unless `force` is given,
    which empties it first. The staff accounts stay behind unless `with_users` is given.
    """
    create_database(target)
    if has_data(target):
        if not force:
            raise TransferError(f"The target {target.describe()} already holds data. Use --force to replace it.")
        drop_tables(target)
    create_tables(target)

    source_engine, target_engine = source.make_engine(), target.make_engine()
    try:
        existing = set(inspect(source_engine).get_table_names())
        tables = [t for t in Base.metadata.sorted_tables if with_users or t is not User.__table__]
        missing = [table.name for table in tables if table.name not in existing]
        if missing:
            raise TransferError(f"The source {source.describe()} has no table {', '.join(missing)}.")
        # One transaction, so that a failure leaves the target empty. Parents come before their children.
        with source_engine.connect() as reader, target_engine.begin() as writer:
            for table in tables:
                copied = 0
                result = reader.execution_options(stream_results=True).execute(select(table))
                for rows in result.partitions(BATCH_ROWS):
                    for batch in _split_by_size([dict(row._mapping) for row in rows]):
                        writer.execute(table.insert(), batch)
                    copied += len(rows)
                say(f"{table.name}: {copied} row(s)")
            if target.engine == "postgresql":
                _reset_postgresql_sequences(writer, tables)
    finally:
        source_engine.dispose()
        target_engine.dispose()


def _split_by_size(rows: list[dict]) -> list[list[dict]]:
    """Cut the rows into groups whose text is about BATCH_TEXT characters, so that a statement stays small."""
    groups, group, size = [], [], 0
    for row in rows:
        row_size = sum(len(value) for value in row.values() if isinstance(value, str))
        if group and size + row_size > BATCH_TEXT:
            groups.append(group)
            group, size = [], 0
        group.append(row)
        size += row_size
    if group:
        groups.append(group)
    return groups


def _reset_postgresql_sequences(connection, tables) -> None:
    """Rows were inserted with their ids, so the sequences have to be moved past them or the next insert collides."""
    for table in tables:
        primary_key = list(table.primary_key.columns)
        if (
            len(primary_key) == 1
            and primary_key[0].autoincrement is not False
            and primary_key[0].type.python_type is int
        ):
            name = f'"{table.name}"'
            column = primary_key[0].name
            connection.execute(
                text(
                    f"SELECT setval(pg_get_serial_sequence('{name}', '{column}'),"
                    f" COALESCE((SELECT MAX({column}) FROM {name}), 1),"
                    f" (SELECT MAX({column}) FROM {name}) IS NOT NULL)"
                )
            )
