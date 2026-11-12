import argparse
import getpass
import os
import re
import tempfile
from datetime import date
from pathlib import Path
from secrets import token_urlsafe

from dotenv import dotenv_values, find_dotenv, set_key

DATABASE_ENGINES = ("sqlite", "postgresql", "mysql")
DEFAULT_PORTS = {"postgresql": "5432", "mysql": "3306"}
DEFAULT_SQLITE_FILE = "higeo.sqlite3"
ENV_FILE = find_dotenv() or os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = "static/uploads"  # relative to the project, and stored in the database in this form
BACKUP_DIR = "backups"
SECRET_KEYS = ("DATABASE_PASSWORD", "SECRET_KEY")  # never printed


def prompt_password():
    """Ask for a password twice without echoing it."""
    password = getpass.getpass("Password: ")
    if password != getpass.getpass("Repeat password: "):
        raise SystemExit("The passwords do not match.")
    return password


def add_connection_options(parser):
    parser.add_argument("-n", "--name", help="Database name, or the path of the file for sqlite.")
    parser.add_argument("-H", "--host", help="Database host (not used by sqlite).")
    parser.add_argument("-P", "--port", help="Database port (not used by sqlite).")
    parser.add_argument("-u", "--user", help="Database user (not used by sqlite).")
    parser.add_argument(
        "-p", "--password", nargs="?", const="", help="Database password (prompted for if empty; not used by sqlite)."
    )


def main():
    """Manage the database settings and the staff accounts."""
    parser = argparse.ArgumentParser(description="Manage the database settings and the staff accounts.")
    subparsers = parser.add_subparsers(dest="command")

    db_set_parser = subparsers.add_parser("db_set", help="Choose the database engine (saved to .env).")
    db_set_parser.add_argument("engine", choices=DATABASE_ENGINES, help="Database engine.")
    add_connection_options(db_set_parser)

    db_init_parser = subparsers.add_parser("db_init", help="Create the database and its tables if they are missing.")
    db_init_parser.add_argument("--drop", action="store_true", help="Drop all the tables first, deleting all data.")
    db_init_parser.add_argument("-y", "--yes", action="store_true", help="Do not ask for confirmation of --drop.")

    db_dump_parser = subparsers.add_parser(
        "db_dump", help="Back up the database to one file (sqlite: the .db file; postgresql, mysql: SQL)."
    )
    db_dump_parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="File to write; .gz at the end compresses it (default: backups/<name>_<date>).",
    )
    db_dump_parser.add_argument(
        "--with-users", action="store_true", help="Keep the staff accounts (their password hashes) in the dump."
    )
    db_dump_parser.add_argument(
        "--keep-days", type=int, metavar="DAYS", help="Afterwards delete dumps of this database older than DAYS days."
    )

    db_restore_parser = subparsers.add_parser(
        "db_restore", help="Load a dump (a file or an https link) into the configured database."
    )
    db_restore_parser.add_argument("source", help="Path or https link of a dump made by db_dump (.gz is fine).")
    db_restore_parser.add_argument("--force", action="store_true", help="Replace the data that is already there.")

    db_migrate_parser = subparsers.add_parser(
        "db_migrate", help="Copy all the data of the configured database to a database of another engine."
    )
    db_migrate_parser.add_argument("engine", choices=DATABASE_ENGINES, help="Engine of the target database.")
    add_connection_options(db_migrate_parser)
    db_migrate_parser.add_argument("--with-users", action="store_true", help="Copy the staff accounts too.")
    db_migrate_parser.add_argument("--force", action="store_true", help="Replace the data in the target.")
    db_migrate_parser.add_argument(
        "--switch", action="store_true", help="Afterwards make the target the configured database (as db_set does)."
    )

    uploads_pack_parser = subparsers.add_parser(
        "uploads_pack", help="Pack the uploaded files (static/uploads) into one .tar.gz."
    )
    uploads_pack_parser.add_argument(
        "-o", "--output", type=Path, help="File to write (default: backups/uploads_<date>.tar.gz)."
    )

    uploads_unpack_parser = subparsers.add_parser(
        "uploads_unpack", help="Unpack an archive made by uploads_pack (a file or an https link) into static/uploads."
    )
    uploads_unpack_parser.add_argument("source", help="Path or https link of the .tar.gz.")
    uploads_unpack_parser.add_argument("--overwrite", action="store_true", help="Replace files that already exist.")

    subparsers.add_parser(
        "quicksetup", help="Set up a new installation step by step: database, data, uploaded files, admin account."
    )

    subparsers.add_parser("db_show", help="Show the database settings.")

    user_add_parser = subparsers.add_parser("user_add", help="Create a user.")
    user_add_parser.add_argument("email", type=str, help="Email of the user.")
    user_add_parser.add_argument("-p", "--password", type=str, help="Password (prompted for if omitted).")

    user_edit_parser = subparsers.add_parser("user_edit", help="Edit a user.")
    user_edit_parser.add_argument("email", type=str, help="Current email of the user.")
    user_edit_parser.add_argument("-e", "--new_email", type=str, help="New email.")
    user_edit_parser.add_argument(
        "-p", "--password", nargs="?", const="", help="New password (prompted for if empty)."
    )

    user_delete_parser = subparsers.add_parser("user_delete", help="Delete a user.")
    user_delete_parser.add_argument("email", type=str, help="Email of the user.")

    subparsers.add_parser("user_list", help="List all users.")

    files_gc_parser = subparsers.add_parser(
        "files_gc", help="Delete uploaded files that are no longer referenced by any record."
    )
    files_gc_parser.add_argument(
        "-n", "--dry-run", action="store_true", help="List the files that would be deleted, without deleting them."
    )

    args = parser.parse_args()

    try:
        run(args, parser)
    except ValueError as e:
        raise SystemExit(f"Error: {e}") from e
    print("Done!")


def run(args, parser):
    """Run the chosen command."""
    if args.command is None:
        parser.print_help()
    elif args.command == "db_set":
        db_set(args)
    elif args.command == "db_show":
        db_show()
    elif args.command == "files_gc":
        files_gc(args)
    elif args.command in DATABASE_COMMANDS:
        DATABASE_COMMANDS[args.command](args)
    else:
        run_user_command(args, parser)


def db_set(args):
    """Save the database settings to .env. Settings that are not given keep their current value."""
    current = {**dotenv_values(ENV_FILE), **os.environ}
    current_engine = current.get("DATABASE_ENGINE") or "sqlite"
    engine_changed = args.engine != current_engine
    settings = {"DATABASE_ENGINE": args.engine}
    if args.name is not None:
        settings["DATABASE_NAME"] = args.name
    elif args.engine == "sqlite" and (engine_changed or not current.get("DATABASE_NAME")):
        settings["DATABASE_NAME"] = DEFAULT_SQLITE_FILE
    elif current_engine == "sqlite":
        raise ValueError(f"--name is needed when switching from sqlite to {args.engine}.")

    if args.engine != "sqlite":
        settings["DATABASE_HOST"] = args.host or current.get("DATABASE_HOST") or "localhost"
        if args.port is not None:
            settings["DATABASE_PORT"] = args.port
        elif engine_changed or not current.get("DATABASE_PORT"):
            settings["DATABASE_PORT"] = DEFAULT_PORTS[args.engine]
        if args.user is not None:
            settings["DATABASE_USER"] = args.user
        if args.password is not None:
            settings["DATABASE_PASSWORD"] = args.password or getpass.getpass("Database password: ")

    write_env(settings)
    print(f"Saved to {ENV_FILE}. Run `manager.py db_init` to create the database and its tables.")


def write_env(settings):
    """Save settings to .env (created readable by its owner only: it holds the password and the secret key)."""
    if not os.path.exists(ENV_FILE):
        with open(ENV_FILE, "w", encoding="utf-8"):
            pass
        os.chmod(ENV_FILE, 0o600)
    for key, value in settings.items():
        set_key(ENV_FILE, key, value)
        print(f"{key} = {'***' if key in SECRET_KEYS and value else value}")


def db_show():
    """Print the database settings that the application will use."""
    import helper

    print(f"DATABASE_ENGINE = {helper.DATABASE_ENGINE}")
    print(f"DATABASE_NAME = {helper.DATABASE_NAME}")
    if helper.DATABASE_ENGINE != "sqlite":
        print(f"DATABASE_HOST = {helper.DATABASE_HOST}")
        print(f"DATABASE_PORT = {helper.DATABASE_PORT or DEFAULT_PORTS[helper.DATABASE_ENGINE]}")
        print(f"DATABASE_USER = {helper.DATABASE_USER or ''}")
        print(f"DATABASE_PASSWORD = {'***' if helper.DATABASE_PASSWORD else ''}")


def files_gc(args):
    """Delete files in the upload folder that no column in the database points to.

    Every text column of every table is checked, not just the known file fields (Document.file, Person.photo):
    some rows were populated by a one-off import script rather than through the app's own upload form, so a
    fixed field list could miss a file that is still in use and delete it.
    """
    from sqlalchemy import String, select
    from sqlalchemy.orm import Session

    from helper.db.initialise_database import Base, engine

    upload_dir = BASE_DIR / UPLOAD_DIR
    if not upload_dir.is_dir():
        print("No upload folder yet, nothing to do.")
        return

    # A path can be the column's whole value (Document.file, Person.photo) or be embedded in richer text
    # (biography/bibliography HTML), and some rows imported long ago store it as "/static/uploads/..." with a
    # leading slash instead of "static/uploads/..." like the app itself writes, so this extracts the path itself
    # rather than trusting the column's full value or a fixed leading character.
    path_pattern = re.compile(rf"/?{re.escape(UPLOAD_DIR)}/[^\s\"'<>]+")
    referenced = set()
    with Session(engine) as session:
        for table in Base.metadata.tables.values():
            for column in table.columns:
                if isinstance(column.type, String):
                    stmt = select(column).where(column.like(f"%{UPLOAD_DIR}/%"))
                    for (value,) in session.execute(stmt):
                        if value:
                            referenced.update(match.lstrip("/") for match in path_pattern.findall(value))

    removed = 0
    for entry in sorted(upload_dir.iterdir()):
        if entry.is_file() and f"{UPLOAD_DIR}/{entry.name}" not in referenced:
            print(f"{'Would delete' if args.dry_run else 'Deleting'} {entry}")
            if not args.dry_run:
                entry.unlink()
            removed += 1
    print(f"{'Would remove' if args.dry_run else 'Removed'} {removed} orphaned file(s).")


def target_settings(args):
    """The database that the connection options of db_migrate describe."""
    from helper.db.settings import DEFAULT_NAMES, DatabaseSettings

    if args.engine == "sqlite":
        return DatabaseSettings.sqlite_file(args.name or DEFAULT_NAMES["sqlite"])
    password = args.password
    if password == "":
        password = getpass.getpass("Target database password: ")
    return DatabaseSettings(
        args.engine, args.name or DEFAULT_NAMES[args.engine], args.host or "localhost", args.port, args.user, password
    )


def db_init(args):
    from helper.db.initialise_database import create_database
    from helper.db.migrate import create_tables, drop_tables
    from helper.db.settings import DatabaseSettings

    settings = DatabaseSettings.from_config()
    create_database(settings)
    if args.drop:
        if not args.yes and input(f"This deletes all data in the {settings.describe()}. Type y to go on: ") != "y":
            raise SystemExit("Cancelled.")
        drop_tables(settings)
    create_tables(settings)
    print(f"The tables of the {settings.describe()} are ready.")


def db_dump(args):
    from helper.db.backup import default_dump_path, delete_old_dumps, dump
    from helper.db.settings import DatabaseSettings

    settings = DatabaseSettings.from_config()
    output = args.output
    if output is None:
        (BASE_DIR / BACKUP_DIR).mkdir(mode=0o700, exist_ok=True)  # a dump can hold password hashes
        output = default_dump_path(settings, BASE_DIR / BACKUP_DIR)
    dump(settings, output, with_users=args.with_users)
    if args.keep_days is not None:
        delete_old_dumps(output.parent, settings, args.keep_days)


def db_restore(args):
    from helper.archive import fetch
    from helper.db.backup import restore
    from helper.db.settings import DatabaseSettings

    settings = DatabaseSettings.from_config()
    with tempfile.TemporaryDirectory(prefix="higeo-") as directory:
        restore(settings, fetch(args.source, Path(directory)), force=args.force)
    print(f"Loaded the dump into the {settings.describe()}.")


def db_migrate(args):
    from helper.db.migrate import copy_database
    from helper.db.settings import DatabaseSettings

    source, target = DatabaseSettings.from_config(), target_settings(args)
    if (source.engine, source.name, source.host, source.effective_port) == (
        target.engine,
        target.name,
        target.host,
        target.effective_port,
    ):
        raise ValueError("The target is the database that is configured now.")
    print(f"Copying the {source.describe()} to the {target.describe()}")
    copy_database(source, target, with_users=args.with_users, force=args.force)
    print(f"Copied to the {target.describe()}.")
    if args.switch:
        write_env(
            {
                "DATABASE_ENGINE": target.engine,
                "DATABASE_NAME": target.name,
                **(
                    {}
                    if target.engine == "sqlite"
                    else {
                        "DATABASE_HOST": target.host,
                        "DATABASE_PORT": target.effective_port,
                        "DATABASE_USER": target.user or "",
                        "DATABASE_PASSWORD": target.password or "",
                    }
                ),
            }
        )


def uploads_pack(args):
    from helper.archive import pack_uploads

    output = args.output
    if output is None:
        (BASE_DIR / BACKUP_DIR).mkdir(mode=0o700, exist_ok=True)
        output = BASE_DIR / BACKUP_DIR / f"uploads_{date.today().isoformat()}.tar.gz"
    pack_uploads(BASE_DIR / UPLOAD_DIR, output)


def uploads_unpack(args):
    from helper.archive import fetch, unpack_uploads

    with tempfile.TemporaryDirectory(prefix="higeo-") as directory:
        unpack_uploads(fetch(args.source, Path(directory)), BASE_DIR / UPLOAD_DIR, overwrite=args.overwrite)


def ask(question, default=None):
    """Ask on the terminal; Enter gives the default."""
    answer = input(f"{question}{f' [{default}]' if default else ''}: ").strip()
    return answer or default or ""


def quicksetup(_args):
    """Walk through a new installation. Every step can be skipped by pressing Enter."""
    from helper.archive import fetch, unpack_uploads
    from helper.db.settings import DEFAULT_NAMES, DatabaseSettings

    print("This sets up a new Higeo installation. Press Enter to accept the value in brackets.\n")
    engine = ""
    while engine not in DATABASE_ENGINES:
        engine = ask(f"Database engine ({', '.join(DATABASE_ENGINES)})", "sqlite")
    env = {"DATABASE_ENGINE": engine}
    if engine == "sqlite":
        env["DATABASE_NAME"] = ask("File of the database", DEFAULT_NAMES[engine])
    else:
        env["DATABASE_NAME"] = ask("Database name", DEFAULT_NAMES[engine])
        env["DATABASE_HOST"] = ask("Host", "localhost")
        env["DATABASE_PORT"] = ask("Port", DEFAULT_PORTS[engine])
        env["DATABASE_USER"] = ask("User")
        env["DATABASE_PASSWORD"] = getpass.getpass("Password: ")
    if not (os.environ.get("SECRET_KEY") or dotenv_values(ENV_FILE).get("SECRET_KEY")):
        env["SECRET_KEY"] = token_urlsafe(32)  # signs the login cookie
    write_env(env)
    os.environ.update(env)  # the settings the rest of this run (and helper, when it loads) uses
    settings = DatabaseSettings(
        engine,
        env["DATABASE_NAME"],
        env.get("DATABASE_HOST", "localhost"),
        env.get("DATABASE_PORT"),
        env.get("DATABASE_USER") or None,
        env.get("DATABASE_PASSWORD") or None,
    )
    _quicksetup_database(settings)

    uploads = ask("\nUploaded files (photos, documents) to unpack: a link to a .tar.gz or a file path, Enter to skip")
    if uploads:
        with tempfile.TemporaryDirectory(prefix="higeo-") as directory:
            unpack_uploads(fetch(uploads, Path(directory)), BASE_DIR / UPLOAD_DIR)

    email = ask("\nEmail of the first admin account, Enter to skip")
    if email:
        _quicksetup_admin(settings, email)
    print("\nSetup complete. Start the application with: uv run main.py")


def _quicksetup_database(settings):
    from helper.archive import fetch
    from helper.db.backup import restore
    from helper.db.initialise_database import create_database
    from helper.db.migrate import create_tables, has_data

    create_database(settings)
    dump = ask(
        "\nDatabase dump to load: a link or a file path (.sql, .sql.gz, .db, .db.gz), Enter for an empty database"
    )
    if not dump:
        create_tables(settings)
        print("Created the empty tables.")
        return
    force = False
    if has_data(settings):
        if ask(f"The {settings.describe()} already holds data. Replace it? (y/n)", "n") != "y":
            create_tables(settings)
            print("Kept the existing data.")
            return
        force = True
    with tempfile.TemporaryDirectory(prefix="higeo-") as directory:
        restore(settings, fetch(dump, Path(directory)), force=force)
    print("Loaded the dump.")


def _quicksetup_admin(settings, email):
    from sqlalchemy.orm import Session

    from helper.db.initialise_database import User
    from helper.login import users

    engine = settings.make_engine()
    try:
        User.metadata.create_all(engine, tables=[User.__table__])
        with Session(engine) as session:
            users.create(session, email, prompt_password())
    finally:
        engine.dispose()


DATABASE_COMMANDS = {
    "db_init": db_init,
    "db_dump": db_dump,
    "db_restore": db_restore,
    "db_migrate": db_migrate,
    "uploads_pack": uploads_pack,
    "uploads_unpack": uploads_unpack,
    "quicksetup": quicksetup,
}


def run_user_command(args, parser):
    """Run a staff account command. The database is only connected to here, so that db_set works without one."""
    from sqlalchemy.orm import Session

    from helper.db.initialise_database import User, engine
    from helper.login import users

    User.metadata.create_all(engine, tables=[User.__table__])  # only creates the users table if it is missing
    if args.command == "user_add":
        with Session(engine) as session:
            users.create(session, args.email, args.password or prompt_password())
    elif args.command == "user_edit":
        if args.new_email is None and args.password is None:
            parser.error("user_edit needs --new_email and/or --password.")
        new_password = None
        if args.password is not None:
            new_password = args.password or prompt_password()
        with Session(engine) as session:
            users.update(session, args.email, new_email=args.new_email, new_password=new_password)
    elif args.command == "user_delete":
        with Session(engine) as session:
            users.delete(session, args.email)
    elif args.command == "user_list":
        with Session(engine) as session:
            for user in users.list(session):
                print(user.email)


if __name__ == "__main__":
    main()
