#!/usr/bin/env python3
"""Main entry point for Litmus Chaos Actions.

This module provides the main workflow for creating and running chaos experiments
using the Litmus Chaos platform. It handles:

- Authentication with Litmus ChaosCenter
- Project, environment, and infrastructure ID resolution
- Chaos experiment creation from YAML manifests
- Experiment execution and status monitoring
- Result logging and fault-level details

The script can be run standalone using environment variables or imported and
called programmatically with injectable configuration for testing.

Typical workflow:
  1. Authenticate with Litmus API
  2. Resolve IDs for project, environment, and infrastructure
  3. Create or retrieve chaos experiment
  4. Run experiment and monitor completion
  5. Log results and exit with appropriate status
"""

import os
import sys

from .client import LitmusClient
from .config import LitmusConfig, LoggerConfig, RetryConfig
from .services.experiments import create_chaos_experiment, run_chaos_experiment
from .services.monitoring import wait_experiment_completion
from .services.resources import (
    get_chaos_experiment,
    get_environment_id,
    get_infrastructure_id,
    get_project_id,
)

# Initialize logger
logger = LoggerConfig.setup_logger()


def main(config: LitmusConfig | None = None, retry_config: RetryConfig | None = None) -> None:
    """
    Orchestrate the script execution.

    Args:
      config: Litmus configuration. If None, loads from environment variables.
      retry_config: Retry configuration. If None, uses default values.
    """
    # Load configuration from environment if not provided
    if config is None:
        try:
            config = LitmusConfig(
                litmus_url=os.getenv("LITMUS_URL", ""),
                litmus_username=os.getenv("LITMUS_USERNAME", ""),
                litmus_password=os.getenv("LITMUS_PASSWORD", ""),
                litmus_project=os.getenv("LITMUS_PROJECT", ""),
                litmus_environment=os.getenv("LITMUS_ENVIRONMENT", ""),
                litmus_infra=os.getenv("LITMUS_INFRA", ""),
                experiment_name=os.getenv("EXPERIMENT_NAME", ""),
                experiment_manifest=os.getenv("EXPERIMENT_MANIFEST", ""),
                run_experiment=os.getenv("RUN_EXPERIMENT", "true").lower() == "true",
            )
        except ValueError as e:
            logger.error(f"Configuration error: {e}")
            sys.exit(1)

    if retry_config is None:
        retry_config = RetryConfig()

    # Log starting message
    logger.info("Starting Litmus Chaos Action script")
    logger.debug("Debug mode is enabled.")

    # Create Litmus client with context manager
    with LitmusClient(config, logger, retry_config) as client:
        # Authenticate with Litmus
        logger.info(f"Authenticating with Litmus Chaos {config.litmus_url}")
        client.authenticate()

        # Get project ID
        logger.info(f"Retrieving projectID for project {config.litmus_project}")
        project_id = get_project_id(client=client, project_name=config.litmus_project)

        # Get environment ID
        logger.info(f"Retrieving environmentID for environment {config.litmus_environment}")
        environment_id = get_environment_id(
            client=client, environment_name=config.litmus_environment, project_id=project_id
        )

        # Get infrastructure ID
        logger.info(f"Retrieving infrastructureID for cluster {config.litmus_infra}")
        litmus_infra_id = get_infrastructure_id(
            client=client,
            project_id=project_id,
            environment_id=environment_id,
            litmus_infra=config.litmus_infra,
        )

        # Create or retrieve chaos experiment
        if not config.experiment_name:
            logger.info("Creating new chaos experiment based on provided manifest")
            experiment_manifest = config.experiment_manifest
            create_experiment = create_chaos_experiment(
                client=client,
                project_id=project_id,
                litmus_infra_id=litmus_infra_id,
                experiment_manifest=experiment_manifest,
            )
            experiment_name = create_experiment["experimentName"]
            experiment_id = create_experiment["experimentID"]
        else:
            # If experiment name is provided, retrieve existing experiment
            experiment_name = config.experiment_name
            logger.info(f"Retrieving experimentID for experiment {experiment_name}")
            experiment_id = get_chaos_experiment(
                client=client,
                project_id=project_id,
                environment_id=environment_id,
                experiment_name=experiment_name,
            )

        # Run chaos experiment if specified
        if config.run_experiment:
            logger.info(f"Running chaos experiment {experiment_name}")
            run_experiment = run_chaos_experiment(
                client=client,
                project_id=project_id,
                experiment_id=experiment_id,
                experiment_name=experiment_name,
            )
            notify_id = run_experiment.get("runExperiment", {}).get("notifyID")
            if not notify_id:
                raise ValueError("No notifyID returned from run experiment")

            wait_experiment_completion(
                client=client,
                project_id=project_id,
                experiment_id=experiment_id,
                notify_id=notify_id,
            )

        else:
            logger.info("Skipping experiment run as per configuration")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.error(f"Script terminated with error: {e}")
        raise
