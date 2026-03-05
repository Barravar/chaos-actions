#!/usr/bin/env python3
"""Unit tests for LitmusClient class."""

from unittest.mock import Mock, patch

import pytest
from requests.exceptions import HTTPError, RequestException

from src.client import LitmusClient
from src.exceptions import LitmusAuthenticationError, LitmusGraphQLError, LitmusRestError


class TestLitmusClientInitialization:
    """Tests for LitmusClient initialization."""

    def test_client_initialization(self, mock_config, mock_logger):
        """Test client initializes with correct attributes."""
        client = LitmusClient(mock_config, mock_logger)

        assert client.config == mock_config
        assert client.logger == mock_logger
        assert client.authenticated is False
        assert client.session is not None

    def test_client_with_retry_config(self, mock_config, mock_logger, mock_retry_config):
        """Test client initializes with custom retry config."""
        client = LitmusClient(mock_config, mock_logger, mock_retry_config)

        assert client.retry_config == mock_retry_config

    def test_client_creates_session_with_retries(self, mock_config, mock_logger):
        """Test that session is created with retry strategy."""
        client = LitmusClient(mock_config, mock_logger)

        # Verify session has adapters mounted
        assert "http://" in client.session.adapters
        assert "https://" in client.session.adapters


class TestLitmusClientContextManager:
    """Tests for LitmusClient context manager behavior."""

    def test_context_manager_enter(self, mock_config, mock_logger):
        """Test context manager __enter__ returns client."""
        client = LitmusClient(mock_config, mock_logger)

        with client as ctx_client:
            assert ctx_client is client

    def test_context_manager_exit_closes_session(self, mock_config, mock_logger):
        """Test context manager __exit__ closes session."""
        client = LitmusClient(mock_config, mock_logger)

        with patch.object(client.session, "close") as mock_close:
            with client:
                pass
            mock_close.assert_called_once()

    def test_context_manager_exit_with_exception(self, mock_config, mock_logger):
        """Test context manager closes session even on exception."""
        client = LitmusClient(mock_config, mock_logger)

        with patch.object(client.session, "close") as mock_close:
            try:
                with client:
                    raise ValueError("Test error")
            except ValueError:
                pass
            mock_close.assert_called_once()


class TestLitmusClientAuthentication:
    """Tests for authentication functionality."""

    def test_authenticate_success(self, mock_config, mock_logger):
        """Test successful authentication."""
        client = LitmusClient(mock_config, mock_logger)

        mock_response = Mock()
        mock_response.json.return_value = {"accessToken": "test-token-12345"}

        with patch.object(client, "_rest_call", return_value=mock_response):
            client.authenticate()

        assert client.authenticated is True
        assert "Authorization" in client.session.headers
        assert client.session.headers["Authorization"] == "Bearer test-token-12345"

    def test_authenticate_already_authenticated(self, mock_config, mock_logger):
        """Test that re-authentication is skipped when already authenticated."""
        client = LitmusClient(mock_config, mock_logger)
        client.authenticated = True

        with patch.object(client, "_rest_call") as mock_rest:
            client.authenticate()
            mock_rest.assert_not_called()

    def test_authenticate_failure_invalid_credentials(self, mock_config, mock_logger):
        """Test authentication failure with invalid credentials."""
        client = LitmusClient(mock_config, mock_logger)

        with patch.object(client, "_rest_call", side_effect=RequestException("401 Unauthorized")):
            with pytest.raises(LitmusAuthenticationError, match="Authentication failed"):
                client.authenticate()

        assert client.authenticated is False

    def test_authenticate_missing_access_token(self, mock_config, mock_logger):
        """Test authentication when response is missing accessToken."""
        client = LitmusClient(mock_config, mock_logger)

        mock_response = Mock()
        mock_response.json.return_value = {}  # No accessToken

        with patch.object(client, "_rest_call", return_value=mock_response):
            client.authenticate()

        # Should still mark as authenticated even with empty token
        assert client.authenticated is True
        assert client.session.headers["Authorization"] == "Bearer "


class TestLitmusClientRestCall:
    """Tests for REST API calls."""

    def test_rest_call_success(self, mock_config, mock_logger):
        """Test successful REST API call."""
        client = LitmusClient(mock_config, mock_logger)

        mock_response = Mock()
        mock_response.json.return_value = {"success": True, "data": "test"}
        mock_response.raise_for_status = Mock()

        with patch.object(client.session, "request", return_value=mock_response):
            response = client._rest_call("GET", "/test_endpoint")

        assert response == mock_response
        mock_response.raise_for_status.assert_called_once()

    def test_rest_call_constructs_correct_url(self, mock_config, mock_logger):
        """Test that REST call constructs correct URL."""
        client = LitmusClient(mock_config, mock_logger)

        mock_response = Mock()
        mock_response.json.return_value = {"success": True}
        mock_response.raise_for_status = Mock()

        with patch.object(client.session, "request", return_value=mock_response) as mock_request:
            client._rest_call("POST", "/login", json={"test": "data"})

            expected_url = "https://litmus.example.com/auth/login"
            mock_request.assert_called_once()
            assert mock_request.call_args[0][1] == expected_url

    def test_rest_call_sets_timeout(self, mock_config, mock_logger, mock_retry_config):
        """Test that REST call sets timeout from config."""
        client = LitmusClient(mock_config, mock_logger, mock_retry_config)

        mock_response = Mock()
        mock_response.json.return_value = {"success": True}
        mock_response.raise_for_status = Mock()

        with patch.object(client.session, "request", return_value=mock_response) as mock_request:
            client._rest_call("GET", "/test")

            assert "timeout" in mock_request.call_args[1]
            assert mock_request.call_args[1]["timeout"] == mock_retry_config.request_timeout

    def test_rest_call_handles_http_error(self, mock_config, mock_logger):
        """Test REST call error handling."""
        client = LitmusClient(mock_config, mock_logger)

        mock_response = Mock()
        mock_response.status_code = 404
        error = HTTPError(response=mock_response)

        with patch.object(client.session, "request", side_effect=error):
            with pytest.raises(LitmusRestError, match="REST API request failed"):
                client._rest_call("GET", "/nonexistent")

    def test_rest_call_invalid_json_response(self, mock_config, mock_logger):
        """Test error when REST response is not valid JSON object."""
        client = LitmusClient(mock_config, mock_logger)

        mock_response = Mock()
        mock_response.json.return_value = ["not", "a", "dict"]  # List instead of dict
        mock_response.raise_for_status = Mock()

        with patch.object(client.session, "request", return_value=mock_response):
            with pytest.raises(LitmusRestError, match="not a valid JSON object"):
                client._rest_call("GET", "/test")

    def test_rest_call_redacts_sensitive_data_in_logs(self, mock_config, mock_logger):
        """Test that sensitive data is redacted in debug logs."""
        mock_logger.isEnabledFor = Mock(return_value=True)
        client = LitmusClient(mock_config, mock_logger)

        mock_response = Mock()
        mock_response.json.return_value = {"accessToken": "secret-token", "data": "test"}
        mock_response.raise_for_status = Mock()
        mock_response.text = '{"accessToken":"secret-token"}'

        with patch.object(client.session, "request", return_value=mock_response):
            client._rest_call("POST", "/login")

        # Check that debug was called with redacted message
        debug_calls = [call for call in mock_logger.debug.call_args_list]
        assert any("REDACTED" in str(call) for call in debug_calls)


class TestLitmusClientGraphQLCall:
    """Tests for GraphQL API calls."""

    def test_graphql_call_success(self, mock_config, mock_logger):
        """Test successful GraphQL API call."""
        client = LitmusClient(mock_config, mock_logger)

        mock_response = Mock()
        mock_response.json.return_value = {
            "data": {"projects": [{"name": "test", "projectID": "123"}]}
        }
        mock_response.raise_for_status = Mock()
        mock_response.status_code = 200

        with patch.object(client.session, "post", return_value=mock_response):
            result = client._graphql_call("query { projects }", {"var": "value"})

        assert "projects" in result
        assert result["projects"][0]["projectID"] == "123"

    def test_graphql_call_constructs_correct_payload(self, mock_config, mock_logger):
        """Test that GraphQL call constructs correct payload."""
        client = LitmusClient(mock_config, mock_logger)

        mock_response = Mock()
        mock_response.json.return_value = {"data": {}}
        mock_response.raise_for_status = Mock()
        mock_response.status_code = 200
        mock_response.text = '{"data":{}}'

        query = "query Test { projects }"
        variables = {"projectID": "123"}

        with patch.object(client.session, "post", return_value=mock_response) as mock_post:
            client._graphql_call(query, variables)

            call_kwargs = mock_post.call_args[1]
            assert call_kwargs["json"]["query"] == query
            assert call_kwargs["json"]["variables"] == variables

    def test_graphql_call_with_errors_in_response(self, mock_config, mock_logger):
        """Test GraphQL call when response contains errors."""
        client = LitmusClient(mock_config, mock_logger)

        mock_response = Mock()
        mock_response.json.return_value = {"errors": [{"message": "Field not found"}]}
        mock_response.raise_for_status = Mock()
        mock_response.status_code = 200
        mock_response.text = '{"errors":[{"message":"Field not found"}]}'

        with patch.object(client.session, "post", return_value=mock_response):
            with pytest.raises(LitmusGraphQLError, match="GraphQL query returned errors"):
                client._graphql_call("query { invalid }", {})

    def test_graphql_call_invalid_json_response(self, mock_config, mock_logger):
        """Test error when GraphQL response is not valid JSON."""
        client = LitmusClient(mock_config, mock_logger)

        mock_response = Mock()
        mock_response.json.return_value = ["not", "a", "dict"]
        mock_response.raise_for_status = Mock()
        mock_response.status_code = 200
        mock_response.text = '["not","a","dict"]'

        with patch.object(client.session, "post", return_value=mock_response):
            with pytest.raises(LitmusGraphQLError, match="not a valid JSON object"):
                client._graphql_call("query { test }", {})

    def test_graphql_call_network_error(self, mock_config, mock_logger):
        """Test GraphQL call handles network errors."""
        client = LitmusClient(mock_config, mock_logger)

        with patch.object(
            client.session, "post", side_effect=RequestException("Connection timeout")
        ):
            with pytest.raises(LitmusGraphQLError, match="GraphQL request failed"):
                client._graphql_call("query { test }", {})

    def test_graphql_call_sets_timeout(self, mock_config, mock_logger, mock_retry_config):
        """Test that GraphQL call uses correct timeout."""
        client = LitmusClient(mock_config, mock_logger, mock_retry_config)

        mock_response = Mock()
        mock_response.json.return_value = {"data": {}}
        mock_response.raise_for_status = Mock()
        mock_response.status_code = 200
        mock_response.text = '{"data":{}}'

        with patch.object(client.session, "post", return_value=mock_response) as mock_post:
            client._graphql_call("query { test }", {})

            assert mock_post.call_args[1]["timeout"] == mock_retry_config.graphql_timeout

    def test_graphql_call_returns_empty_dict_when_no_data(self, mock_config, mock_logger):
        """Test that GraphQL call returns empty dict when data field is missing."""
        client = LitmusClient(mock_config, mock_logger)

        mock_response = Mock()
        mock_response.json.return_value = {}  # No 'data' field
        mock_response.raise_for_status = Mock()
        mock_response.status_code = 200
        mock_response.text = "{}"

        with patch.object(client.session, "post", return_value=mock_response):
            result = client._graphql_call("query { test }", {})
            assert result == {}
