"""Dump a database into one file and load such a file back, for every supported engine.

- sqlite: the dump is the database file itself (a consistent copy made with SQLite's online backup).
- postgresql: plain SQL made by pg_dump, loaded with psql.
- mysql: plain SQL made by mysqldump, loaded with mysql.

Either can be gzip-compressed (a name ending in .gz when dumping; detected from the content when restoring).
The staff accounts are left out unless asked for, so that a dump can be published.
"""

from __future__ import annotations

import contextlib
import gzip
import hashlib
import os
import re
import secrets
import shutil
import sqlite3
import subprocess
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

from helper.db.initialise_database import create_database
from helper.db.migrate import copy_database, create_tables, drop_tables, has_data
from helper.db.settings import DatabaseSettings, TransferError

if TYPE_CHECKING:
    from collections.abc import Callable

# GitHub accepts release assets smaller than 2 GiB.
RELEASE_ASSET_LIMIT = 2 * 1024**3
SQLITE_MAGIC = b"SQLite format 3\x00"
GZIP_MAGIC = b"\x1f\x8b"
USERS_TABLE = "users"
CHUNK = 1024 * 1024


def default_dump_path(settings: DatabaseSettings, directory: Path) -> Path:
    stem = Path(settings.name).stem if settings.engine == "sqlite" else settings.name
    extension = "db" if settings.engine == "sqlite" else "sql"
    return directory / f"{stem}_{date.today().isoformat()}.{extension}.gz"


def delete_old_dumps(directory: Path, settings: DatabaseSettings, days: int) -> None:
    """Delete this database's dumps in `directory` (named like the default ones) that are older than `days`."""
    stem = Path(settings.name).stem if settings.engine == "sqlite" else settings.name
    pattern = re.compile(rf"{re.escape(stem)}_\d{{4}}-\d{{2}}-\d{{2}}\.(sql|db)(\.gz)?(\.sha256)?")
    cutoff = datetime.now() - timedelta(days=days)
    for entry in directory.iterdir():
        if pattern.fullmatch(entry.name) and datetime.fromtimestamp(entry.stat().st_mtime) < cutoff:
            print(f"Deleting old dump {entry}")
            entry.unlink()


# --- dumping --------------------------------------------------------------------------------------------------


def dump(settings: DatabaseSettings, output: Path, *, with_users: bool = False) -> Path:
    """Write the dump to `output` (compressed if its name ends in .gz) and a `.sha256` file next to it."""
    output.parent.mkdir(parents=True, exist_ok=True)
    partial = output.with_name(output.name + ".part")
    try:
        if settings.engine == "sqlite":
            _dump_sqlite(settings, partial, output.name.endswith(".gz"), with_users)
        else:
            with _open_for_writing(partial, output.name.endswith(".gz")) as out:
                _run_dump_tool(settings, out, with_users)
        os.replace(partial, output)
    finally:
        partial.unlink(missing_ok=True)

    digest = _sha256(output)
    output.with_name(output.name + ".sha256").write_text(f"{digest}  {output.name}\n", encoding="utf-8")
    size = output.stat().st_size
    print(f"Wrote {output} ({size / 1024**2:.1f} MiB), sha256 {digest}")
    if size >= RELEASE_ASSET_LIMIT:
        print("Warning: this is 2 GiB or more, which is too big for a GitHub release asset.")
    return output


def _open_for_writing(path: Path, compress: bool):
    return gzip.open(path, "wb", compresslevel=6) if compress else open(path, "wb")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as file:
        while chunk := file.read(CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


def _dump_sqlite(settings: DatabaseSettings, partial: Path, compress: bool, with_users: bool) -> None:
    if not Path(settings.name).is_file():
        raise TransferError(f"There is no SQLite database file {settings.name}.")
    copy_path = partial.with_name(partial.name + ".db")
    source = sqlite3.connect(settings.name)
    copy = sqlite3.connect(copy_path, isolation_level=None)
    try:
        source.backup(copy)
        if not with_users and copy.execute("SELECT 1 FROM sqlite_master WHERE name = ?", (USERS_TABLE,)).fetchone():
            copy.execute(f"DELETE FROM {USERS_TABLE}")
        copy.execute("VACUUM")  # also frees the pages of the deleted accounts, which could otherwise be recovered
    finally:
        source.close()
        copy.close()
    try:
        if compress:
            with open(copy_path, "rb") as raw, gzip.open(partial, "wb", compresslevel=6) as packed:
                shutil.copyfileobj(raw, packed, CHUNK)
        else:
            os.replace(copy_path, partial)
    finally:
        copy_path.unlink(missing_ok=True)


def _run_dump_tool(settings: DatabaseSettings, out, with_users: bool) -> None:
    if settings.engine == "postgresql":
        command = ["pg_dump", "--no-owner", "--no-privileges", *_postgresql_connection(settings), "-d", settings.name]
        if not with_users:
            command.append(f"--exclude-table-data={USERS_TABLE}")  # the empty table is kept, so the schema is whole
    else:
        command = [
            "mysqldump",
            "--single-transaction",
            "--no-tablespaces",
            "--default-character-set=utf8mb4",
            *_mysql_connection(settings),
        ]
        if not with_users:
            command.append(f"--ignore-table={settings.name}.{USERS_TABLE}")  # restore creates the empty table
        command.append(settings.name)

    with tempfile.TemporaryFile() as errors:
        process = _start(command, settings, stdout=subprocess.PIPE, stderr=errors)
        try:
            shutil.copyfileobj(process.stdout, out, CHUNK)
        finally:
            process.stdout.close()
            code = process.wait()
        if code:
            raise TransferError(f"{command[0]} failed: {_read_back(errors)}")


# --- restoring ------------------------------------------------------------------------------------------------


def restore(settings: DatabaseSettings, source: Path, *, force: bool = False, say: Callable[[str], None] = print):
    """Load a dump into the database described by `settings`, creating the database and the missing tables.

    The database must hold no data, unless `force` is given, which empties it first. A SQLite file can be loaded
    into any engine; a SQL dump only into the engine it was made for (to change engines, restore it into its own
    engine and then copy the data with `db_migrate`).
    """
    with _open_dump(source) as stream:
        head = stream.read(8192)
        stream.seek(0)
        kind = _kind_of(head)
        if kind is None:
            raise TransferError(f"{source} is neither a SQLite database nor a pg_dump or mysqldump file.")
        if kind == "sqlite":
            _restore_sqlite(settings, stream, force, say)
        elif kind == settings.engine:
            create_database(settings)
            if has_data(settings) and not force:
                raise TransferError(f"The {settings.describe()} already holds data. Use --force to replace it.")
            drop_tables(settings)  # the dump creates the tables itself
            _load_sql(settings, stream)
        else:
            raise TransferError(
                f"{source} is a {kind} dump, but the database is {settings.engine}. Restore it into a {kind} database"
                f" and copy the data with db_migrate, or restore a SQLite dump."
            )
    create_tables(settings)  # the staff table is not in a published dump


def _open_dump(path: Path):
    with open(path, "rb") as file:
        compressed = file.read(2) == GZIP_MAGIC
    return gzip.open(path, "rb") if compressed else open(path, "rb")


def _kind_of(head: bytes) -> str | None:
    """Which engine a dump is for, judging by its first bytes."""
    if head.startswith(SQLITE_MAGIC):
        return "sqlite"
    if b"PostgreSQL database dump" in head:
        return "postgresql"
    if b"MySQL dump" in head or b"MariaDB dump" in head:
        return "mysql"
    return None


def _restore_sqlite(settings: DatabaseSettings, stream, force: bool, say: Callable[[str], None]) -> None:
    if settings.engine == "sqlite":
        directory = Path(settings.name).resolve().parent
        directory.mkdir(parents=True, exist_ok=True)
    else:
        directory = None  # the system's temporary folder
    with tempfile.NamedTemporaryFile(dir=directory, prefix="higeo-restore-", suffix=".db", delete=False) as copy:
        shutil.copyfileobj(stream, copy, CHUNK)
    copy_path = Path(copy.name)
    try:
        connection = sqlite3.connect(copy_path)
        try:
            tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        finally:
            connection.close()
        if "person" not in tables:
            raise TransferError("This SQLite file is not a Higeo database (it has no person table).")
        if settings.engine == "sqlite":
            if Path(settings.name).exists() and has_data(settings) and not force:
                raise TransferError(f"The {settings.describe()} already holds data. Use --force to replace it.")
            os.replace(copy_path, settings.name)
        else:
            copy_database(DatabaseSettings.sqlite_file(str(copy_path)), settings, force=force, say=say)
    finally:
        copy_path.unlink(missing_ok=True)


def _load_sql(settings: DatabaseSettings, stream) -> None:
    """Pipe a SQL dump into psql or mysql, which stop at the first error.

    A dump from a link is text that a client program runs, and both clients can run commands of their own
    (psql's \\! starts a shell). So psql is first put into restricted mode with a key that the dump cannot know, and
    the dump's own \\restrict and \\unrestrict lines are dropped; mysql is started with --binary-mode, which
    disables its commands. The SQL itself still has the rights of the database user: load only dumps you trust.
    """
    if settings.engine == "postgresql":
        command = ["psql", "-X", "-q", "-v", "ON_ERROR_STOP=1", "--single-transaction"]
        command += [*_postgresql_connection(settings), "-d", settings.name]
        first_line = f"\\restrict {secrets.token_hex(16)}\n".encode()
        own_lines = (b"\\restrict ", b"\\unrestrict ")
    else:
        command = ["mysql", "--binary-mode", "--default-character-set=utf8mb4", "--local-infile=0"]
        command += [*_mysql_connection(settings), settings.name]
        first_line, own_lines = b"", ()

    with tempfile.TemporaryFile() as errors:
        process = _start(command, settings, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=errors)
        try:
            process.stdin.write(first_line)
            for line in stream:
                if not line.startswith(own_lines):
                    process.stdin.write(line)
            process.stdin.close()
        except BrokenPipeError:
            with contextlib.suppress(OSError):
                process.stdin.close()  # the client quit on an error, which is reported below
        except BaseException:
            process.kill()
            process.wait()
            raise
        code = process.wait()
        if code:
            message = _read_back(errors)
            hint = (
                "\nThis psql is too old to load dumps safely; update it to a release of August 2025 or later."
                if "restrict" in message and settings.engine == "postgresql" and "only" not in message
                else "\nThe database may be half loaded; run the command again with --force to start over."
            )
            raise TransferError(f"{command[0]} failed: {message}{hint}")


# --- helpers --------------------------------------------------------------------------------------------------


def _postgresql_connection(settings: DatabaseSettings) -> list[str]:
    arguments = ["-h", settings.host]
    if settings.port:
        arguments += ["-p", settings.port]
    if settings.user:
        arguments += ["-U", settings.user]
    return arguments


def _mysql_connection(settings: DatabaseSettings) -> list[str]:
    # TCP like the application itself; without it "localhost" means a socket and the port is ignored.
    arguments = ["--protocol=TCP", "-h", settings.host]
    if settings.port:
        arguments += ["-P", settings.port]
    if settings.user:
        arguments += ["-u", settings.user]
    return arguments


def _start(command: list[str], settings: DatabaseSettings, **streams) -> subprocess.Popen:
    """Start a client tool. The password goes in the environment: arguments show up in `ps`."""
    environment = os.environ.copy()
    if settings.password:
        environment["PGPASSWORD" if settings.engine == "postgresql" else "MYSQL_PWD"] = settings.password
    try:
        return subprocess.Popen(command, env=environment, **streams)
    except FileNotFoundError:
        raise TransferError(
            f"{command[0]} was not found. Install the {settings.engine} client tools and put them on the PATH."
        ) from None


def _read_back(errors) -> str:
    errors.seek(0)
    return errors.read().decode(errors="replace").strip() or "no message"
