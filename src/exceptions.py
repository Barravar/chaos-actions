"""Custom exceptions for Litmus Chaos Actions."""


class LitmusRestError(Exception):
    """Custom exception for Litmus REST API errors."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        """
        Initialize the exception.

        Args:
          message: Error message
          status_code: Optional HTTP status code
        """
        super().__init__(message)
        self.status_code = status_code

    def __str__(self) -> str:
        """Return string representation of the error."""
        if self.status_code:
            return f"{super().__str__()} (HTTP {self.status_code})"
        return super().__str__()


class LitmusAuthenticationError(LitmusRestError):
    """Custom exception for Litmus authentication errors."""

    pass


class LitmusGraphQLError(LitmusRestError):
    """Custom exception for Litmus GraphQL errors."""

    pass


class ExperimentTimeoutError(Exception):
    """Exception raised when an experiment times out."""

    pass
