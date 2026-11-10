"""Translations: the locale of the current request and gettext for Python code and templates."""

from contextvars import ContextVar
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import parse_qs

from babel.support import Translations

if TYPE_CHECKING:
    from jinja2 import Environment

LANGUAGES = ["ru", "en"]
DEFAULT_LOCALE = "ru"
TRANSLATIONS_DIR = Path(__file__).resolve().parent.parent / "translations"

_locale: ContextVar[str] = ContextVar("locale", default=DEFAULT_LOCALE)
_translations = {lang: Translations.load(TRANSLATIONS_DIR, [lang]) for lang in LANGUAGES}


def get_locale() -> str:
    """The locale of the request being handled."""
    return _locale.get()


def gettext(message: str, **variables) -> str:
    """Translate a message to the current locale, filling in `%(name)s` placeholders."""
    translated = _translations[get_locale()].gettext(message)
    return translated % variables if variables else translated


def ngettext(singular: str, plural: str, n: int, **variables) -> str:
    """Translate a message that has a plural form."""
    variables.setdefault("num", n)
    return _translations[get_locale()].ngettext(singular, plural, n) % variables


def install(env: Environment) -> None:
    """Make `_()` and `{% trans %}` in templates translate to the current locale."""
    env.add_extension("jinja2.ext.i18n")
    env.install_gettext_callables(  # ty: ignore[missing-attribute] (added by the i18n extension)
        lambda message: _translations[get_locale()].gettext(message),
        lambda singular, plural, n: _translations[get_locale()].ngettext(singular, plural, n),
        newstyle=True,
    )


class LocaleMiddleware:
    """Choose the locale of each request: explicit ?lang= -> session -> default.

    Must run inside the session middleware. It is a plain ASGI middleware so that the locale set here is
    seen by the route handlers.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        session = scope.get("session", {})
        lang = parse_qs(scope["query_string"].decode("latin-1")).get("lang", [None])[0]
        if lang in LANGUAGES:
            session["lang"] = lang
        elif session.get("lang") in LANGUAGES:
            lang = session["lang"]
        else:
            lang = DEFAULT_LOCALE
        token = _locale.set(lang)
        try:
            await self.app(scope, receive, send)
        finally:
            _locale.reset(token)
