"""Integration tests for main.py entry point."""

from unittest.mock import MagicMock, patch

import pytest

from src.config import LitmusConfig
from src.exceptions import LitmusAuthenticationError
from src.main import main


class TestMainFunction:
    """Test suite for main() function."""

    def test_main_with_provided_config(self, mocker):
        """Test main function with config provided programmatically."""
        # Arrange
        config = LitmusConfig(
            litmus_url="https://litmus.example.com",
            litmus_username="testuser",
            litmus_password="testpass",
            litmus_project="test-project",
            litmus_environment="test-env",
            litmus_infra="test-infra",
            experiment_name="test-experiment",
            run_experiment=False,
        )

        # Mock all service calls
        mocker.patch("src.main.LitmusClient")
        mock_get_project_id = mocker.patch("src.main.get_project_id", return_value="proj-123")
        mock_get_env_id = mocker.patch("src.main.get_environment_id", return_value="env-456")
        mock_get_infra_id = mocker.patch("src.main.get_infrastructure_id", return_value="infra-789")
        mock_get_experiment = mocker.patch("src.main.get_chaos_experiment", return_value="exp-999")

        # Act
        main(config)

        # Assert
        assert mock_get_project_id.called
        assert mock_get_env_id.called
        assert mock_get_infra_id.called
        assert mock_get_experiment.called

    def test_main_with_env_vars(self, mocker):
        """Test main function loading config from environment variables."""
        # Arrange
        env_vars = {
            "LITMUS_URL": "https://litmus.example.com",
            "LITMUS_USERNAME": "testuser",
            "LITMUS_PASSWORD": "testpass",
            "LITMUS_PROJECT": "test-project",
            "LITMUS_ENVIRONMENT": "test-env",
            "LITMUS_INFRA": "test-infra",
            "EXPERIMENT_NAME": "test-experiment",
            "RUN_EXPERIMENT": "false",
        }

        # Mock all service calls
        mocker.patch("src.main.LitmusClient")
        mocker.patch("src.main.get_project_id", return_value="proj-123")
        mocker.patch("src.main.get_environment_id", return_value="env-456")
        mocker.patch("src.main.get_infrastructure_id", return_value="infra-789")
        mocker.patch("src.main.get_chaos_experiment", return_value="exp-999")

        # Act
        with patch.dict("os.environ", env_vars):
            main()

        # Assert - should not raise

    def test_main_creates_and_runs_experiment(self, mocker):
        """Test main function creating and running new experiment."""
        # Arrange
        config = LitmusConfig(
            litmus_url="https://litmus.example.com",
            litmus_username="testuser",
            litmus_password="testpass",
            litmus_project="test-project",
            litmus_environment="test-env",
            litmus_infra="test-infra",
            experiment_manifest="apiVersion: v1\nkind: Workflow",
            run_experiment=True,
        )

        # Mock all service calls
        mocker.patch("src.main.LitmusClient")
        mocker.patch("src.main.get_project_id", return_value="proj-123")
        mocker.patch("src.main.get_environment_id", return_value="env-456")
        mocker.patch("src.main.get_infrastructure_id", return_value="infra-789")
        mock_create = mocker.patch(
            "src.main.create_chaos_experiment",
            return_value={"experimentID": "exp-new", "experimentName": "new-exp"},
        )
        mock_run = mocker.patch(
            "src.main.run_chaos_experiment",
            return_value={"runExperiment": {"notifyID": "notify-123"}},
        )
        mock_wait = mocker.patch("src.main.wait_experiment_completion")

        # Act
        main(config)

        # Assert
        assert mock_create.called
        assert mock_run.called
        assert mock_wait.called

    def test_main_handles_missing_env_vars(self, mocker):
        """Test main function exits with error on missing config."""
        # Arrange
        env_vars = {"LITMUS_URL": "https://litmus.example.com"}  # Missing required vars

        # Act & Assert
        with patch.dict("os.environ", env_vars, clear=True):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1

    def test_main_exception_propagation(self, mocker):
        """Test that exceptions in main are properly logged and re-raised."""
        # Arrange
        config = LitmusConfig(
            litmus_url="https://litmus.example.com",
            litmus_username="testuser",
            litmus_password="testpass",
            litmus_project="test-project",
            litmus_environment="test-env",
            litmus_infra="test-infra",
            experiment_name="test-experiment",
        )

        # Mock authentication to fail
        mock_client_instance = MagicMock()
        mock_client_instance.authenticate.side_effect = LitmusAuthenticationError("Auth failed")
        mock_client = mocker.patch("src.main.LitmusClient")
        mock_client.return_value.__enter__.return_value = mock_client_instance

        # Act & Assert
        with pytest.raises(LitmusAuthenticationError):
            main(config)
