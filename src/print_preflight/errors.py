"""Exceptions raised by print_preflight. All map to CLI exit code 3."""


class PreflightError(Exception):
    """Base class for errors that prevent a report from being produced."""


class ProfileError(PreflightError):
    """The target profile is missing, unreadable or invalid."""


class ImageError(PreflightError):
    """The input image is missing, unreadable or in an unsupported format."""
