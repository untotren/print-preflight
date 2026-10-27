"""Deterministic raster preflight checks for print-ready artwork."""

from .core import analyze, check
from .errors import PreflightError
from .profile import Profile, load_profile, parse_profile_json
from .reasons import REASONS

__all__ = [
    "PreflightError",
    "Profile",
    "REASONS",
    "analyze",
    "check",
    "load_profile",
    "parse_profile_json",
]
__version__ = "0.1.0"
