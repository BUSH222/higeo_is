"""Staff login with email and password. Intentionally not linked from any page."""

from urllib.parse import urlsplit

from flask import Blueprint, redirect, render_template, request, url_for
from flask_babel import gettext as _
from flask_login import LoginManager, login_user, logout_user
from sqlalchemy.orm import Session

from helper.db.initialise_database import engine
from helper.login import users
from helper.login.objects import LoginUser

app_login = Blueprint("app_login", __name__)
login_manager = LoginManager()
login_manager.login_view = "app_login.login"


@login_manager.user_loader
def load_user(user_id):
    try:
        user_pk = int(user_id)
    except ValueError:
        return None
    with Session(engine) as session:
        user = users.get(session, user_pk)
        return LoginUser(user.id, user.email) if user else None


def _safe_next(target):
    """Only allow redirects to a path on this site."""
    if target and not urlsplit(target).netloc and target.startswith("/") and not target.startswith("//"):
        return target
    return url_for("search")


@app_login.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html", error=None)
    with Session(engine) as session:
        user = users.authenticate(session, request.form.get("email", ""), request.form.get("password", ""))
        if user is None:
            return render_template("login.html", error=_("Неверный email или пароль.")), 401
        login_user(LoginUser(user.id, user.email))
    return redirect(_safe_next(request.args.get("next")))


@app_login.route("/logout")
def logout():
    logout_user()
    return redirect("/")
