"""Staff users: password hashing and management."""

from typing import TYPE_CHECKING

from sqlalchemy import select
from werkzeug.security import check_password_hash, generate_password_hash

from helper.db.initialise_database import User

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

MIN_PASSWORD_LENGTH = 8

# Verified against when the email is unknown, so that response time does not reveal which emails exist.
_DUMMY_HASH = generate_password_hash("dummy-password")


def normalise_email(email: str) -> str:
    """Normalise an email address, raising ValueError if it is not valid."""
    email = email.strip().lower()
    local, _, domain = email.partition("@")
    if not local or "." not in domain or " " in email:
        raise ValueError(f"Invalid email address: {email!r}")
    return email


def validate_password(password: str) -> None:
    """Raise ValueError if the password is too short."""
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"The password must be at least {MIN_PASSWORD_LENGTH} characters long.")


def get(session: Session, user_id: int) -> User | None:
    return session.get(User, user_id)


def get_by_email(session: Session, email: str) -> User | None:
    return session.scalars(select(User).where(User.email == email.strip().lower())).first()


def authenticate(session: Session, email: str, password: str) -> User | None:
    """Return the user if the credentials are correct, otherwise None."""
    user = get_by_email(session, email)
    if user is None:
        check_password_hash(_DUMMY_HASH, password)
        return None
    return user if check_password_hash(user.password_hash, password) else None


def create(session: Session, email: str, password: str) -> User:
    """Create a user with a hashed password."""
    email = normalise_email(email)
    validate_password(password)
    if get_by_email(session, email):
        raise ValueError(f"A user with the email {email} already exists.")
    user = User(email=email, password_hash=generate_password_hash(password))
    session.add(user)
    session.commit()
    return user


def update(session: Session, email: str, new_email: str | None = None, new_password: str | None = None) -> None:
    """Change the email and/or the password of a user."""
    user = get_by_email(session, email)
    if user is None:
        raise ValueError(f"No user with the email {email}.")
    if new_email is not None:
        new_email = normalise_email(new_email)
        other = get_by_email(session, new_email)
        if other and other.id != user.id:
            raise ValueError(f"A user with the email {new_email} already exists.")
        user.email = new_email
    if new_password is not None:
        validate_password(new_password)
        user.password_hash = generate_password_hash(new_password)
    session.commit()


def delete(session: Session, email: str) -> None:
    user = get_by_email(session, email)
    if user is None:
        raise ValueError(f"No user with the email {email}.")
    session.delete(user)
    session.commit()
