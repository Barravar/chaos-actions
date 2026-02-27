#!/usr/bin/env python3
"""Unit tests for main.py functions."""

import pytest
from unittest.mock import Mock, patch, MagicMock
import json
import yaml

from src.main import (
    get_project_id,
    get_environment_id,
    get_infrastructure_id,
    get_chaos_experiment,
    create_chaos_experiment,
    run_chaos_experiment,
    _generate_experiment_id,
    _prepare_manifest_metadata,
    _serialize_manifest_to_json,
)
from src.exceptions import LitmusRestError, LitmusGraphQLError
from src.config import LitmusConfig


@pytest.fixture
def mock_client():
    """Create a mock LitmusClient."""
    client = Mock()
    client.config = LitmusConfig(
        litmus_url="https://litmus.example.com",
        litmus_username="test",
        litmus_password="test",
        litmus_project="test-project",
        litmus_environment="test-env",
        litmus_infra="test-infra",
        experiment_manifest="test.yaml"
    )
    return client


@pytest.fixture
def sample_manifest():
    """Sample experiment manifest."""
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


class TestGetProjectId:
    """Tests for get_project_id function."""
    
    def test_get_project_id_success(self, mock_client):
        """Test successful project ID retrieval."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "data": {
                "projects": [
                    {"name": "test-project", "projectID": "proj-123"},
                    {"name": "other-project", "projectID": "proj-456"}
                ]
            }
        }
        mock_client._rest_call.return_value = mock_response
        
        project_id = get_project_id(mock_client, "test-project")
        
        assert project_id == "proj-123"
        mock_client._rest_call.assert_called_once_with(
            method="GET",
            path="/list_projects"
        )
    
    def test_get_project_id_not_found(self, mock_client):
        """Test project not found error."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "data": {
                "projects": [
                    {"name": "other-project", "projectID": "proj-456"}
                ]
            }
        }
        mock_client._rest_call.return_value = mock_response
        
        with pytest.raises(LitmusRestError, match="Project.*not found"):
            get_project_id(mock_client, "missing-project")
    
    def test_get_project_id_invalid_response(self, mock_client):
        """Test handling of invalid response structure."""
        mock_response = Mock()
        mock_response.json.return_value = {"invalid": "structure"}
        mock_client._rest_call.return_value = mock_response
        
        with pytest.raises(LitmusRestError, match="Invalid response structure"):
            get_project_id(mock_client, "test-project")
    
    def test_get_project_id_missing_project_id(self, mock_client):
        """Test handling of projects without projectID field."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "data": {
                "projects": [
                    {"name": "test-project"}  # Missing projectID
                ]
            }
        }
        mock_client._rest_call.return_value = mock_response
        
        with pytest.raises(LitmusRestError, match="not found"):
            get_project_id(mock_client, "test-project")


class TestGetEnvironmentId:
    """Tests for get_environment_id function."""
    
    def test_get_environment_id_success(self, mock_client):
        """Test successful environment ID retrieval."""
        mock_client._graphql_call.return_value = {
            "listEnvironments": {
                "environments": [
                    {"environmentID": "env-123", "name": "test-env"}
                ]
            }
        }
        
        env_id = get_environment_id(mock_client, "test-env", "proj-123")
        
        assert env_id == "env-123"
    
    def test_get_environment_id_not_found(self, mock_client):
        """Test environment not found error."""
        mock_client._graphql_call.return_value = {
            "listEnvironments": {
                "environments": []
            }
        }
        
        with pytest.raises(LitmusGraphQLError, match="Environment.*not found"):
            get_environment_id(mock_client, "missing-env", "proj-123")
    
    def test_get_environment_id_multiple_found(self, mock_client):
        """Test error when multiple environments match."""
        mock_client._graphql_call.return_value = {
            "listEnvironments": {
                "environments": [
                    {"environmentID": "env-123", "name": "test-env"},
                    {"environmentID": "env-456", "name": "test-env"}
                ]
            }
        }
        
        with pytest.raises(LitmusGraphQLError, match="Multiple environments found"):
            get_environment_id(mock_client, "test-env", "proj-123")
    
    def test_get_environment_id_missing_id_field(self, mock_client):
        """Test handling when environmentID field is missing."""
        mock_client._graphql_call.return_value = {
            "listEnvironments": {
                "environments": [
                    {"name": "test-env"}  # Missing environmentID
                ]
            }
        }
        
        with pytest.raises(LitmusGraphQLError, match="Could not get environment ID"):
            get_environment_id(mock_client, "test-env", "proj-123")


class TestGetInfrastructureId:
    """Tests for get_infrastructure_id function."""
    
    def test_get_infrastructure_id_success(self, mock_client):
        """Test successful infrastructure ID retrieval."""
        mock_client._graphql_call.return_value = {
            "listInfras": {
                "infras": [
                    {
                        "infraID": "infra-123",
                        "name": "test-infra",
                        "isActive": True,
                        "isInfraConfirmed": True
                    }
                ]
            }
        }
        
        infra_id = get_infrastructure_id(mock_client, "proj-123", "env-123", "test-infra")
        
        assert infra_id == "infra-123"
    
    def test_get_infrastructure_id_not_found(self, mock_client):
        """Test error when infrastructure is not found."""
        mock_client._graphql_call.return_value = {
            "listInfras": {
                "infras": []
            }
        }
        
        with pytest.raises(LitmusGraphQLError, match="not found"):
            get_infrastructure_id(mock_client, "proj-123", "env-123", "missing-infra")
    
    def test_get_infrastructure_id_not_active(self, mock_client):
        """Test error when infrastructure is not active."""
        mock_client._graphql_call.return_value = {
            "listInfras": {
                "infras": [
                    {
                        "infraID": "infra-123",
                        "name": "test-infra",
                        "isActive": False,
                        "isInfraConfirmed": True
                    }
                ]
            }
        }
        
        with pytest.raises(LitmusGraphQLError, match="not active"):
            get_infrastructure_id(mock_client, "proj-123", "env-123", "test-infra")
    
    def test_get_infrastructure_id_not_confirmed(self, mock_client):
        """Test error when infrastructure is not confirmed."""
        mock_client._graphql_call.return_value = {
            "listInfras": {
                "infras": [
                    {
                        "infraID": "infra-123",
                        "name": "test-infra",
                        "isActive": True,
                        "isInfraConfirmed": False
                    }
                ]
            }
        }
        
        with pytest.raises(LitmusGraphQLError, match="not confirmed"):
            get_infrastructure_id(mock_client, "proj-123", "env-123", "test-infra")
    
    def test_get_infrastructure_id_multiple_found(self, mock_client):
        """Test error when multiple infrastructures match."""
        mock_client._graphql_call.return_value = {
            "listInfras": {
                "infras": [
                    {
                        "infraID": "infra-123",
                        "name": "test-infra",
                        "isActive": True,
                        "isInfraConfirmed": True
                    },
                    {
                        "infraID": "infra-456",
                        "name": "test-infra",
                        "isActive": True,
                        "isInfraConfirmed": True
                    }
                ]
            }
        }
        
        with pytest.raises(LitmusGraphQLError, match="Multiple"):
            get_infrastructure_id(mock_client, "proj-123", "env-123", "test-infra")




class TestGetChaosExperiment:
    """Tests for get_chaos_experiment function."""
    
    def test_get_chaos_experiment_success(self, mock_client):
        """Test successful experiment retrieval."""
        mock_client._graphql_call.return_value = {
            "listExperiment": {
                "experiments": [
                    {
                        "experimentID": "exp-123",
                        "name": "test-experiment"
                    }
                ]
            }
        }
        
        exp_id = get_chaos_experiment(mock_client, "proj-123", "env-123", "test-experiment")
        
        assert exp_id == "exp-123"
    
    def test_get_chaos_experiment_not_found(self, mock_client):
        """Test error when experiment is not found."""
        mock_client._graphql_call.return_value = {
            "listExperiment": {
                "experiments": []
            }
        }
        
        with pytest.raises(LitmusGraphQLError, match="not found"):
            get_chaos_experiment(mock_client, "proj-123", "env-123", "missing-experiment")
    
    def test_get_chaos_experiment_missing_id(self, mock_client):
        """Test error when experimentID is missing."""
        mock_client._graphql_call.return_value = {
            "listExperiment": {
                "experiments": [
                    {"name": "test-experiment"}  # Missing experimentID
                ]
            }
        }
        
        with pytest.raises(LitmusGraphQLError, match="Could not get experiment ID"):
            get_chaos_experiment(mock_client, "proj-123", "env-123", "test-experiment")


class TestGenerateExperimentId:
    """Tests for _generate_experiment_id helper function."""
    
    def test_generate_experiment_id_format(self):
        """Test that generated ID has correct format."""
        exp_id = _generate_experiment_id()
        assert len(exp_id) == 8
        assert all(c in '0123456789abcdef' for c in exp_id)
    
    def test_generate_experiment_id_unique(self):
        """Test that generated IDs are unique."""
        id1 = _generate_experiment_id()
        id2 = _generate_experiment_id()
        assert id1 != id2


class TestPrepareManifestMetadata:
    """Tests for _prepare_manifest_metadata helper function."""
    
    def test_prepare_manifest_with_name(self):
        """Test preparing manifest with name field."""
        manifest = """
apiVersion: litmuschaos.io/v1alpha1
kind: Workflow
metadata:
  name: pod-delete
  annotations:
    description: "Test experiment"
spec:
  experiments:
    - name: pod-delete
"""
        manifest_dict, exp_name, exp_desc = _prepare_manifest_metadata(manifest, "abc123")
        
        assert exp_name == "pod-delete-abc123"
        assert exp_desc == "Test experiment"
        assert manifest_dict["metadata"]["name"] == "pod-delete-abc123"
        assert "generateName" not in manifest_dict["metadata"]
    
    def test_prepare_manifest_with_generate_name(self):
        """Test preparing manifest with generateName field."""
        manifest = """
apiVersion: litmuschaos.io/v1alpha1
kind: Workflow
metadata:
  generateName: pod-delete-
  annotations:
    description: "Test"
spec:
  experiments:
    - name: pod-delete
"""
        manifest_dict, exp_name, exp_desc = _prepare_manifest_metadata(manifest, "xyz789")
        
        assert exp_name == "pod-delete-xyz789"
        assert exp_desc == "Test"
        assert manifest_dict["metadata"]["name"] == "pod-delete-xyz789"
        assert "generateName" not in manifest_dict["metadata"]
    
    def test_prepare_manifest_no_description(self):
        """Test preparing manifest without description annotation."""
        manifest = """
apiVersion: litmuschaos.io/v1alpha1
kind: Workflow
metadata:
  name: test-exp
spec:
  experiments:
    - name: test
"""
        manifest_dict, exp_name, exp_desc = _prepare_manifest_metadata(manifest, "test123")
        
        assert exp_name == "test-exp-test123"
        assert exp_desc == ""
    
    def test_prepare_manifest_invalid_yaml(self):
        """Test error with invalid YAML."""
        invalid_manifest = "invalid: yaml: content: ["
        
        with pytest.raises(ValueError, match="Invalid YAML"):
            _prepare_manifest_metadata(invalid_manifest, "test123")


class TestSerializeManifestToJson:
    """Tests for _serialize_manifest_to_json helper function."""
    
    def test_serialize_manifest_success(self):
        """Test successful manifest serialization."""
        manifest_dict = {
            "apiVersion": "v1",
            "kind": "Workflow",
            "metadata": {"name": "test"}
        }
        
        result = _serialize_manifest_to_json(manifest_dict)
        
        assert isinstance(result, str)
        assert '"apiVersion":"v1"' in result  # Compact format
        assert ' ' not in result.replace('"', '')  # No extra spaces
    
    def test_serialize_manifest_invalid_type(self):
        """Test error with non-serializable content."""
        # Create a dict with a non-serializable object
        manifest_dict = {
            "apiVersion": "v1",
            "invalid": object()  # object() is not JSON serializable
        }
        
        with pytest.raises(ValueError, match="Error converting manifest to JSON"):
            _serialize_manifest_to_json(manifest_dict)


class TestCreateChaosExperiment:
    """Tests for create_chaos_experiment function."""
    
    def test_create_chaos_experiment_success(self, mock_client, sample_manifest, tmp_path):
        """Test successful experiment creation."""
        manifest_file = tmp_path / "test.yaml"
        manifest_file.write_text(sample_manifest)
        
        mock_client._graphql_call.return_value = {
            "saveChaosExperiment": "success"
        }
        
        result = create_chaos_experiment(
            mock_client,
            "proj-123",
            "infra-123",
            str(manifest_file)
        )
        
        assert "experimentID" in result
        assert "experimentName" in result
        assert "pod-delete" in result["experimentName"]
    
    def test_create_chaos_experiment_with_generate_name(self, mock_client, tmp_path):
        """Test experiment creation with generateName instead of name."""
        manifest_with_generate = """
apiVersion: litmuschaos.io/v1alpha1
kind: Workflow
metadata:
  generateName: pod-delete-
  annotations:
    description: "Test"
spec:
  experiments:
    - name: pod-delete
"""
        manifest_file = tmp_path / "test.yaml"
        manifest_file.write_text(manifest_with_generate)
        
        mock_client._graphql_call.return_value = {
            "saveChaosExperiment": "success"
        }
        
        result = create_chaos_experiment(
            mock_client,
            "proj-123",
            "infra-123",
            str(manifest_file)
        )
        
        assert "experimentName" in result
        assert result["experimentName"].startswith("pod-delete-")
    
    def test_create_chaos_experiment_empty_manifest(self, mock_client):
        """Test error with empty manifest."""
        with pytest.raises(ValueError, match="missing or empty"):
            create_chaos_experiment(mock_client, "proj-123", "infra-123", "")
    
    def test_create_chaos_experiment_missing_name(self, mock_client, tmp_path):
        """Test error when manifest has no name or generateName."""
        manifest_no_name = """
apiVersion: litmuschaos.io/v1alpha1
kind: Workflow
metadata:
  annotations:
    description: "Test"
spec:
  experiments:
    - name: pod-delete
"""
        manifest_file = tmp_path / "test.yaml"
        manifest_file.write_text(manifest_no_name)
        
        with pytest.raises(ValueError, match="must contain 'name' or 'generateName'"):
            create_chaos_experiment(mock_client, "proj-123", "infra-123", str(manifest_file))


class TestRunChaosExperiment:
    """Tests for run_chaos_experiment function."""
    
    def test_run_chaos_experiment_success(self, mock_client):
        """Test successful experiment run."""
        mock_client._graphql_call.return_value = {
            "runExperiment": {
                "notifyID": "notify-123"
            }
        }
        
        result = run_chaos_experiment(mock_client, "proj-123", "exp-123", "test-experiment")
        
        assert result == {"runExperiment": {"notifyID": "notify-123"}}
        mock_client._graphql_call.assert_called_once()
    
    def test_run_chaos_experiment_api_error(self, mock_client):
        """Test handling of API errors during run."""
        from src.exceptions import LitmusGraphQLError
        mock_client._graphql_call.side_effect = LitmusGraphQLError("API Error")
        
        with pytest.raises(LitmusGraphQLError):
            run_chaos_experiment(mock_client, "proj-123", "exp-123", "test-experiment")


class TestErrorHandling:
    """Tests for error handling patterns."""
    
    def test_graphql_error_propagation(self, mock_client):
        """Test that GraphQL errors are properly propagated."""
        from src.exceptions import LitmusGraphQLError
        mock_client._graphql_call.side_effect = LitmusGraphQLError("Test error")
        
        with pytest.raises(LitmusGraphQLError, match="Test error"):
            get_environment_id(mock_client, "test-env", "proj-123")
    
    def test_rest_error_propagation(self, mock_client):
        """Test that REST errors are properly propagated."""
        from src.exceptions import LitmusRestError
        mock_client._rest_call.side_effect = LitmusRestError("Test error")
        
        with pytest.raises(LitmusRestError, match="Test error"):
            get_project_id(mock_client, "test-project")
