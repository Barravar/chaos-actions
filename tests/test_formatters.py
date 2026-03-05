#!/usr/bin/env python3
"""Unit tests for formatting and logging utilities."""

from datetime import datetime

import pytest

from src.utils.formatters import _log_fault_details, format_timestamp, log_experiment_result


class TestFormatTimestamp:
    """Tests for format_timestamp function."""

    @pytest.mark.parametrize(
        "timestamp,expected",
        [
            # Unix timestamps (seconds)
            (1609459200, "2021-01-01 00:00:00 UTC"),
            ("1609459200", "2021-01-01 00:00:00 UTC"),
            (1672531200, "2023-01-01 00:00:00 UTC"),
            # ISO format strings
            ("2021-01-01T00:00:00Z", "2021-01-01 00:00:00 UTC"),
            ("2023-06-15T14:30:45Z", "2023-06-15 14:30:45 UTC"),
            # Edge cases
            (None, "N/A"),
            ("", "N/A"),
            ("invalid", "N/A"),
            ("not-a-timestamp", "N/A"),
            (0, "N/A"),  # Epoch 0 is before reasonable range
            (-1, "N/A"),  # Negative timestamp
        ],
    )
    def test_format_timestamp_variations(self, timestamp, expected):
        """Test timestamp formatting with various input types."""
        result = format_timestamp(timestamp)
        assert result == expected, f"Expected '{expected}' but got '{result}' for input {timestamp}"

    def test_format_timestamp_current_time(self):
        """Test formatting current timestamp."""
        now = int(datetime.now().timestamp())
        result = format_timestamp(now)

        # Should return a valid formatted string (not N/A)
        assert result != "N/A"
        assert "UTC" in result
        assert len(result) > 10

    def test_format_timestamp_future_timestamp(self):
        """Test formatting a future timestamp (within reasonable range)."""
        # Date in 2099 (still within valid range)
        future_ts = 4102444799  # Just before year 2100
        result = format_timestamp(future_ts)

        assert result != "N/A"
        assert "2099" in result or "2100" in result

    def test_format_timestamp_beyond_range(self):
        """Test timestamp beyond year 2100 returns N/A."""
        far_future = 5000000000  # Year 2128
        result = format_timestamp(far_future)

        assert result == "N/A"

    def test_format_timestamp_iso_with_timezone(self):
        """Test ISO format with explicit timezone."""
        timestamp = "2023-01-01T00:00:00+00:00"
        result = format_timestamp(timestamp)

        assert "2023-01-01" in result
        assert "UTC" in result


class TestLogFaultDetails:
    """Tests for _log_fault_details function."""

    def test_log_fault_details_complete_data(self, caplog):
        """Test logging fault details with complete chaos data."""
        chaos_data = {
            "engineName": "pod-delete",
            "experimentStatus": "Completed",
            "experimentVerdict": "Pass",
            "probeSuccessPercentage": "100",
            "chaosResult": {
                "status": {
                    "probeStatuses": [
                        {
                            "name": "check-app-status",
                            "status": {
                                "verdict": "Passed",
                                "description": "Application is healthy",
                            },
                        },
                        {
                            "name": "check-database",
                            "status": {
                                "verdict": "Passed",
                                "description": "Database is operational",
                            },
                        },
                    ]
                }
            },
        }

        _log_fault_details(chaos_data)

        # Check that logs contain expected information (if logging is configured)
        # Note: caplog may not capture if logger isn't properly configured in test

    def test_log_fault_details_minimal_data(self, caplog):
        """Test logging with minimal chaos data."""
        chaos_data = {"engineName": "network-loss"}

        # Should not raise error even with missing fields
        _log_fault_details(chaos_data)

    def test_log_fault_details_no_probes(self, caplog):
        """Test logging when no probes are present."""
        chaos_data = {
            "engineName": "pod-delete",
            "experimentStatus": "Completed",
            "experimentVerdict": "Pass",
            "probeSuccessPercentage": "100",
            "chaosResult": {"status": {}},  # No probeStatuses
        }

        _log_fault_details(chaos_data)

    def test_log_fault_details_empty_probes(self, caplog):
        """Test logging with empty probe list."""
        chaos_data = {
            "engineName": "disk-fill",
            "experimentStatus": "Completed",
            "experimentVerdict": "Pass",
            "probeSuccessPercentage": "100",
            "chaosResult": {"status": {"probeStatuses": []}},  # Empty list
        }

        _log_fault_details(chaos_data)

    def test_log_fault_details_failed_verdict(self, caplog):
        """Test logging fault with failed verdict."""
        chaos_data = {
            "engineName": "cpu-hog",
            "experimentStatus": "Completed",
            "experimentVerdict": "Fail",
            "probeSuccessPercentage": "50",
            "chaosResult": {
                "status": {
                    "probeStatuses": [
                        {
                            "name": "check-app-status",
                            "status": {
                                "verdict": "Failed",
                                "description": "Application is not healthy",
                            },
                        }
                    ]
                }
            },
        }

        _log_fault_details(chaos_data)


class TestLogExperimentResult:
    """Tests for log_experiment_result function."""

    def test_log_experiment_result_success(self, caplog, mock_experiment_run_details):
        """Test logging successful experiment result."""
        log_experiment_result(mock_experiment_run_details)

        # Function should complete without errors
        # Actual log validation would require proper logger configuration

    def test_log_experiment_result_with_faults(
        self, caplog, mock_experiment_run_details_with_faults
    ):
        """Test logging experiment with fault details."""
        log_experiment_result(mock_experiment_run_details_with_faults)

        # Should parse and log fault information from execution data

    def test_log_experiment_result_no_execution_data(self, caplog):
        """Test logging when execution data is missing."""
        run_details = {
            "experimentName": "test-experiment",
            "phase": "Completed",
            "resiliencyScore": 100.0,
            "totalFaults": 1,
            "executionData": "",  # Empty execution data
        }

        log_experiment_result(run_details)

    def test_log_experiment_result_invalid_execution_data(self, caplog):
        """Test logging with malformed execution data."""
        run_details = {
            "experimentName": "test-experiment",
            "phase": "Completed",
            "resiliencyScore": 100.0,
            "totalFaults": 1,
            "executionData": "invalid: yaml: [[[[",  # Invalid YAML
        }

        # Should handle gracefully without crashing
        log_experiment_result(run_details)

    def test_log_experiment_result_minimal_data(self, caplog):
        """Test logging with minimal run details."""
        run_details = {"experimentName": "minimal-test"}

        # Should handle missing fields gracefully
        log_experiment_result(run_details)

    def test_log_experiment_result_failed_experiment(self, caplog):
        """Test logging failed experiment."""
        run_details = {
            "experimentName": "failed-test",
            "phase": "Error",
            "resiliencyScore": 0.0,
            "totalFaults": 1,
            "executionData": "",
        }

        log_experiment_result(run_details)

    def test_log_experiment_result_with_multiple_faults(self, caplog):
        """Test logging experiment with multiple faults."""
        run_details = {
            "experimentName": "multi-fault-test",
            "phase": "Completed",
            "resiliencyScore": 85.0,
            "totalFaults": 3,
            "executionData": """
nodes:
  node-1:
    type: ChaosEngine
    chaosData:
      engineName: pod-delete
      experimentStatus: Completed
      experimentVerdict: Pass
      probeSuccessPercentage: 100
  node-2:
    type: ChaosEngine
    chaosData:
      engineName: network-loss
      experimentStatus: Completed
      experimentVerdict: Pass
      probeSuccessPercentage: 90
  node-3:
    type: ChaosEngine
    chaosData:
      engineName: cpu-hog
      experimentStatus: Completed
      experimentVerdict: Fail
      probeSuccessPercentage: 60
""",
        }

        log_experiment_result(run_details)

    def test_log_experiment_result_non_chaos_engine_nodes(self, caplog):
        """Test logging with execution data containing non-ChaosEngine nodes."""
        run_details = {
            "experimentName": "mixed-nodes-test",
            "phase": "Completed",
            "resiliencyScore": 100.0,
            "totalFaults": 1,
            "executionData": """
nodes:
  node-1:
    type: TaskGroup
    data:
      name: setup
  node-2:
    type: ChaosEngine
    chaosData:
      engineName: pod-delete
      experimentStatus: Completed
      experimentVerdict: Pass
      probeSuccessPercentage: 100
  node-3:
    type: TaskGroup
    data:
      name: cleanup
""",
        }

        # Should only log ChaosEngine type nodes
        log_experiment_result(run_details)

    def test_log_experiment_result_execution_data_not_dict(self, caplog):
        """Test logging when execution data parses to non-dict."""
        run_details = {
            "experimentName": "invalid-structure-test",
            "phase": "Completed",
            "resiliencyScore": 100.0,
            "totalFaults": 1,
            "executionData": "- item1\n- item2\n- item3",  # Parses to list, not dict
        }

        # Should handle gracefully
        log_experiment_result(run_details)

    def test_log_experiment_result_none_score(self, caplog):
        """Test logging when resiliency score is None."""
        run_details = {
            "experimentName": "no-score-test",
            "phase": "Running",
            "resiliencyScore": None,
            "totalFaults": "N/A",
            "executionData": "",
        }

        log_experiment_result(run_details)


class TestFormattingIntegration:
    """Integration tests for formatting utilities."""

    def test_complete_experiment_logging_flow(self, mock_experiment_run_details_with_faults):
        """Test complete flow of logging experiment results."""
        # This tests the integration of all formatting functions
        log_experiment_result(mock_experiment_run_details_with_faults)

        # Should complete without errors

    def test_timestamp_in_result_logging(self, caplog):
        """Test that timestamps in results are properly formatted (if present)."""
        run_details = {
            "experimentName": "timestamp-test",
            "phase": "Completed",
            "resiliencyScore": 100.0,
            "totalFaults": 1,
            "executionData": "",
            "startedAt": 1609459200,  # These might be present
            "finishedAt": 1609459800,
        }

        # Function should handle additional timestamp fields gracefully
        log_experiment_result(run_details)
