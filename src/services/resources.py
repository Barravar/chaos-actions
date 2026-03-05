"""Resource ID resolution services for Litmus Chaos.

This module provides functions to resolve IDs for:
- Projects
- Environments
- Infrastructure
- Experiments
"""

import logging

from ..client import LitmusClient
from ..exceptions import LitmusGraphQLError, LitmusRestError
from ..queries import LitmusGraphQLQueries
from ..utils import handle_graphql_errors, handle_rest_errors

# Initialize logger
logger = logging.getLogger(__name__)

# Constants for validation
PAGINATION_WARNING_THRESHOLD = 100  # Number of items that may indicate pagination issues


@handle_rest_errors("retrieve project ID")
def get_project_id(client: LitmusClient, project_name: str) -> str:
    """
    Retrieve the project ID for a given project name.

    Args:
      client: The LitmusClient instance to use for the call.
      project_name: Name of the project to look up.

    Returns:
      The project ID as a string.

    Raises:
      LitmusRestError: If the request fails.
    """
    response = client._rest_call(method="GET", path="/list_projects")
    projects = response.json()

    # Check if response contains expected data
    if "data" not in projects or "projects" not in projects.get("data", {}):
        logger.error("Invalid response structure: 'data' or 'projects' key missing.")
        raise LitmusRestError("Invalid response structure from Litmus REST API")

    project_data = projects.get("data", {}).get("projects", [])

    # Warn if large number of projects (potential pagination issue)
    if len(project_data) >= PAGINATION_WARNING_THRESHOLD:
        logger.warning(
            f"Retrieved {len(project_data)} projects. "
            f"If you have more projects, some may not be included in the results."
        )

    # Print all retrieved projects for debugging
    logger.debug(f"Retrieved projects: {[proj.get('name') for proj in project_data]}")

    # Search for the project by name
    project_info = next((p for p in project_data if p.get("name") == project_name), None)
    if not project_info or "projectID" not in project_info:
        logger.error(
            f"Project {project_name} not found. Check if the project exists and try again."
        )
        raise LitmusRestError(f"Project {project_name} not found in Litmus REST API response")

    # Print projectID for debugging
    logger.debug(f"Project {project_name} has ID {project_info.get('projectID')}")
    project_id = project_info.get("projectID")
    assert isinstance(project_id, str)
    return project_id


@handle_graphql_errors("retrieve environment ID")
def get_environment_id(client: LitmusClient, environment_name: str, project_id: str) -> str:
    """
    Retrieve the environment ID for a given environment name within a project.

    Args:
      client: The LitmusClient instance to use for the call.
      environment_name: Name of the environment to look up.
      project_id: ID of the project containing the environment.

    Returns:
      The environment ID as a string.

    Raises:
      LitmusGraphQLError: If the request fails.
    """
    # Variables for the GraphQL query filtering by environment name
    variables = {"projectID": project_id, "request": {"filter": {"name": environment_name}}}

    response = client._graphql_call(
        query=LitmusGraphQLQueries.LIST_ENVIRONMENTS, variables=variables
    )
    env_data = response.get("listEnvironments", {}).get("environments", [])

    # Check if environment exists
    if not env_data:
        logger.error(f"Environment {environment_name} not found in project {project_id}")
        raise LitmusGraphQLError(f"Environment {environment_name} not found")
    elif len(env_data) > 1:
        logger.error(
            f"Multiple environments found with name {environment_name} in project {project_id}"
        )
        raise LitmusGraphQLError(
            f"Multiple environments found with name {environment_name} in project {project_id}"
        )

    env_id = env_data[0].get("environmentID")
    if not env_id:
        logger.error(f"Could not get environment ID for environment {environment_name}")
        raise LitmusGraphQLError(f"Could not get environment ID for environment {environment_name}")

    # Print environmentID for debugging
    logger.debug(f"Environment {environment_name} has ID {env_id}")
    assert isinstance(env_id, str)
    return env_id


@handle_graphql_errors("retrieve infrastructure ID")
def get_infrastructure_id(
    client: LitmusClient, project_id: str, environment_id: str, litmus_infra: str
) -> str:
    """
    Retrieve the infrastructure ID for a given infrastructure name within an environment.

    Args:
      client: The LitmusClient instance to use for the call.
      project_id: ID of the project containing the environment.
      environment_id: ID of the environment containing the infrastructure.
      litmus_infra: Name of the Chaos Infrastructure to look up.

    Returns:
      The Chaos Infrastructure ID as a string.

    Raises:
      LitmusGraphQLError: If the request fails.
    """
    variables = {
        "projectID": project_id,
        "request": {"environmentIDs": [environment_id], "filter": {"name": litmus_infra}},
    }

    response = client._graphql_call(
        query=LitmusGraphQLQueries.LIST_CHAOS_INFRASTRUCTURES, variables=variables
    )
    # Validate response structure
    infra_data = response.get("listInfras", {}).get("infras", [])

    if not infra_data:
        logger.error(
            f"Chaos Infrastructure {litmus_infra} not found in environment {environment_id}"
        )
        raise LitmusGraphQLError(f"Chaos Infrastructure {litmus_infra} not found")
    elif len(infra_data) > 1:
        logger.error(
            f"Multiple Chaos Infrastructures found with name {litmus_infra} "
            f"in environment {environment_id}"
        )
        raise LitmusGraphQLError(
            f"Multiple Chaos Infrastructures found with name {litmus_infra} "
            f"in environment {environment_id}"
        )

    infra_info = infra_data[0]
    infra_id = infra_info.get("infraID")
    is_active = infra_info.get("isActive")
    is_confirmed = infra_info.get("isInfraConfirmed")

    if not infra_id:
        logger.error(f"Could not get infrastructure ID for Chaos Infrastructure {litmus_infra}")
        raise LitmusGraphQLError(
            f"Could not get infrastructure ID for Chaos Infrastructure {litmus_infra}"
        )

    # Validate infrastructure is active and confirmed
    if not is_active:
        logger.error(f"Chaos Infrastructure {litmus_infra} is not active (isActive: {is_active})")
        raise LitmusGraphQLError(
            f"Chaos Infrastructure {litmus_infra} is not active. "
            f"Please ensure the infrastructure agent is running and connected."
        )

    if not is_confirmed:
        logger.error(
            f"Chaos Infrastructure {litmus_infra} is not confirmed "
            f"(isInfraConfirmed: {is_confirmed})"
        )
        raise LitmusGraphQLError(
            f"Chaos Infrastructure {litmus_infra} is not confirmed. "
            f"Please confirm the infrastructure in Litmus UI."
        )

    # Print infrastructureID for debugging
    logger.debug(
        f"Chaos Infrastructure {litmus_infra} has ID {infra_id} "
        f"(active: {is_active}, confirmed: {is_confirmed})"
    )
    assert isinstance(infra_id, str)
    return infra_id


@handle_graphql_errors("retrieve experiment ID")
def get_chaos_experiment(
    client: LitmusClient, project_id: str, environment_id: str, experiment_name: str
) -> str:
    """
    Retrieve chaos experiment details by name.

    Args:
      client: The LitmusClient instance to use for the call.
      project_id: ID of the project.
      environment_id: ID of the environment.
      experiment_name: Name of the experiment to look up.

    Returns:
      The experiment id.

    Raises:
      LitmusGraphQLError: If the request fails.
    """
    variables = {
        "projectID": project_id,
        "request": {"filter": {"experimentName": experiment_name, "infraActive": True}},
    }

    response = client._graphql_call(
        query=LitmusGraphQLQueries.LIST_EXPERIMENTS, variables=variables
    )
    # Validate response structure
    experiment_data = response.get("listExperiment", {}).get("experiments", [])

    if not experiment_data:
        logger.error(f"Experiment {experiment_name} not found in project {project_id}")
        raise LitmusGraphQLError(f"Experiment {experiment_name} not found")

    experiment_info = experiment_data[0]
    experiment_id = experiment_info.get("experimentID")

    if not experiment_id:
        logger.error(f"Could not get experiment ID for experiment {experiment_name}")
        raise LitmusGraphQLError(f"Could not get experiment ID for experiment {experiment_name}")

    # Print experimentID for debugging
    logger.debug(f"Experiment {experiment_name} has ID {experiment_id}")
    assert isinstance(experiment_id, str)
    return experiment_id
