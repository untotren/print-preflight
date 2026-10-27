"""Deterministic raster preflight checks for print-ready artwork."""

__version__ = "0.1.0"

from .analysis import check_image, load_image, preflight  # noqa: E402
from .errors import ImageLoadError, PreflightError, ProfileError  # noqa: E402
from .profile import Profile, load_profile  # noqa: E402
from .reasons import REASONS  # noqa: E402

__all__ = [
    "REASONS",
    "ImageLoadError",
    "PreflightError",
    "Profile",
    "ProfileError",
    "check_image",
    "load_image",
    "load_profile",
    "preflight",
]
