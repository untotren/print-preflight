"""Error type raised for conditions that prevent a report from being produced."""

ERROR_CODES = {
    "PROFILE_UNREADABLE": "The profile file is missing, unreadable, or not valid JSON.",
    "PROFILE_INVALID": "The profile JSON has missing, unknown, or out-of-range fields.",
    "IMAGE_NOT_FOUND": "The image path does not exist or is not a file.",
    "IMAGE_UNREADABLE": "The image could not be decoded.",
    "IMAGE_FORMAT_UNSUPPORTED": "The image is not PNG, JPEG or TIFF, or uses an unsupported pixel mode.",
    "OUTPUT_UNWRITABLE": "The --out report file could not be written.",
    "USAGE": "The command line was invalid.",
}


class PreflightError(Exception):
    """A preflight could not be completed. ``code`` is one of ``ERROR_CODES``."""

    def __init__(self, code: str, message: str):
        if code not in ERROR_CODES:
            raise ValueError(f"unknown error code {code!r}")
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
