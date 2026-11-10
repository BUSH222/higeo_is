"""CSRF protection for state-changing requests: a per-session token checked against the submitted form field."""

import secrets

from fastapi import HTTPException, Request, status

SESSION_KEY = "csrf_token"


def get_or_create_csrf_token(request: Request) -> str:
    """The CSRF token for this session, generating and storing one if there isn't one yet."""
    token = request.session.get(SESSION_KEY)
    if not token:
        token = secrets.token_urlsafe(32)
        request.session[SESSION_KEY] = token
    return token


def verify_csrf_token(request: Request, token: str) -> None:
    """Raise 403 unless the submitted token matches the one stored in the session."""
    expected = request.session.get(SESSION_KEY)
    if not expected or not token or not secrets.compare_digest(expected, token):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Invalid or missing CSRF token.")
