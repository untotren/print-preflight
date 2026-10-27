"""Error type for conditions that prevent a report from being produced."""


class PreflightError(Exception):
    """Raised for unreadable inputs or invalid profiles (CLI exit code 3).

    ``code`` is a stable machine-readable identifier documented in README.
    """

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
