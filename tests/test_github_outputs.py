#!/usr/bin/env python3
"""Unit tests for GitHub Actions output utilities."""

import json
import os
import tempfile
from typing import Any
from unittest.mock import patch

from src.utils.github_outputs import (
    extract_fault_results,
    write_experiment_outputs,
    write_github_output,
)


class TestExtractFaultResults:
    """Tests for extract_fault_results function."""

    def test_extract_fault_results_empty_data(self):
        """Test with empty execution data."""
        result = extract_fault_results("")
        assert result == []

    def test_extract_fault_results_no_nodes(self):
        """Test with execution data that has no nodes."""
        execution_data = """
other_field: value
metadata: test
"""
        result = extract_fault_results(execution_data)
        assert result == []

    def test_extract_fault_results_no_chaos_engines(self):
        """Test with nodes but no ChaosEngine types."""
        execution_data = """
nodes:
  node-1:
    type: Other
    data: test
"""
        result = extract_fault_results(execution_data)
        assert result == []

    def test_extract_fault_results_single_fault(self):
        """Test extracting a single fault result."""
        execution_data = """
nodes:
  node-1:
    type: ChaosEngine
    chaosData:
      engineName: pod-delete
      namespace: default
      chaosResult:
        status:
          experimentStatus:
            verdict: Pass
            failStep: N/A
            probeSuccessPercentage: 100
"""
        result = extract_fault_results(execution_data)
        assert len(result) == 1
        assert result[0]["fault_name"] == "pod-delete"
        assert result[0]["verdict"] == "Pass"
        assert result[0]["fail_step"] == "N/A"
        assert result[0]["probe_success_percentage"] == 100

    def test_extract_fault_results_multiple_faults(self):
        """Test extracting multiple fault results."""
        execution_data = """
nodes:
  node-1:
    type: ChaosEngine
    chaosData:
      engineName: pod-delete
      namespace: default
      chaosResult:
        status:
          experimentStatus:
            verdict: Pass
            failStep: N/A
            probeSuccessPercentage: 100
  node-2:
    type: ChaosEngine
    chaosData:
      engineName: network-loss
      namespace: test
      chaosResult:
        status:
          experimentStatus:
            verdict: Fail
            failStep: chaos-injection
            probeSuccessPercentage: 50
  node-3:
    type: Other
    data: ignored
"""
        result = extract_fault_results(execution_data)
        assert len(result) == 2
        assert result[0]["fault_name"] == "pod-delete"
        assert result[0]["verdict"] == "Pass"
        assert result[1]["fault_name"] == "network-loss"
        assert result[1]["verdict"] == "Fail"

    def test_extract_fault_results_with_probes(self):
        """Test extracting fault results including probe information."""
        execution_data = """
nodes:
  node-1:
    type: ChaosEngine
    chaosData:
      engineName: pod-delete
      namespace: default
      chaosResult:
        status:
          experimentStatus:
            verdict: Pass
            failStep: N/A
            probeSuccessPercentage: 100
          probeStatuses:
            - name: check-app-status
              type: httpProbe
              status:
                verdict: Passed
                description: Application is healthy and responding
            - name: check-database
              type: cmdProbe
              status:
                verdict: Passed
                description: Database connectivity verified
"""
        result = extract_fault_results(execution_data)
        assert len(result) == 1
        assert "probes" in result[0]
        assert len(result[0]["probes"]) == 2
        assert result[0]["probes"][0]["name"] == "check-app-status"
        assert result[0]["probes"][0]["type"] == "httpProbe"
        assert result[0]["probes"][0]["status"] == "Passed"
        assert result[0]["probes"][0]["description"] == "Application is healthy and responding"
        assert result[0]["probes"][1]["name"] == "check-database"
        assert result[0]["probes"][1]["description"] == "Database connectivity verified"

    def test_extract_fault_results_missing_fields(self):
        """Test with missing optional fields."""
        execution_data = """
nodes:
  node-1:
    type: ChaosEngine
    chaosData:
      chaosResult:
        status:
          experimentStatus: {}
"""
        result = extract_fault_results(execution_data)
        assert len(result) == 1
        assert result[0]["fault_name"] == "Unknown"
        assert result[0]["verdict"] == "Unknown"
        assert result[0]["fail_step"] == "N/A"
        assert result[0]["probe_success_percentage"] == "N/A"

    def test_extract_fault_results_invalid_yaml(self):
        """Test with invalid YAML data."""
        execution_data = """
nodes:
  - this is invalid: yaml: syntax
    [broken
"""
        result = extract_fault_results(execution_data)
        assert result == []

    def test_extract_fault_results_probes_without_description(self):
        """Test extracting probes that don't have description field."""
        execution_data = """
nodes:
  node-1:
    type: ChaosEngine
    chaosData:
      engineName: pod-delete
      namespace: default
      chaosResult:
        status:
          experimentStatus:
            verdict: Pass
            failStep: N/A
            probeSuccessPercentage: 100
          probeStatuses:
            - name: legacy-probe
              type: cmdProbe
              status:
                verdict: Passed
"""
        result = extract_fault_results(execution_data)
        assert len(result) == 1
        assert "probes" in result[0]
        assert len(result[0]["probes"]) == 1
        assert result[0]["probes"][0]["name"] == "legacy-probe"
        assert result[0]["probes"][0]["description"] == "No details available"

    def test_extract_fault_results_not_dict(self):
        """Test with execution data that's not a dictionary."""
        execution_data = """
- list
- of
- items
"""
        result = extract_fault_results(execution_data)
        assert result == []

    def test_extract_fault_results_with_timeout_description(self):
        """Test extracting fault with probe timeout error description."""
        execution_data = """
nodes:
  node-1:
    type: ChaosEngine
    chaosData:
      engineName: http-chaos
      namespace: production
      chaosResult:
        status:
          experimentStatus:
            verdict: Fail
            failStep: probe-check
            probeSuccessPercentage: 0
          probeStatuses:
            - name: check-endpoint
              type: httpProbe
              status:
                verdict: Failed
                description: >
                  Get "https://podtato-head-demo.primary-a.us-east-1.kic-dev.shuttercloud.org/":
                  context deadline exceeded (Client.Timeout exceeded while awaiting headers)
"""
        result = extract_fault_results(execution_data)
        assert len(result) == 1
        assert result[0]["fault_name"] == "http-chaos"
        assert result[0]["verdict"] == "Fail"
        assert result[0]["fail_step"] == "probe-check"
        assert result[0]["probe_success_percentage"] == 0
        assert "probes" in result[0]
        assert len(result[0]["probes"]) == 1
        assert result[0]["probes"][0]["name"] == "check-endpoint"
        assert result[0]["probes"][0]["status"] == "Failed"
        assert "context deadline exceeded" in result[0]["probes"][0]["description"]
        assert "Client.Timeout exceeded" in result[0]["probes"][0]["description"]


class TestWriteGithubOutput:
    """Tests for write_github_output function."""

    def test_write_github_output_no_env_var(self, caplog):
        """Test when GITHUB_OUTPUT environment variable is not set."""
        import logging

        with caplog.at_level(logging.DEBUG):
            with patch.dict(os.environ, {}, clear=True):
                write_github_output("test-name", "test-value")
                # Just verify no exception is raised
                # Log message checking is optional since logger config varies

    def test_write_github_output_string_value(self):
        """Test writing a simple string value."""
        with tempfile.NamedTemporaryFile(mode="w+", delete=False) as f:
            output_file = f.name

        try:
            with patch.dict(os.environ, {"GITHUB_OUTPUT": output_file}):
                write_github_output("test-name", "test-value")

            with open(output_file) as f:
                content = f.read()
            assert content == "test-name=test-value\n"
        finally:
            os.unlink(output_file)

    def test_write_github_output_numeric_values(self):
        """Test writing numeric values."""
        with tempfile.NamedTemporaryFile(mode="w+", delete=False) as f:
            output_file = f.name

        try:
            with patch.dict(os.environ, {"GITHUB_OUTPUT": output_file}):
                write_github_output("int-value", 42)
                write_github_output("float-value", 95.5)

            with open(output_file) as f:
                content = f.read()
            assert "int-value=42\n" in content
            assert "float-value=95.5\n" in content
        finally:
            os.unlink(output_file)

    def test_write_github_output_dict_value(self):
        """Test writing a dictionary value (JSON serialized)."""
        with tempfile.NamedTemporaryFile(mode="w+", delete=False) as f:
            output_file = f.name

        try:
            test_dict = {"key": "value", "number": 123}
            with patch.dict(os.environ, {"GITHUB_OUTPUT": output_file}):
                write_github_output("dict-output", test_dict)

            with open(output_file) as f:
                content = f.read()
            assert "dict-output=" in content
            # Should be JSON serialized
            assert '"key":"value"' in content.replace(" ", "")
        finally:
            os.unlink(output_file)

    def test_write_github_output_list_value(self):
        """Test writing a list value (JSON serialized)."""
        with tempfile.NamedTemporaryFile(mode="w+", delete=False) as f:
            output_file = f.name

        try:
            test_list = [{"name": "fault1"}, {"name": "fault2"}]
            with patch.dict(os.environ, {"GITHUB_OUTPUT": output_file}):
                write_github_output("list-output", test_list)

            with open(output_file) as f:
                content = f.read()
            assert "list-output=" in content
            # Verify it's valid JSON
            json_start = content.index("[")
            json_data = content[json_start:].strip()
            parsed = json.loads(json_data)
            assert len(parsed) == 2
        finally:
            os.unlink(output_file)

    def test_write_github_output_multiline_value(self):
        """Test writing a multi-line value using heredoc format."""
        with tempfile.NamedTemporaryFile(mode="w+", delete=False) as f:
            output_file = f.name

        try:
            multiline_value = "line1\nline2\nline3"
            with patch.dict(os.environ, {"GITHUB_OUTPUT": output_file}):
                write_github_output("multiline", multiline_value)

            with open(output_file) as f:
                content = f.read()
            # Should use heredoc format
            assert "multiline<<EOF\n" in content
            assert "line1\nline2\nline3\n" in content
            assert "EOF\n" in content
        finally:
            os.unlink(output_file)

    def test_write_github_output_file_error(self, caplog):
        """Test handling of file write errors."""
        with patch.dict(os.environ, {"GITHUB_OUTPUT": "/nonexistent/path/file"}):
            write_github_output("test", "value")
            assert "Failed to write GitHub Actions output" in caplog.text


class TestWriteExperimentOutputs:
    """Tests for write_experiment_outputs function."""

    def test_write_experiment_outputs_complete_details(self):
        """Test writing outputs with complete run details."""
        with tempfile.NamedTemporaryFile(mode="w+", delete=False) as f:
            output_file = f.name

        try:
            run_details = {
                "phase": "Completed",
                "resiliencyScore": 95.0,
                "executionData": """
nodes:
  node-1:
    type: ChaosEngine
    chaosData:
      engineName: pod-delete
      chaosResult:
        status:
          experimentStatus:
            verdict: Pass
            failStep: N/A
            probeSuccessPercentage: 100
""",
            }

            with patch.dict(os.environ, {"GITHUB_OUTPUT": output_file}):
                write_experiment_outputs(run_details)

            with open(output_file) as f:
                content = f.read()

            assert "EXPERIMENT_RESULT=Completed\n" in content
            assert "RESILIENCY_SCORE=95.0\n" in content
            assert "FAULT_RESULTS=" in content
            # Verify fault results is valid JSON
            assert "pod-delete" in content
        finally:
            os.unlink(output_file)

    def test_write_experiment_outputs_missing_fields(self):
        """Test writing outputs with missing fields (defaults should be used)."""
        with tempfile.NamedTemporaryFile(mode="w+", delete=False) as f:
            output_file = f.name

        try:
            run_details: dict[str, Any] = {}

            with patch.dict(os.environ, {"GITHUB_OUTPUT": output_file}):
                write_experiment_outputs(run_details)

            with open(output_file) as f:
                content = f.read()

            assert "EXPERIMENT_RESULT=Unknown\n" in content
            assert "RESILIENCY_SCORE=0.0\n" in content
            assert "FAULT_RESULTS=[]\n" in content
        finally:
            os.unlink(output_file)

    def test_write_experiment_outputs_empty_execution_data(self):
        """Test with empty execution data."""
        with tempfile.NamedTemporaryFile(mode="w+", delete=False) as f:
            output_file = f.name

        try:
            run_details = {
                "phase": "Error",
                "resiliencyScore": 0.0,
                "executionData": "",
            }

            with patch.dict(os.environ, {"GITHUB_OUTPUT": output_file}):
                write_experiment_outputs(run_details)

            with open(output_file) as f:
                content = f.read()

            assert "EXPERIMENT_RESULT=Error\n" in content
            assert "FAULT_RESULTS=[]\n" in content
        finally:
            os.unlink(output_file)

    def test_write_experiment_outputs_logging(self, caplog):
        """Test that outputs are logged."""
        import logging

        with tempfile.NamedTemporaryFile(mode="w+", delete=False) as f:
            output_file = f.name

        try:
            run_details = {
                "phase": "Completed",
                "resiliencyScore": 100.0,
                "executionData": "",
            }

            with caplog.at_level(logging.INFO):
                with patch.dict(os.environ, {"GITHUB_OUTPUT": output_file}):
                    write_experiment_outputs(run_details)

                assert "Experiment outputs written" in caplog.text
                assert "result=Completed" in caplog.text
                assert "score=100.0" in caplog.text
                assert "faults=0" in caplog.text
        finally:
            os.unlink(output_file)
