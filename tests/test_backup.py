"""Dumping, restoring and copying the database, and packing the uploaded files. Only SQLite is needed here:
the PostgreSQL and MySQL paths call pg_dump, psql, mysqldump and mysql, which a test machine may not have."""

import gzip
import io
import os
import sqlite3
import tarfile
from datetime import date, timedelta
from unittest import mock

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

import manager
from helper.archive import fetch, pack_uploads, unpack_uploads
from helper.db import initialise_database as db
from helper.db.backup import _kind_of, default_dump_path, delete_old_dumps, dump, restore
from helper.db.migrate import copy_database, has_data
from helper.db.settings import DatabaseSettings, TransferError


def count(settings, model):
    engine = settings.make_engine()
    try:
        with Session(engine) as session:
            return session.scalar(select(func.count()).select_from(model))
    finally:
        engine.dispose()


@pytest.fixture
def configured():
    """The database that the test session seeded: some records and one staff account."""
    return DatabaseSettings.from_config()


def test_dump_leaves_the_staff_out_and_restore_brings_the_records_back(configured, tmp_path):
    output = dump(configured, tmp_path / "release.db.gz")
    assert (tmp_path / "release.db.gz.sha256").read_text().endswith(f"  {output.name}\n")
    with gzip.open(output) as unpacked:
        assert unpacked.read(16) == b"SQLite format 3\x00"

    target = DatabaseSettings.sqlite_file(str(tmp_path / "new" / "restored.sqlite3"))
    restore(target, output)
    assert count(target, db.Person) == count(configured, db.Person) > 0
    assert count(target, db.DocumentAuthorship) == count(configured, db.DocumentAuthorship) > 0
    assert count(target, db.User) == 0  # the table exists, empty, so that user_add works at once
    assert count(configured, db.User) == 1  # and the original is untouched


def test_dump_can_keep_the_staff(configured, tmp_path):
    output = dump(configured, tmp_path / "private.db", with_users=True)  # no .gz: the file itself
    assert output.read_bytes().startswith(b"SQLite format 3\x00")
    assert sqlite3.connect(output).execute("SELECT count(*) FROM users").fetchone() == (1,)


def test_deleted_staff_cannot_be_recovered_from_the_dump(configured, tmp_path):
    output = dump(configured, tmp_path / "release.db")
    assert b"$argon2" not in output.read_bytes() and b"scrypt" not in output.read_bytes()


def test_restore_refuses_to_overwrite_data_unless_forced(configured, tmp_path):
    output = dump(configured, tmp_path / "release.db.gz")
    target = DatabaseSettings.sqlite_file(str(tmp_path / "t.sqlite3"))
    restore(target, output)
    with pytest.raises(TransferError, match="already holds data"):
        restore(target, output)
    restore(target, output, force=True)
    assert has_data(target)


@pytest.mark.parametrize("content", [b"just some text", b""])
def test_restore_rejects_files_that_are_not_dumps(tmp_path, content):
    path = tmp_path / "x.sql"
    path.write_bytes(content)
    with pytest.raises(TransferError, match="neither"):
        restore(DatabaseSettings.sqlite_file(str(tmp_path / "t.sqlite3")), path)


def test_restore_rejects_a_sqlite_file_of_something_else(tmp_path):
    path = tmp_path / "other.db"
    connection = sqlite3.connect(path)
    connection.execute("CREATE TABLE unrelated (x)")
    connection.close()
    with pytest.raises(TransferError, match="not a Higeo database"):
        restore(DatabaseSettings.sqlite_file(str(tmp_path / "t.sqlite3")), path)


def test_a_sql_dump_of_another_engine_is_refused(tmp_path):
    path = tmp_path / "pg.sql"
    path.write_text("--\n-- PostgreSQL database dump\n--\n")
    with pytest.raises(TransferError, match="postgresql dump"):
        restore(DatabaseSettings.sqlite_file(str(tmp_path / "t.sqlite3")), path)


def test_kind_of():
    assert _kind_of(b"SQLite format 3\x00...") == "sqlite"
    assert _kind_of(b"-- MySQL dump 10.13") == "mysql"
    assert _kind_of(b"-- MariaDB dump 10.19") == "mysql"
    assert _kind_of(b"\\restrict x\n-- PostgreSQL database dump") == "postgresql"
    assert _kind_of(b"hello") is None


def test_copy_database_copies_every_table_and_not_the_staff(configured, tmp_path):
    target = DatabaseSettings.sqlite_file(str(tmp_path / "copy.sqlite3"))
    copy_database(configured, target, say=lambda _: None)
    for model in (db.Person, db.Organization, db.Document, db.FieldOfStudy, db.PersonEducation):
        assert count(target, model) == count(configured, model)
    assert count(target, db.User) == 0

    with pytest.raises(TransferError, match="already holds data"):
        copy_database(configured, target, say=lambda _: None)
    copy_database(configured, target, with_users=True, force=True, say=lambda _: None)
    assert count(target, db.User) == 1


def test_default_dump_name_and_retention(configured, tmp_path):
    path = default_dump_path(configured, tmp_path)
    assert path.parent == tmp_path and path.name.endswith(f"_{date.today().isoformat()}.db.gz")

    stem = os.path.splitext(os.path.basename(configured.name))[0]
    old = tmp_path / f"{stem}_{(date.today() - timedelta(days=90)).isoformat()}.db.gz"
    fresh = tmp_path / f"{stem}_{date.today().isoformat()}.db.gz"
    unrelated = tmp_path / "notes.txt"
    for file in (old, fresh, unrelated):
        file.write_text("x")
    for file in (old, unrelated):
        os.utime(file, (0, 0))
    delete_old_dumps(tmp_path, configured, 30)
    assert not old.exists() and fresh.exists() and unrelated.exists()


# --- uploaded files -------------------------------------------------------------------------------------------


def test_uploads_round_trip(tmp_path):
    uploads = tmp_path / "uploads"
    uploads.mkdir()
    (uploads / "[2024-01-01 10:00:00.1]photo.jpg").write_bytes(b"jpg")
    (uploads / "doc.pdf").write_bytes(b"pdf")
    (uploads / "folder").mkdir()  # not a file, not packed
    archive = pack_uploads(uploads, tmp_path / "uploads.tar.gz")

    restored = tmp_path / "restored"
    unpack_uploads(archive, restored)
    assert sorted(p.name for p in restored.iterdir()) == ["[2024-01-01 10:00:00.1]photo.jpg", "doc.pdf"]

    (restored / "doc.pdf").write_bytes(b"newer")
    unpack_uploads(archive, restored)  # keeps what is there
    assert (restored / "doc.pdf").read_bytes() == b"newer"
    unpack_uploads(archive, restored, overwrite=True)
    assert (restored / "doc.pdf").read_bytes() == b"pdf"


def make_tar(path, members):
    with tarfile.open(path, "w:gz") as archive:
        for name, data in members:
            info = tarfile.TarInfo(name)
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))
    return path


def test_unpacking_accepts_an_archive_of_the_whole_folder(tmp_path):
    archive = make_tar(tmp_path / "a.tar.gz", [("static/uploads/x.jpg", b"x")])
    unpack_uploads(archive, tmp_path / "out")
    assert (tmp_path / "out" / "x.jpg").read_bytes() == b"x"


@pytest.mark.parametrize("name", ["../evil.txt", "/etc/evil.txt", "sub/dir/evil.txt"])
def test_unpacking_refuses_paths_that_leave_the_folder(tmp_path, name):
    archive = make_tar(tmp_path / "a.tar.gz", [(name, b"x")])
    with pytest.raises(TransferError, match="Refusing"):
        unpack_uploads(archive, tmp_path / "out")
    assert not (tmp_path / "evil.txt").exists()


def test_fetch(tmp_path):
    (tmp_path / "local.db").write_bytes(b"x")
    assert fetch(f" '{tmp_path / 'local.db'}' ", tmp_path) == tmp_path / "local.db"
    with pytest.raises(TransferError, match="no file"):
        fetch(str(tmp_path / "missing"), tmp_path)
    with pytest.raises(TransferError, match="https"):
        fetch("http://example.com/dump.sql.gz", tmp_path)


# --- manager.py -----------------------------------------------------------------------------------------------


def test_quicksetup_from_a_dump_and_an_uploads_archive(configured, tmp_path, monkeypatch):
    release = dump(configured, tmp_path / "release.db.gz")
    uploads = tmp_path / "src"
    uploads.mkdir()
    (uploads / "a.jpg").write_bytes(b"a")
    archive = pack_uploads(uploads, tmp_path / "uploads.tar.gz")

    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.delenv("SECRET_KEY")  # a fresh installation has none, and quicksetup makes one
    monkeypatch.setattr(manager, "BASE_DIR", project)
    monkeypatch.setattr(manager, "ENV_FILE", str(project / ".env"))
    new_database = project / "higeo.sqlite3"
    answers = iter(["sqlite", str(new_database), str(release), str(archive), "new-admin@example.com"])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(answers))
    monkeypatch.setattr("getpass.getpass", lambda _prompt="": "a long password")

    with mock.patch.dict(os.environ):  # quicksetup also sets the new settings for the rest of its own run
        manager.quicksetup(None)

    target = DatabaseSettings.sqlite_file(str(new_database))
    assert count(target, db.Person) == count(configured, db.Person) > 0
    engine = target.make_engine()
    with Session(engine) as session:
        assert [user.email for user in session.scalars(select(db.User))] == ["new-admin@example.com"]
    engine.dispose()
    assert (project / "static" / "uploads" / "a.jpg").read_bytes() == b"a"
    env = (project / ".env").read_text()
    assert "SECRET_KEY" in env and "DATABASE_ENGINE" in env
    assert oct((project / ".env").stat().st_mode & 0o777) == "0o600"
