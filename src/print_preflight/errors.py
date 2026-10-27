"""Error type for conditions that prevent a report from being produced."""


class PreflightError(Exception):
    """Raised for invalid input; ``code`` is a documented reason code."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message
