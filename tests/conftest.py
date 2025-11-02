"""Shared pytest fixtures for application smoke tests."""

from collections.abc import Generator
from pathlib import Path
import sys

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import create_app
from extensions import db
from models import User


@pytest.fixture
def app() -> Generator:
    app = create_app()
    app.config.update(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "WTF_CSRF_ENABLED": False,
        }
    )

    with app.app_context():
        db.drop_all()
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def root_user(app) -> User:
    """Create a default root user for authentication flows."""

    with app.app_context():
        user = User(username="root", password="password123", role="root")
        db.session.add(user)
        db.session.commit()
        return user
