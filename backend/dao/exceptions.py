"""DAO-level exceptions for better error handling."""


class DAOError(Exception):
    """Base exception for DAO operations."""

    pass


class DuplicateRecordError(DAOError):
    """Raised when attempting to insert a duplicate record."""

    def __init__(self, message: str = "Record already exists", details: str | None = None):
        self.message = message
        self.details = details
        super().__init__(self.message)
