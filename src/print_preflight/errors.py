class PreflightError(Exception):
    """Raised for invalid input (unreadable image, bad profile). CLI exit code 3."""


class ProfileError(PreflightError):
    pass


class ImageLoadError(PreflightError):
    pass
