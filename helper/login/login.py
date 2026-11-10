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
    with Session(engine) as session:
        user = users.authenticate(session, email, password)
        if user is None:
            return render(request, "login.html", status_code=401, error=_("Неверный email или пароль."))
        log_in(request, LoginUser(user.id, user.email))
    return RedirectResponse(_safe_next(request.query_params.get("next")), status_code=303)


@router.get("/logout")
def logout(request: Request):
    log_out(request)
    return RedirectResponse("/", status_code=302)
