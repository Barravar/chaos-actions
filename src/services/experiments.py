"""Experiment creation and execution services for Litmus Chaos.

This module provides functions to:
- Create chaos experiments
- Run chaos experiments
"""

import logging

from ..client import LitmusClient
from ..litmus_types import ExperimentData, RunExperimentResponse
from ..models import SaveChaosExperimentRequest
from ..queries import LitmusGraphQLQueries
from ..utils import handle_graphql_errors, read_manifest_content, serialize
from ..utils.manifest import (
    generate_experiment_id,
    prepare_manifest_metadata,
    serialize_manifest_to_json,
)

# Initialize logger
logger = logging.getLogger(__name__)


@handle_graphql_errors("create chaos experiment")
def create_chaos_experiment(
    client: LitmusClient, project_id: str, litmus_infra_id: str, experiment_manifest: str
) -> ExperimentData:
    """
    Create a chaos experiment workflow in Litmus.

    Args:
      client: The LitmusClient instance to use for the call.
      project_id: ID of the project.
      litmus_infra_id: ID of the chaos infrastructure.
      experiment_manifest: The experiment manifest as a YAML string (will be converted to JSON).

    Returns:
      ExperimentData containing experimentID and experimentName.

    Raises:
      LitmusGraphQLError: If the request fails.
      ValueError: If the manifest is invalid or missing.
    """
    # Validate experiment manifest
    if not experiment_manifest:
        logger.error("Experiment manifest is missing or empty")
        raise ValueError("Experiment manifest is missing or empty")

    # Load the manifest content
    manifest_content = read_manifest_content(experiment_manifest)

    # Generate a unique experiment ID
    experiment_id = generate_experiment_id()

    # Parse and prepare manifest metadata
    manifest_dict, experiment_name, experiment_description = prepare_manifest_metadata(
        manifest_content, experiment_id
    )

    # Convert manifest to JSON
    manifest_json_str = serialize_manifest_to_json(manifest_dict)

    # Create experiment request
    experiment_request = SaveChaosExperimentRequest(
        id=experiment_id,
        name=experiment_name,
        description=experiment_description,
        manifest=manifest_json_str,
        infraID=litmus_infra_id,
    )

    variables = {"projectID": project_id, "request": serialize(experiment_request)}

    logger.info(f"Saving chaos experiment {experiment_name} in project {project_id}")
    client._graphql_call(query=LitmusGraphQLQueries.SAVE_EXPERIMENT, variables=variables)

    # Return experiment data with proper type
    # Note: The API doesn't return the experimentID in the response,
    # so we return the one we generated
    return ExperimentData(experimentID=experiment_id, experimentName=experiment_name)


@handle_graphql_errors("run chaos experiment")
def run_chaos_experiment(
    client: LitmusClient, project_id: str, experiment_id: str, experiment_name: str
) -> RunExperimentResponse:
    """
    Run a chaos experiment in Litmus.

    Args:
      client: The LitmusClient instance to use for the call.
      project_id: ID of the project.
      experiment_id: ID of the experiment to run.
      experiment_name: Name of the experiment to run.

    Returns:
      RunExperimentResponse containing the runExperiment data with notifyID.

    Raises:
      LitmusGraphQLError: If the request fails.
    """
    variables = {"projectID": project_id, "experimentID": experiment_id}

    response = client._graphql_call(query=LitmusGraphQLQueries.RUN_EXPERIMENT, variables=variables)
    return RunExperimentResponse(runChaosExperiment=response.get("runChaosExperiment", {}))
