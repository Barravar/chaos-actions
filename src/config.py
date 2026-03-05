"""Configuration classes for Litmus Chaos Actions."""

import logging
from dataclasses import dataclass, field
from os import getenv


class LoggerConfig:
    """Configuration for application logging."""

    LOG_FORMAT = "%(asctime)s - %(levelname)s: %(message)s"
    DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

    @staticmethod
    def setup_logger() -> logging.Logger:
        """
        Set up and configure the application logger.

        Returns:
          Configured logger instance.
        """
        logging.basicConfig(
            format=LoggerConfig.LOG_FORMAT,
            datefmt=LoggerConfig.DATE_FORMAT,
            level=logging.DEBUG if getenv("LOG_LEVEL") == "DEBUG" else logging.INFO,
        )
        return logging.getLogger(__name__)


@dataclass
class LitmusConfig:
    """
    Configuration for Litmus Chaos Center connection and experiment settings.

    Attributes:
      litmus_url: URL of the Litmus ChaosCenter
      litmus_username: Username for authentication
      litmus_password: Password for authentication (not shown in repr)
      litmus_project: Name of the Litmus project
      litmus_environment: Name of the Litmus environment
      litmus_infra: Name of the Chaos Infrastructure
      experiment_name: Name of existing experiment to run
      experiment_manifest: YAML manifest content or file path
      run_experiment: Whether to run the experiment after creation
    """

    litmus_url: str = ""
    litmus_username: str = ""
    litmus_password: str = field(repr=False, default="")
    litmus_project: str = ""
    litmus_environment: str = ""
    litmus_infra: str = ""
    experiment_name: str = ""
    experiment_manifest: str = ""
    run_experiment: bool = False

    _logger: logging.Logger = field(init=False, repr=False)

    def __post_init__(self) -> None:
        """Initialize logger and validate configuration."""
        self._logger = LoggerConfig.setup_logger()
        self.normalize_url()
        self.validate()

    def normalize_url(self) -> None:
        """Normalize the Litmus URL by adding protocol if missing."""
        self.litmus_url = self.litmus_url.rstrip("/")
        if not self.litmus_url.startswith(("http://", "https://")):
            self.litmus_url = f"https://{self.litmus_url}"

    def validate(self) -> None:
        """
        Validate that all required configuration is present.

        Raises:
          ValueError: If required configuration is missing.
        """
        required_attrs = {
            "litmus_url": "Litmus URL",
            "litmus_username": "Litmus username",
            "litmus_password": "Litmus password",
            "litmus_project": "Litmus project",
            "litmus_environment": "Litmus environment",
            "litmus_infra": "Chaos infrastructure name",
        }
        if not self.experiment_manifest and not self.experiment_name:
            required_attrs["experiment_manifest"] = "Experiment manifest"

        missing_attrs = [desc for attr, desc in required_attrs.items() if not getattr(self, attr)]
        if missing_attrs:
            self._logger.error(f"Missing required Litmus configuration: {', '.join(missing_attrs)}")
            raise ValueError(f"Missing: {', '.join(missing_attrs)}")


@dataclass
class RetryConfig:
    """
    Configuration for HTTP request retry logic.

    Attributes:
      max_retries: Maximum number of retry attempts
      backoff_factor: Exponential backoff factor between retries
      request_timeout: Timeout for REST API requests in seconds
      graphql_timeout: Timeout for GraphQL requests in seconds
      status_forcelist: HTTP status codes that trigger a retry
    """

    max_retries: int = int(getenv("HTTP_MAX_RETRIES", "5"))
    backoff_factor: float = float(getenv("HTTP_BACKOFF_FACTOR", "0.3"))
    request_timeout: int = int(getenv("REQUEST_TIMEOUT", "30"))
    graphql_timeout: int = int(getenv("GRAPHQL_TIMEOUT", "60"))
    status_forcelist: tuple[int, ...] = (500, 502, 503, 504)

    def __post_init__(self) -> None:
        """Validate retry configuration values."""
        if self.max_retries < 0:
            raise ValueError("max_retries must be non-negative")
        if self.backoff_factor < 0:
            raise ValueError("backoff_factor must be non-negative")
        if self.request_timeout <= 0:
            raise ValueError("request_timeout must be positive")
        if self.graphql_timeout <= 0:
            raise ValueError("graphql_timeout must be positive")
