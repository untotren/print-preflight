"""Deterministic raster preflight for print-ready artwork."""

from .core import analyze, check_image, content_mask
from .errors import ImageError, PreflightError, ProfileError
from .profile import Profile, load_profile
from .reasons import REASONS

__all__ = [
    "REASONS",
    "ImageError",
    "PreflightError",
    "Profile",
    "ProfileError",
    "analyze",
    "check_image",
    "content_mask",
    "load_profile",
]
__version__ = "0.1.0"
