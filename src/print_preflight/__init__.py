"""Deterministic raster preflight checks for print-ready artwork."""

from .core import preflight
from .errors import PreflightError
from .profile import Profile

__all__ = ["preflight", "PreflightError", "Profile"]
__version__ = "0.1.0"
