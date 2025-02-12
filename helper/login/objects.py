from flask_login import UserMixin


class User(UserMixin):
    def __init__(self, id, email):
        self.id = id
        self.email = email

    def __repr__(self):
        return self.email
