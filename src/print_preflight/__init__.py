"""Deterministic raster preflight for print-ready artwork."""

from .checks import REASONS, check
from .profile import PreflightError, Profile, load_profile, profile_from_dict

__all__ = ["REASONS", "PreflightError", "Profile", "check", "load_profile", "profile_from_dict"]
__version__ = "0.1.0"
