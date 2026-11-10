import argparse
import getpass
import os
import re
from pathlib import Path

from dotenv import dotenv_values, find_dotenv, set_key

DATABASE_ENGINES = ("sqlite", "postgresql", "mysql")
DEFAULT_PORTS = {"postgresql": "5432", "mysql": "3306"}
DEFAULT_SQLITE_FILE = "higeo.sqlite3"
ENV_FILE = find_dotenv() or os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = "static/uploads"  # relative to the project, and stored in the database in this form


def prompt_password():
    """Ask for a password twice without echoing it."""
    password = getpass.getpass("Password: ")
    if password != getpass.getpass("Repeat password: "):
        raise SystemExit("The passwords do not match.")
    return password


def main():
    """Manage the database settings and the staff accounts."""
    parser = argparse.ArgumentParser(description="Manage the database settings and the staff accounts.")
    subparsers = parser.add_subparsers(dest="command")

    db_set_parser = subparsers.add_parser("db_set", help="Choose the database engine (saved to .env).")
    db_set_parser.add_argument("engine", choices=DATABASE_ENGINES, help="Database engine.")
    db_set_parser.add_argument("-n", "--name", help="Database name, or the path of the file for sqlite.")
    db_set_parser.add_argument("-H", "--host", help="Database host (not used by sqlite).")
    db_set_parser.add_argument("-P", "--port", help="Database port (not used by sqlite).")
    db_set_parser.add_argument("-u", "--user", help="Database user (not used by sqlite).")
    db_set_parser.add_argument(
        "-p", "--password", nargs="?", const="", help="Database password (prompted for if empty; not used by sqlite)."
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

    if not os.path.exists(ENV_FILE):
        with open(ENV_FILE, "w", encoding="utf-8"):
            pass
        os.chmod(ENV_FILE, 0o600)  # the file holds the database password and the secret key
    for key, value in settings.items():
        set_key(ENV_FILE, key, value)
        print(f"{key} = {'***' if key == 'DATABASE_PASSWORD' and value else value}")
    print(f"Saved to {ENV_FILE}. Run `python -m helper` to create the database and its tables.")


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
