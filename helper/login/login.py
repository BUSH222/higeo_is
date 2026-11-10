"""Staff login with email and password. Intentionally not linked from any page."""

from typing import Annotated
from urllib.parse import urlsplit

from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from helper.db.initialise_database import engine
from helper.i18n import gettext as _
from helper.login import users
from helper.login.auth import log_in, log_out
from helper.login.objects import LoginUser
from helper.login.throttle import clear_attempts, is_locked_out, record_failed_attempt
from helper.templating import render

router = APIRouter()


def _safe_next(target):
    """Only allow redirects to a path on this site."""
    if target and not urlsplit(target).netloc and target.startswith("/") and not target.startswith("//"):
        return target
    return "/search"


@router.get("/login")
def login_form(request: Request):
    return render(request, "login.html", error=None)


@router.post("/login")
def login(request: Request, email: Annotated[str, Form()] = "", password: Annotated[str, Form()] = ""):
    ip_key = f"ip:{request.client.host if request.client else 'unknown'}"
    email_key = f"email:{email.strip().lower()}"
    if is_locked_out(ip_key) or is_locked_out(email_key):
        error = _("Слишком много неудачных попыток входа. Повторите попытку через 15 минут.")
        return render(request, "login.html", status_code=429, error=error)
    with Session(engine) as session:
        user = users.authenticate(session, email, password)
        if user is None:
            record_failed_attempt(ip_key)
            record_failed_attempt(email_key)
            return render(request, "login.html", status_code=401, error=_("Неверный email или пароль."))
        clear_attempts(ip_key)
        clear_attempts(email_key)
        log_in(request, LoginUser(user.id, user.email))
    return RedirectResponse(_safe_next(request.query_params.get("next")), status_code=303)


@router.get("/logout")
def logout(request: Request):
    log_out(request)
    return RedirectResponse("/", status_code=302)
