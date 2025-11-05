"""Maintenance module package."""

from flask import Blueprint

bp = Blueprint("maintenance", __name__, url_prefix="/maintenance")

from . import models  # noqa: E402  pylint: disable=wrong-import-position
from . import routes  # noqa: E402  pylint: disable=wrong-import-position

__all__ = ["bp", "models", "routes"]
