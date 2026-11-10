"""Rendering of the Jinja templates."""

from pathlib import Path
from typing import TYPE_CHECKING

from fastapi.templating import Jinja2Templates

from helper import i18n
from helper.login.auth import get_current_user
from helper.login.csrf import get_or_create_csrf_token

if TYPE_CHECKING:
    from fastapi import Request
    from fastapi.responses import HTMLResponse

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"

templates = Jinja2Templates(directory=TEMPLATES_DIR)
i18n.install(templates.env)


def render(request: Request, name: str, status_code: int = 200, **context) -> HTMLResponse:
    """Render a template, giving it the current user and locale."""
    context["current_user"] = get_current_user(request)
    context["current_locale"] = i18n.get_locale()
    context["csrf_token"] = get_or_create_csrf_token(request)
    return templates.TemplateResponse(request, name, context, status_code=status_code)
