import argparse
import getpass

from sqlalchemy.orm import Session

from helper.db.initialise_database import User, engine
from helper.login import users


def prompt_password():
    """Ask for a password twice without echoing it."""
    password = getpass.getpass("Password: ")
    if password != getpass.getpass("Repeat password: "):
        raise SystemExit("The passwords do not match.")
    return password


def main():
    """Manage staff accounts."""
    parser = argparse.ArgumentParser(description="Manage staff accounts.")
    subparsers = parser.add_subparsers(dest="command")

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
        return
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


if __name__ == "__main__":
    main()
