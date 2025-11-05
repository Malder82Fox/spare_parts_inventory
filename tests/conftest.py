# tests/conftest.py
# tests/conftest.py
import os
import sys
import pytest

# чтобы import create_app работал при запуске из корня
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app import create_app
from extensions import db


@pytest.fixture()
def app():
    app = create_app()
    app.config.update(
        TESTING=True,
        SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
        WTF_CSRF_ENABLED=False,
        LOGIN_DISABLED=True,          # ← ключевая строка: отключаем логин в тестах
        SECRET_KEY="test-secret",     # чтобы не ругался Flask-Login/сессии
    )
    with app.app_context():
        db.create_all()
        yield app


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def root_user():
    class U:
        id = 1
        username = "root"
        role = "root"
    return U()
