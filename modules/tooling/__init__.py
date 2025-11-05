"""Tooling module package."""

from flask import Blueprint

bp = Blueprint("tooling", __name__, url_prefix="/tooling")

from . import models  # noqa: E402  pylint: disable=wrong-import-position
from . import routes  # noqa: E402  pylint: disable=wrong-import-position

__all__ = ["bp", "models", "routes"]
