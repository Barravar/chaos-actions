"""Litmus API client for REST and GraphQL interactions."""

import logging
from types import TracebackType
from typing import Any, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .config import LitmusConfig, RetryConfig
from .exceptions import LitmusAuthenticationError, LitmusGraphQLError, LitmusRestError


class LitmusClient:
    """Client for interacting with Litmus Chaos REST and GraphQL APIs."""

    # API path constants
    REST_BASE_PATH = "/auth"
    GRAPHQL_BASE_PATH = "/api/query"

    def __init__(
        self,
        config: LitmusConfig,
        logger: logging.Logger,
        retry_config: Optional[RetryConfig] = None,
    ) -> None:
        """
        Initialize the Litmus API client.

        Args:
          config: Litmus configuration
          logger: Logger instance
          retry_config: Optional retry configuration
        """
        self.config = config
        self.logger = logger
        self.retry_config = retry_config or RetryConfig()
        self.session = self._create_session()
        self.authenticated = False

    def __enter__(self) -> "LitmusClient":
        """Context manager entry."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Context manager exit - close session."""
        self.session.close()

    def _create_session(self) -> requests.Session:
        """
        Create HTTP session with retry strategy.

        Returns:
          Configured requests Session.
        """
        session = requests.Session()
        retries = Retry(
            total=self.retry_config.max_retries,
            backoff_factor=self.retry_config.backoff_factor,
            status_forcelist=self.retry_config.status_forcelist,
        )
        adapter = HTTPAdapter(max_retries=retries)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return session

    def authenticate(self) -> None:
        """
        Authenticate with Litmus ChaosCenter.

        Raises:
          LitmusAuthenticationError: If authentication fails.
        """
        # Avoid re-authentication if already authenticated
        if self.authenticated:
            return

        try:
            auth = self._rest_call(
                "POST",
                "/login",
                json={
                    "username": self.config.litmus_username,
                    "password": self.config.litmus_password,
                },
            )
        except requests.RequestException as e:
            self.logger.error(f"Authentication failed: {e}")
            raise LitmusAuthenticationError(f"Authentication failed: {e}") from e

        access_token = auth.json().get("accessToken", "")
        self.session.headers.update({"Authorization": f"Bearer {access_token}"})
        self.authenticated = True
        self.logger.info(f"Successfully authenticated to Litmus at {self.config.litmus_url}")

    def _rest_call(self, method: str, path: str, **kwargs: Any) -> requests.Response:
        """
        Make a REST API call to Litmus ChaosCenter.

        Args:
          method: HTTP method (GET, POST, etc.)
          path: API endpoint path
          **kwargs: Additional arguments for requests

        Returns:
          Response object from the API.

        Raises:
          LitmusRestError: If the request fails.
        """
        # Set request timeout
        kwargs.setdefault("timeout", self.retry_config.request_timeout)

        # Construct full REST API URL
        base_path = self.REST_BASE_PATH
        url = f"{self.config.litmus_url}{base_path}{path}"

        try:
            response = self.session.request(method, url, **kwargs)
            response.raise_for_status()

            # Logging the full response for debugging but mask sensitive data
            sensitive_keys = {"password", "token", "accessToken", "secret"}
            if self.logger.isEnabledFor(logging.DEBUG):
                if not any(key in response.json() for key in sensitive_keys):
                    self.logger.debug(f"REST API response from {url}: {response.text}")
                else:
                    self.logger.debug(f"REST API response from {url}: [REDACTED SENSITIVE DATA]")

            # Check response
            if not isinstance(response.json(), dict):
                self.logger.error("REST API response is not a valid JSON object.")
                raise LitmusRestError("REST API response is not a valid JSON object.")

            return response

        except requests.RequestException as e:
            status_code = (
                getattr(e.response, "status_code", None) if hasattr(e, "response") else None
            )
            self.logger.error(f"REST API request to {url} failed: {e}")
            raise LitmusRestError(f"REST API request failed: {e}", status_code=status_code) from e

    def _graphql_call(self, query: str, variables: Optional[dict[str, Any]]) -> dict[str, Any]:
        """
        Make a GraphQL API call to Litmus ChaosCenter.

        Args:
          query: GraphQL query string
          variables: Query variables

        Returns:
          Response data from the GraphQL API.

        Raises:
          LitmusGraphQLError: If the request fails.
        """
        # Construct full GraphQL API URL and payload
        base_path = self.GRAPHQL_BASE_PATH
        url = f"{self.config.litmus_url}{base_path}"
        payload = {"query": query, "variables": variables}

        # Log the payload for debugging
        self.logger.debug(f"GraphQL payload: {payload}")

        try:
            response = self.session.post(
                url, json=payload, timeout=self.retry_config.graphql_timeout
            )

            # Log response for debugging before checking status
            self.logger.debug(f"GraphQL response status: {response.status_code}")
            self.logger.debug(f"GraphQL response: {response.text}")

            response.raise_for_status()
            response_data = response.json()

            # Logging the full response for debugging
            self.logger.debug(f"GraphQL response data: {response_data}")

            # Check for GraphQL errors in the response
            if not isinstance(response_data, dict):
                self.logger.error("GraphQL response is not a valid JSON object.")
                raise LitmusGraphQLError("GraphQL response is not a valid JSON object.")

            if "errors" in response_data:
                self.logger.error(f"GraphQL query returned errors: {response_data.get('errors')}")
                raise LitmusGraphQLError(
                    f"GraphQL query returned errors: {response_data.get('errors')}"
                )

            # Return the 'data' part of the response
            data = response_data.get("data")
            if not isinstance(data, dict):
                return {}
            return data

        except requests.RequestException as e:
            # Try to log response body if available
            try:
                if hasattr(e, "response") and e.response is not None:
                    self.logger.error(f"Response body: {e.response.text}")
            except Exception:  # nosec B110
                pass  # nosec B110
            self.logger.error(f"GraphQL request to {url} failed: {e}")
            raise LitmusGraphQLError(f"GraphQL request failed: {e}") from e
