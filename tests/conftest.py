#!/usr/bin/env python3
"""Shared test fixtures for chaos-actions tests."""

from unittest.mock import Mock

import pytest

from src.client import LitmusClient
from src.config import LitmusConfig, RetryConfig


@pytest.fixture
def mock_config():
    """Create a mock LitmusConfig for testing."""
    return LitmusConfig(
        litmus_url="https://litmus.example.com",
        litmus_username="test_user",
        litmus_password="test_password",
        litmus_project="test-project",
        litmus_environment="test-env",
        litmus_infra="test-infra",
        experiment_manifest="test.yaml",
        experiment_name="",
        run_experiment=True,
    )


@pytest.fixture
def mock_retry_config():
    """Create a mock RetryConfig for testing."""
    return RetryConfig(max_retries=3, backoff_factor=0.1, request_timeout=10, graphql_timeout=15)


@pytest.fixture
def mock_logger():
    """Create a mock logger for testing."""
    logger = Mock()
    logger.info = Mock()
    logger.debug = Mock()
    logger.warning = Mock()
    logger.error = Mock()
    logger.isEnabledFor = Mock(return_value=False)
    return logger


@pytest.fixture
def mock_client(mock_config, mock_logger, mock_retry_config):
    """Create a mock LitmusClient for testing."""
    client = Mock(spec=LitmusClient)
    client.config = mock_config
    client.logger = mock_logger
    client.retry_config = mock_retry_config
    client.authenticated = False
    client._rest_call = Mock()
    client._graphql_call = Mock()
    client.authenticate = Mock()
    return client


@pytest.fixture
def authenticated_client(mock_client):
    """Create an authenticated mock client."""
    mock_client.authenticated = True
    return mock_client


@pytest.fixture
def sample_manifest():
    """Sample experiment manifest YAML."""
    return """
apiVersion: litmuschaos.io/v1alpha1
kind: Workflow
metadata:
  name: pod-delete
  annotations:
    description: "Test pod deletion"
spec:
  experiments:
    - name: pod-delete
"""


@pytest.fixture
def sample_manifest_with_generate_name():
    """Sample experiment manifest with generateName."""
    return """
apiVersion: litmuschaos.io/v1alpha1
kind: Workflow
metadata:
  generateName: pod-delete-
  annotations:
    description: "Test pod deletion"
spec:
  experiments:
    - name: pod-delete
"""


@pytest.fixture
def temp_manifest_file(tmp_path, sample_manifest):
    """Create a temporary manifest file for testing."""
    manifest_file = tmp_path / "test-manifest.yaml"
    manifest_file.write_text(sample_manifest)
    return str(manifest_file)


@pytest.fixture
def mock_project_response():
    """Mock response for list_projects API call."""
    return {
        "data": {
            "projects": [
                {"name": "test-project", "projectID": "proj-123"},
                {"name": "other-project", "projectID": "proj-456"},
            ]
        }
    }


@pytest.fixture
def mock_environment_response():
    """Mock response for listEnvironments GraphQL call."""
    return {
        "listEnvironments": {"environments": [{"environmentID": "env-123", "name": "test-env"}]}
    }


@pytest.fixture
def mock_infrastructure_response():
    """Mock response for listInfras GraphQL call."""
    return {
        "listInfras": {
            "infras": [
                {
                    "infraID": "infra-123",
                    "name": "test-infra",
                    "isActive": True,
                    "isInfraConfirmed": True,
                }
            ]
        }
    }


@pytest.fixture
def mock_experiment_response():
    """Mock response for listExperiment GraphQL call."""
    return {
        "listExperiment": {"experiments": [{"experimentID": "exp-123", "name": "test-experiment"}]}
    }


@pytest.fixture
def mock_experiment_run_response():
    """Mock response for listExperimentRun GraphQL call."""
    return {
        "listExperimentRun": {
            "experimentRuns": [
                {
                    "experimentRunID": "run-123",
                    "experimentName": "test-experiment",
                    "phase": "Running",
                }
            ]
        }
    }


@pytest.fixture
def mock_experiment_run_details():
    """Mock experiment run details."""
    return {
        "experimentRunID": "run-123",
        "experimentName": "test-experiment",
        "phase": "Completed",
        "resiliencyScore": 100.0,
        "totalFaults": 1,
        "executionData": "",
    }


@pytest.fixture
def mock_experiment_run_details_with_faults():
    """Mock experiment run details with fault information."""
    return {
        "experimentRunID": "run-123",
        "experimentName": "test-experiment",
        "phase": "Completed",
        "resiliencyScore": 100.0,
        "totalFaults": 1,
        "executionData": """
nodes:
  node-1:
    type: ChaosEngine
    chaosData:
      engineName: pod-delete
      experimentStatus: Completed
      experimentVerdict: Pass
      probeSuccessPercentage: 100
      chaosResult:
        status:
          probeStatuses:
            - name: check-app-status
              status: Passed
""",
    }
