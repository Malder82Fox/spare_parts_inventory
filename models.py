"""Shared SQLAlchemy models."""

from flask_login import UserMixin

from extensions import db


class User(UserMixin, db.Model):
    """Represents an authenticated application user."""

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    role = db.Column(db.String(50), nullable=False)  # user, admin, root

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<User {self.username}>"
