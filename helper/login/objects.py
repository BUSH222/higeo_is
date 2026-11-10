from flask_login import UserMixin


class LoginUser(UserMixin):
    """Lightweight, session-independent view of a staff user for flask-login."""

    def __init__(self, id, email):
        self.id = str(id)
        self.email = email

    def __repr__(self):
        return self.email
