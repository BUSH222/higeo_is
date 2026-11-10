class LoginUser:
    """Lightweight, session-independent view of a logged in staff user."""

    is_authenticated = True

    def __init__(self, id, email):
        self.id = str(id)
        self.email = email

    def __repr__(self):
        return self.email


class AnonymousUser:
    """A visitor who is not logged in."""

    is_authenticated = False
    id = None
    email = None

    def __repr__(self):
        return "anonymous"
