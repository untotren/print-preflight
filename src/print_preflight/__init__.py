"""Deterministic raster preflight checks for print-ready artwork."""

from .checks import REASON_CODES, analyze, check_image, measure_resolution, open_image
from .errors import ERROR_CODES, PreflightError
from .profile import Profile, load_profile

__all__ = [
    "ERROR_CODES",
    "REASON_CODES",
    "PreflightError",
    "Profile",
    "analyze",
    "check_image",
    "load_profile",
    "measure_resolution",
    "open_image",
]
__version__ = "0.1.0"
