"""Spare parts module package."""

from flask import Blueprint

bp = Blueprint("main", __name__, url_prefix="/parts")

from . import models  # noqa: E402  pylint: disable=wrong-import-position
from . import routes  # noqa: E402  pylint: disable=wrong-import-position

__all__ = ["bp", "models", "routes"]
