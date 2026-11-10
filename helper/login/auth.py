"""Who is logged in: the staff user is remembered in the signed session cookie."""

from urllib.parse import quote

from fastapi import Request  # noqa: TC002 (FastAPI reads the annotation of require_login at runtime)
from sqlalchemy.orm import Session

from helper.db.initialise_database import engine
from helper.login import users
from helper.login.objects import AnonymousUser, LoginUser

SESSION_KEY = "user_id"


class LoginRequired(Exception):
    """Raised when a page needs a logged in user. Handled by redirecting to the login page."""

    def __init__(self, next_url: str):
        self.next_url = next_url

    @property
    def login_url(self) -> str:
        return f"/login?next={quote(self.next_url, safe='')}"


def log_in(request: Request, user: LoginUser) -> None:
    """Remember the user in a fresh session, keeping only the chosen language."""
    lang = request.session.get("lang")
    request.session.clear()
    if lang:
        request.session["lang"] = lang
    request.session[SESSION_KEY] = user.id


def log_out(request: Request) -> None:
    request.session.pop(SESSION_KEY, None)


def get_current_user(request: Request) -> LoginUser | AnonymousUser:
    """The logged in user of this request, or an anonymous user. Looked up once per request."""
    user: LoginUser | AnonymousUser | None = getattr(request.state, "user", None)
    if user is None:
        user = request.state.user = _load_user(request.session.get(SESSION_KEY))
    return user


def _load_user(user_id) -> LoginUser | AnonymousUser:
    try:
        user_pk = int(user_id)
    except TypeError, ValueError:
        return AnonymousUser()
    with Session(engine) as session:
        user = users.get(session, user_pk)
        return LoginUser(user.id, user.email) if user else AnonymousUser()


def require_login(request: Request) -> None:
    """Route dependency: only let logged in users through."""
    if not get_current_user(request).is_authenticated:
        next_url = request.url.path + (f"?{request.url.query}" if request.url.query else "")
        raise LoginRequired(next_url)
