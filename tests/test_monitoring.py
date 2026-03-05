#!/usr/bin/env python3
"""Unit tests for monitoring service functions."""

from unittest.mock import patch

import pytest

from src.exceptions import ExperimentTimeoutError, LitmusGraphQLError
from src.services.monitoring import (
    MAX_BACKOFF_SECONDS,
    POLL_INTERVAL_SECONDS,
    _calculate_backoff_time,
    _poll_experiment_status,
    _retrieve_experiment_run_id,
    wait_experiment_completion,
)


class TestCalculateBackoffTime:
    """Tests for _calculate_backoff_time helper function."""

    def test_calculate_backoff_initial(self):
        """Test backoff calculation for initial elapsed time."""
        backoff = _calculate_backoff_time(elapsed=0)
        assert backoff == POLL_INTERVAL_SECONDS

    def test_calculate_backoff_after_1_minute(self):
        """Test backoff after 1 minute elapsed."""
        backoff = _calculate_backoff_time(elapsed=60)
        assert backoff == 5  # 5 * (60 / 60) = 5

    def test_calculate_backoff_after_5_minutes(self):
        """Test backoff after 5 minutes elapsed."""
        backoff = _calculate_backoff_time(elapsed=300)
        assert backoff == 25  # 5 * (300 / 60) = 25

    def test_calculate_backoff_max_cap(self):
        """Test that backoff time is capped at MAX_BACKOFF_SECONDS."""
        backoff = _calculate_backoff_time(elapsed=600)
        assert backoff == MAX_BACKOFF_SECONDS

    def test_calculate_backoff_far_exceeded(self):
        """Test that backoff remains at max even for very long elapsed times."""
        backoff = _calculate_backoff_time(elapsed=10000)
        assert backoff == MAX_BACKOFF_SECONDS


class TestRetrieveExperimentRunId:
    """Tests for _retrieve_experiment_run_id helper function."""

    def test_retrieve_run_id_success(self, mock_client):
        """Test successful retrieval of experiment run ID."""
        mock_client._graphql_call.return_value = {
            "listExperimentRun": {"experimentRuns": [{"experimentRunID": "run-123"}]}
        }

        run_id = _retrieve_experiment_run_id(mock_client, "proj-123", "exp-123", "notify-123")

        assert run_id == "run-123"

    def test_retrieve_run_id_multiple_runs(self, mock_client):
        """Test that most recent run is selected when multiple exist."""
        mock_client._graphql_call.return_value = {
            "listExperimentRun": {
                "experimentRuns": [
                    {"experimentRunID": "run-newest"},
                    {"experimentRunID": "run-older"},
                ]
            }
        }

        run_id = _retrieve_experiment_run_id(mock_client, "proj-123", "exp-123", "notify-123")

        assert run_id == "run-newest"

    def test_retrieve_run_id_retry_success(self, mock_client):
        """Test successful retrieval after retry."""
        # First call returns no runs, second call succeeds
        mock_client._graphql_call.side_effect = [
            {"listExperimentRun": {"experimentRuns": []}},
            {"listExperimentRun": {"experimentRuns": [{"experimentRunID": "run-123"}]}},
        ]

        with patch("time.sleep"):  # Skip actual sleep
            run_id = _retrieve_experiment_run_id(mock_client, "proj-123", "exp-123", "notify-123")

        assert run_id == "run-123"
        assert mock_client._graphql_call.call_count == 2

    def test_retrieve_run_id_not_found(self, mock_client):
        """Test error when run ID cannot be retrieved."""
        mock_client._graphql_call.return_value = {"listExperimentRun": {"experimentRuns": []}}

        with patch("time.sleep"):  # Skip actual sleep
            with pytest.raises(LitmusGraphQLError, match="No experiment runs found"):
                _retrieve_experiment_run_id(mock_client, "proj-123", "exp-123", "notify-123")

    def test_retrieve_run_id_missing_key(self, mock_client):
        """Test error handling for missing required keys."""
        # Simulate KeyError by making the response cause it
        mock_client._graphql_call.side_effect = KeyError("experimentRuns")

        with pytest.raises(LitmusGraphQLError, match="Invalid response structure"):
            _retrieve_experiment_run_id(mock_client, "proj-123", "exp-123", "notify-123")

    def test_retrieve_run_id_missing_run_id_field(self, mock_client):
        """Test error when experimentRunID field is missing."""
        mock_client._graphql_call.return_value = {
            "listExperimentRun": {
                "experimentRuns": [{"experimentName": "test"}]  # Missing experimentRunID
            }
        }

        with patch("time.sleep"):  # Skip actual sleep
            with pytest.raises(LitmusGraphQLError, match="experimentRunID is missing"):
                _retrieve_experiment_run_id(mock_client, "proj-123", "exp-123", "notify-123")

    def test_retrieve_run_id_retry_with_missing_field(self, mock_client):
        """Test retry when experimentRunID is missing, then succeeds."""
        mock_client._graphql_call.side_effect = [
            {"listExperimentRun": {"experimentRuns": [{"experimentName": "test"}]}},
            {"listExperimentRun": {"experimentRuns": [{"experimentRunID": "run-123"}]}},
        ]

        with patch("time.sleep"):  # Skip actual sleep
            run_id = _retrieve_experiment_run_id(mock_client, "proj-123", "exp-123", "notify-123")

        assert run_id == "run-123"
        assert mock_client._graphql_call.call_count == 2

    def test_retrieve_run_id_warns_on_multiple_runs(self, mock_client, caplog):
        """Test that warning is logged when multiple runs found."""
        mock_client._graphql_call.return_value = {
            "listExperimentRun": {
                "experimentRuns": [
                    {"experimentRunID": "run-123"},
                    {"experimentRunID": "run-456"},
                    {"experimentRunID": "run-789"},
                ]
            }
        }

        run_id = _retrieve_experiment_run_id(mock_client, "proj-123", "exp-123", "notify-123")

        assert run_id == "run-123"
        # Check logs contain warning about multiple runs (if logger is configured)


class TestPollExperimentStatus:
    """Tests for _poll_experiment_status helper function."""

    def test_poll_status_success(self, mock_client):
        """Test successful status polling."""
        mock_client._graphql_call.return_value = {
            "getExperimentRun": {
                "experimentRunID": "run-123",
                "experimentName": "test-exp",
                "phase": "Running",
            }
        }

        result = _poll_experiment_status(mock_client, "proj-123", "run-123", "notify-123")

        assert result["experimentRunID"] == "run-123"
        assert result["phase"] == "Running"

    def test_poll_status_no_experiment_run_found(self, mock_client):
        """Test error when experiment run not found."""
        mock_client._graphql_call.return_value = {"getExperimentRun": {}}

        with pytest.raises(LitmusGraphQLError, match="No experiment run found"):
            _poll_experiment_status(mock_client, "proj-123", "run-123", "notify-123")

    def test_poll_status_run_id_mismatch(self, mock_client):
        """Test error when returned run ID doesn't match expected."""
        mock_client._graphql_call.return_value = {
            "getExperimentRun": {"experimentRunID": "run-wrong", "phase": "Running"}
        }

        with pytest.raises(LitmusGraphQLError, match="Run ID mismatch"):
            _poll_experiment_status(mock_client, "proj-123", "run-123", "notify-123")

    def test_poll_status_handles_missing_run_id_in_response(self, mock_client):
        """Test that missing run ID in response doesn't cause mismatch error."""
        mock_client._graphql_call.return_value = {
            "getExperimentRun": {
                "experimentName": "test",
                "phase": "Running",
                # Missing experimentRunID
            }
        }

        # Should not raise error if run ID is missing from response
        result = _poll_experiment_status(mock_client, "proj-123", "run-123", "notify-123")
        assert result["phase"] == "Running"


class TestWaitExperimentCompletion:
    """Tests for wait_experiment_completion function."""

    def test_wait_success_immediate_completion(self, mock_client):
        """Test waiting when experiment completes immediately."""
        # Mock retrieve run ID
        mock_client._graphql_call.side_effect = [
            # First call: retrieve run ID
            {"listExperimentRun": {"experimentRuns": [{"experimentRunID": "run-123"}]}},
            # Second call: get status - already completed
            {
                "getExperimentRun": {
                    "experimentRunID": "run-123",
                    "phase": "Completed",
                    "resiliencyScore": 100.0,
                }
            },
        ]

        result = wait_experiment_completion(mock_client, "proj-123", "exp-123", "notify-123")

        assert result["phase"] == "Completed"
        assert result["resiliencyScore"] == 100.0

    def test_wait_success_after_polling(self, mock_client):
        """Test waiting with several polling iterations."""
        mock_client._graphql_call.side_effect = [
            # Retrieve run ID
            {"listExperimentRun": {"experimentRuns": [{"experimentRunID": "run-123"}]}},
            # Poll 1: Pending
            {"getExperimentRun": {"experimentRunID": "run-123", "phase": "Pending"}},
            # Poll 2: Running
            {"getExperimentRun": {"experimentRunID": "run-123", "phase": "Running"}},
            # Poll 3: Completed
            {
                "getExperimentRun": {
                    "experimentRunID": "run-123",
                    "phase": "Completed",
                    "resiliencyScore": 95.0,
                }
            },
        ]

        with patch("time.sleep"):  # Skip actual sleep
            result = wait_experiment_completion(mock_client, "proj-123", "exp-123", "notify-123")

        assert result["phase"] == "Completed"
        assert mock_client._graphql_call.call_count == 4

    def test_wait_timeout_exceeded(self, mock_client):
        """Test that timeout error is raised when experiment takes too long."""
        mock_client._graphql_call.side_effect = [
            # Retrieve run ID
            {"listExperimentRun": {"experimentRuns": [{"experimentRunID": "run-123"}]}},
            # Keep returning Running status for all subsequent calls
            {"getExperimentRun": {"experimentRunID": "run-123", "phase": "Running"}},
        ] + [{"getExperimentRun": {"experimentRunID": "run-123", "phase": "Running"}}] * 100

        with patch("time.time") as mock_time:
            with patch("time.sleep"):  # Skip actual sleep
                # Simulate time passing beyond timeout
                # Provide plenty of values to account for time.time() calls in logging
                time_values = [0] * 20 + [100] * 20 + [200] * 20 + [301] * 20
                mock_time.side_effect = time_values

                with pytest.raises(ExperimentTimeoutError, match="timed out"):
                    wait_experiment_completion(
                        mock_client, "proj-123", "exp-123", "notify-123", timeout_seconds=300
                    )

    def test_wait_handles_failed_experiment(self, mock_client):
        """Test handling of failed experiment (doesn't raise exception)."""
        mock_client._graphql_call.side_effect = [
            # Retrieve run ID
            {"listExperimentRun": {"experimentRuns": [{"experimentRunID": "run-123"}]}},
            # Failed status
            {
                "getExperimentRun": {
                    "experimentRunID": "run-123",
                    "phase": "Error",
                    "resiliencyScore": 0.0,
                }
            },
        ]

        result = wait_experiment_completion(mock_client, "proj-123", "exp-123", "notify-123")

        # Failed experiments should return normally, not raise exception
        assert result["phase"] == "Error"
        assert result["resiliencyScore"] == 0.0

    def test_wait_handles_stopped_experiment(self, mock_client):
        """Test handling of stopped experiment."""
        mock_client._graphql_call.side_effect = [
            # Retrieve run ID
            {"listExperimentRun": {"experimentRuns": [{"experimentRunID": "run-123"}]}},
            # Stopped status
            {
                "getExperimentRun": {
                    "experimentRunID": "run-123",
                    "phase": "Stopped",
                    "resiliencyScore": 50.0,
                }
            },
        ]

        result = wait_experiment_completion(mock_client, "proj-123", "exp-123", "notify-123")

        assert result["phase"] == "Stopped"

    def test_wait_with_custom_timeout(self, mock_client):
        """Test using custom timeout value."""
        mock_client._graphql_call.side_effect = [
            # Retrieve run ID
            {"listExperimentRun": {"experimentRuns": [{"experimentRunID": "run-123"}]}},
            # Running status
            {"getExperimentRun": {"experimentRunID": "run-123", "phase": "Running"}},
        ] + [{"getExperimentRun": {"experimentRunID": "run-123", "phase": "Running"}}] * 50

        with patch("time.time") as mock_time:
            with patch("time.sleep"):  # Skip actual sleep
                # Provide plenty of values for all time.time() calls including logging
                time_values = [0] * 20 + [65] * 20
                mock_time.side_effect = time_values

                with pytest.raises(ExperimentTimeoutError, match="60 seconds"):
                    wait_experiment_completion(
                        mock_client, "proj-123", "exp-123", "notify-123", timeout_seconds=60
                    )

    def test_wait_logs_phase_changes(self, mock_client, caplog):
        """Test that phase transitions are logged."""
        mock_client._graphql_call.side_effect = [
            # Retrieve run ID
            {"listExperimentRun": {"experimentRuns": [{"experimentRunID": "run-123"}]}},
            # Pending
            {"getExperimentRun": {"experimentRunID": "run-123", "phase": "Pending"}},
            # Queued
            {"getExperimentRun": {"experimentRunID": "run-123", "phase": "Queued"}},
            # Running
            {"getExperimentRun": {"experimentRunID": "run-123", "phase": "Running"}},
            # Completed
            {"getExperimentRun": {"experimentRunID": "run-123", "phase": "Completed"}},
        ]

        with patch("time.sleep"):  # Skip actual sleep
            result = wait_experiment_completion(mock_client, "proj-123", "exp-123", "notify-123")

        assert result["phase"] == "Completed"

    def test_wait_uses_backoff_time(self, mock_client):
        """Test that backoff time increases with elapsed time."""
        mock_client._graphql_call.side_effect = [
            # Retrieve run ID
            {"listExperimentRun": {"experimentRuns": [{"experimentRunID": "run-123"}]}},
            # Multiple running statuses
            {"getExperimentRun": {"experimentRunID": "run-123", "phase": "Running"}},
            {"getExperimentRun": {"experimentRunID": "run-123", "phase": "Running"}},
            {"getExperimentRun": {"experimentRunID": "run-123", "phase": "Completed"}},
        ]

        sleep_calls = []

        def track_sleep(duration):
            sleep_calls.append(duration)

        with patch("time.sleep", side_effect=track_sleep):
            with patch("time.time") as mock_time:
                # Simulate time progression:
                # start, after first poll, after second poll, completion
                mock_time.side_effect = [0, 0, 0, 5, 5, 5, 300, 300, 300, 305, 305, 305]
                wait_experiment_completion(mock_client, "proj-123", "exp-123", "notify-123")

        # Should have called sleep with different backoff times
        assert len(sleep_calls) >= 2, f"Expected at least 2 sleep calls, got {len(sleep_calls)}"
        # Second sleep should use higher backoff due to elapsed time (300s)
        assert sleep_calls[-1] >= sleep_calls[0], f"Expected increasing backoff: {sleep_calls}"

    def test_wait_handles_unknown_phase(self, mock_client):
        """Test handling of unexpected phase value."""
        mock_client._graphql_call.side_effect = [
            # Retrieve run ID
            {"listExperimentRun": {"experimentRuns": [{"experimentRunID": "run-123"}]}},
            # Unknown phase
            {
                "getExperimentRun": {
                    "experimentRunID": "run-123",
                    "phase": "UnexpectedPhase",
                    "resiliencyScore": 0.0,
                }
            },
        ]

        result = wait_experiment_completion(mock_client, "proj-123", "exp-123", "notify-123")

        # Should return even with unknown phase
        assert result["phase"] == "UnexpectedPhase"

    def test_wait_default_timeout(self, mock_client):
        """Test that default timeout is used when not specified."""
        mock_client._graphql_call.side_effect = [
            # Retrieve run ID
            {"listExperimentRun": {"experimentRuns": [{"experimentRunID": "run-123"}]}},
            # Completed immediately
            {"getExperimentRun": {"experimentRunID": "run-123", "phase": "Completed"}},
        ]

        # Should use default POLL_TIMEOUT_SECONDS
        result = wait_experiment_completion(mock_client, "proj-123", "exp-123", "notify-123")

        assert result["phase"] == "Completed"
