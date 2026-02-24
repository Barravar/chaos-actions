#!/usr/bin/env python3
"""Main entry point for Litmus Chaos Actions."""

import json
import os
import uuid
import yaml
from typing import Optional

from .config import LitmusConfig, LoggerConfig, RetryConfig
from .client import LitmusClient
from .exceptions import LitmusRestError, LitmusGraphQLError
from .queries import LitmusGraphQLQueries
from .models import SaveChaosExperimentRequest
from .utils import serialize

# Initialize logger
logger = LoggerConfig.setup_logger()

# Load configuration from environment variables with standardized names
config = LitmusConfig(
  litmus_url=os.getenv("LITMUS_URL", ""),
  litmus_username=os.getenv("LITMUS_USERNAME", ""),
  litmus_password=os.getenv("LITMUS_PASSWORD", ""),
  litmus_project=os.getenv("LITMUS_PROJECT", ""),
  litmus_environment=os.getenv("LITMUS_ENVIRONMENT", ""),
  litmus_infra=os.getenv("LITMUS_INFRA", ""),
  experiment_name=os.getenv("EXPERIMENT_NAME", ""),
  experiment_manifest=os.getenv("EXPERIMENT_MANIFEST", ""),
  run_experiment=os.getenv("RUN_EXPERIMENT", "true").lower() == "true"
)

# Retry configuration
retry_config = RetryConfig()


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
  try:
    response = client._rest_call(
      method="GET",
      path="/list_projects"
    )
    projects = response.json()

    # Check if response contains expected data
    if "data" not in projects or "projects" not in projects.get("data", {}):
      logger.error("Invalid response structure: 'data' or 'projects' key missing.")
      raise LitmusRestError("Invalid response structure from Litmus REST API")
    
    project_data = projects.get("data", {}).get("projects", [])

    # Print all retrieved projects for debugging
    logger.debug(f"Retrieved projects: {[proj.get('name') for proj in project_data]}")

    # Search for the project by name
    project_info = next((p for p in project_data if p.get("name") == project_name), None)
    if not project_info or "projectID" not in project_info:
      logger.error(f"Project {project_name} not found. Check if the project exists and try again.")
      raise LitmusRestError(f"Project {project_name} not found in Litmus REST API response")

    # Print projectID for debugging
    logger.debug(f"Project {project_name} has ID {project_info.get('projectID')}")
    return project_info.get("projectID")
  
  except KeyError as e:
    logger.error(f"Missing required key in projects response: {e}")
    raise LitmusRestError(f"Invalid response structure: missing key {e}") from e
  except (AttributeError, TypeError) as e:
    logger.error(f"Error retrieving projects: {e}")
    raise LitmusRestError(f"Error retrieving projects: {e}") from e


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
  variables = {
    "projectID": project_id,
    "request": {"filter": {"name": environment_name}}
  }

  try:
    response = client._graphql_call(
      query=LitmusGraphQLQueries.LIST_ENVIRONMENTS,
      variables=variables
    )
    env_data = response.get("listEnvironments", {}).get("environments", [])
    
    # Check if environment exists
    if not env_data:
      logger.error(f"Environment {environment_name} not found in project {project_id}")
      raise LitmusGraphQLError(f"Environment {environment_name} not found")
    elif len(env_data) > 1:
      logger.error(f"Multiple environments found with name {environment_name} in project {project_id}")
      raise LitmusGraphQLError(f"Multiple environments found with name {environment_name} in project {project_id}")

    env_id = env_data[0].get("environmentID")
    if not env_id:
      logger.error(f"Could not get environment ID for environment {environment_name}")
      raise LitmusGraphQLError(f"Could not get environment ID for environment {environment_name}")
    
    # Print environmentID for debugging
    logger.debug(f"Environment {environment_name} has ID {env_id}")
    return env_id
  
  except KeyError as e:
    logger.error(f"Missing required key in environments response: {e}")
    raise LitmusGraphQLError(f"Invalid response structure: missing key {e}") from e
  except (AttributeError, TypeError) as e:
    logger.error(f"Error retrieving environmentID for {environment_name}: {e}")
    raise LitmusGraphQLError(f"Error retrieving environmentID for {environment_name}: {e}") from e


def get_infrastructure_id(client: LitmusClient, project_id: str, environment_id: str, litmus_infra: str) -> str:
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
    "request": {"environmentIDs": [environment_id], "filter": {"name": litmus_infra}}
  }

  try:
    response = client._graphql_call(
      query=LitmusGraphQLQueries.LIST_CHAOS_INFRASTRUCTURES,
      variables=variables
    )
    # Validate response structure
    infra_data = response.get("listInfras", {}).get("infras", [])

    if not infra_data:
      logger.error(f"Chaos Infrastructure {litmus_infra} not found in environment {environment_id}")
      raise LitmusGraphQLError(f"Chaos Infrastructure {litmus_infra} not found")
    elif len(infra_data) > 1:
      logger.error(f"Multiple Chaos Infrastructures found with name {litmus_infra} in environment {environment_id}")
      raise LitmusGraphQLError(f"Multiple Chaos Infrastructures found with name {litmus_infra} in environment {environment_id}")
    
    infra_info = infra_data[0]
    infra_id = infra_info.get("infraID")
    is_active = infra_info.get("isActive")
    is_confirmed = infra_info.get("isInfraConfirmed")
    
    if not infra_id:
      logger.error(f"Could not get infrastructure ID for Chaos Infrastructure {litmus_infra}")
      raise LitmusGraphQLError(f"Could not get infrastructure ID for Chaos Infrastructure {litmus_infra}")
    
    # Validate infrastructure is active and confirmed
    if not is_active:
      logger.error(f"Chaos Infrastructure {litmus_infra} is not active (isActive: {is_active})")
      raise LitmusGraphQLError(f"Chaos Infrastructure {litmus_infra} is not active. Please ensure the infrastructure agent is running and connected.")
    
    if not is_confirmed:
      logger.error(f"Chaos Infrastructure {litmus_infra} is not confirmed (isInfraConfirmed: {is_confirmed})")
      raise LitmusGraphQLError(f"Chaos Infrastructure {litmus_infra} is not confirmed. Please confirm the infrastructure in Litmus UI.")

    # Print infrastructureID for debugging
    logger.debug(f"Chaos Infrastructure {litmus_infra} has ID {infra_id} (active: {is_active}, confirmed: {is_confirmed})")
    return infra_id
  
  except KeyError as e:
    logger.error(f"Missing required key in infrastructures response: {e}")
    raise LitmusGraphQLError(f"Invalid response structure: missing key {e}") from e
  except (AttributeError, TypeError) as e:
    logger.error(f"Error retrieving infrastructureID for {litmus_infra}: {e}")
    raise LitmusGraphQLError(f"Error retrieving infrastructureID for {litmus_infra}: {e}") from e


def parse_manifest(experiment_manifest: str) -> str:
  """
  Read and parse the experiment manifest either from a file or from environment variable.

  Args:
    experiment_manifest: Path to the YAML file or environment variable containing the experiment manifest.

  Returns:
    The experiment manifest as a JSON string (compact format, no spaces).

  Raises:
    ValueError: If the manifest is missing or invalid.
  """
  # Load YAML from file or environment variable
  if os.path.isfile(experiment_manifest):
    try:
      with open(experiment_manifest, 'r') as file:
        manifest_content = file.read()
        logger.debug(f"Read experiment manifest from file {experiment_manifest}, length: {len(manifest_content)}")
    except Exception as e:
      logger.error(f"Error reading experiment manifest file {experiment_manifest}: {e}")
      raise ValueError(f"Error reading experiment manifest file {experiment_manifest}: {e}") from e
  else:
    manifest_content = experiment_manifest
    logger.debug(f"Using experiment manifest from environment variable, length: {len(manifest_content)}")
  
  # Convert YAML manifest to JSON object
  try:
    manifest_dict = yaml.safe_load(manifest_content)
  except yaml.YAMLError as e:
    logger.error(f"Error parsing YAML manifest: {e}")
    raise ValueError(f"Invalid YAML manifest: {e}") from e
  
  # Stringify the converted value to send to Litmus
  # Litmus API requires compact JSON format without whitespace
  try:
    manifest_jsons = json.dumps(manifest_dict, separators=(',', ':'))
    logger.debug(f"Serialized manifest to compact JSON ({len(manifest_jsons)} bytes)")
    return manifest_jsons
  except (TypeError, ValueError) as e:
    logger.error(f"Error converting manifest to JSON: {e}")
    raise ValueError(f"Error converting manifest to JSON: {e}") from e


def get_chaos_experiment(client: LitmusClient, project_id: str, environment_id: str, experiment_name: str) -> str:
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
    "request": {"filter": {"experimentName": experiment_name, "infraActive": True}}
  }

  try:
    response = client._graphql_call(
      query=LitmusGraphQLQueries.LIST_EXPERIMENTS,
      variables=variables
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
    return experiment_id
  
  except KeyError as e:
    logger.error(f"Missing required key in experiments response: {e}")
    raise LitmusGraphQLError(f"Invalid response structure: missing key {e}") from e
  except (AttributeError, TypeError) as e:
    logger.error(f"Error retrieving experimentID for {experiment_name}: {e}")
    raise LitmusGraphQLError(f"Error retrieving experimentID for {experiment_name}: {e}") from e


def create_chaos_experiment(client: LitmusClient, project_id: str, litmus_infra_id: str, experiment_manifest: str, tags: Optional[list[str]] = None) -> dict:
  """
  Create a chaos experiment workflow in Litmus.

  Args:
    client: The LitmusClient instance to use for the call.
    project_id: ID of the project.
    litmus_infra_id: ID of the chaos infrastructure.
    experiment_manifest: The experiment manifest as a YAML string (will be converted to JSON).
    tags: List of tags for the experiment.
    
  Returns:
    The experiment data as a dictionary containing experiment ID and name.
    
  Raises:
    LitmusGraphQLError: If the request fails.
  """
  # Validate experiment manifest
  if not experiment_manifest:
    logger.error("Experiment manifest is missing or empty")
    raise ValueError("Experiment manifest is missing or empty")
  
  # First, load the manifest to extract metadata
  # Load YAML from file or environment variable
  if os.path.isfile(experiment_manifest):
    try:
      with open(experiment_manifest, 'r') as file:
        manifest_content = file.read()
        logger.debug(f"Read experiment manifest from file {experiment_manifest}, length: {len(manifest_content)}")
    except Exception as e:
      logger.error(f"Error reading experiment manifest file {experiment_manifest}: {e}")
      raise ValueError(f"Error reading experiment manifest file {experiment_manifest}: {e}") from e
  else:
    manifest_content = experiment_manifest
    logger.debug(f"Using experiment manifest from environment variable, length: {len(manifest_content)}")
  
  # Generate a unique experiment ID for this run (could also be generated by the API, but we need it for naming)
  experiment_id = f"{uuid.uuid4().hex[:8]}"

  # Get experiment name and description from manifest
  try:
    manifest_dict = yaml.safe_load(manifest_content)
    metadata = manifest_dict.get("metadata", {})
    # Try to get 'name' first, fall back to 'generateName' if not present
    experiment_name = f"{metadata.get('name') or metadata.get('generateName', '').rstrip('-')}-{experiment_id}"
    experiment_description = metadata.get("annotations", {}).get("description", "").strip()
    
    if not experiment_name:
      logger.error("Experiment name not found in manifest metadata")
      raise ValueError("Experiment name not found in manifest metadata (neither 'name' nor 'generateName' present)")
    
    # Set the name field in metadata to match the experiment name (required by API)
    manifest_dict["metadata"]["name"] = experiment_name
    # Remove generateName if present to avoid conflicts
    if "generateName" in manifest_dict["metadata"]:
      del manifest_dict["metadata"]["generateName"]
      
  except yaml.YAMLError as e:
    logger.error(f"Error parsing YAML manifest for experiment name and description: {e}")
    raise ValueError(f"Invalid YAML manifest: {e}") from e
  
  # Now convert the modified manifest to JSON string for Litmus API
  try:
    manifest_json_str = json.dumps(manifest_dict, separators=(',', ':'))
    logger.debug(f"Serialized manifest to compact JSON ({len(manifest_json_str)} bytes)")
  except (TypeError, ValueError) as e:
    logger.error(f"Error converting manifest to JSON: {e}")
    raise ValueError(f"Error converting manifest to JSON: {e}") from e
  
  experiment_request = SaveChaosExperimentRequest(
    id=experiment_id,
    name=experiment_name,
    description=experiment_description,
    manifest=manifest_json_str,
    infraID=litmus_infra_id
  )

  variables = {
    "projectID": project_id,
    "request": serialize(experiment_request)
  }

  logger.info(f"Saving chaos experiment {experiment_name} in project {project_id}")
  try:
    response = client._graphql_call(
      query=LitmusGraphQLQueries.SAVE_EXPERIMENT,
      variables=variables
    )    
    # Prepare custom data for return
    # Somehow the API is not returning the experimentID in the response, so we will return the one we generated for naming
    experiment_data = {"experimentID": experiment_id, "experimentName": experiment_name}
    return experiment_data
    
  except KeyError as e:
    logger.error(f"Missing required key in save experiment response: {e}")
    raise LitmusGraphQLError(f"Invalid response structure: missing key {e}") from e
  except (AttributeError, TypeError) as e:
    logger.error(f"Error saving chaos experiment {experiment_name}: {e}")
    raise LitmusGraphQLError(f"Error saving chaos experiment {experiment_name}: {e}") from e


def run_chaos_experiment(client: LitmusClient, project_id: str, experiment_id: str, experiment_name: str) -> dict:
  """
  Run a chaos experiment in Litmus.

  Args:
    client: The LitmusClient instance to use for the call.
    project_id: ID of the project.
    experiment_id: ID of the experiment to run.
    experiment_name: Name of the experiment to run.
  
  Returns:
    The response from the Litmus API as a dictionary.
  
  Raises:
    LitmusGraphQLError: If the request fails.
  """
  variables = {
    "projectID": project_id,
    "experimentID": experiment_id
  }

  try:
    response = client._graphql_call(
      query=LitmusGraphQLQueries.RUN_EXPERIMENT,
      variables=variables
    )
    return response
  
  except KeyError as e:
    logger.error(f"Missing required key in run experiment response: {e}")
    raise LitmusGraphQLError(f"Invalid response structure: missing key {e}") from e
  except (AttributeError, TypeError) as e:
    logger.error(f"Error running chaos experiment {experiment_name}: {e}")
    raise LitmusGraphQLError(f"Error running chaos experiment {experiment_name}: {e}") from e


def main() -> None:
  """
  Main function to orchestrate the script execution.
  Performs authentication, retrieves IDs, creates and runs chaos experiments as configured.
  """
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
    environment_id = get_environment_id(client=client, environment_name=config.litmus_environment, project_id=project_id)
    
    # Get infrastructure ID
    logger.info(f"Retrieving infrastructureID for cluster {config.litmus_infra}")
    litmus_infra_id = get_infrastructure_id(
      client=client, 
      project_id=project_id, 
      environment_id=environment_id, 
      litmus_infra=config.litmus_infra
    )
    
    # Create chaos experiment request
    if not config.experiment_name:
      logger.info("Creating new chaos experiment based on provided manifest")
      experiment_manifest = config.experiment_manifest
      create_experiment = create_chaos_experiment(
        client=client, 
        project_id=project_id, 
        litmus_infra_id=litmus_infra_id, 
        experiment_manifest=experiment_manifest
      )
      config.experiment_name = create_experiment['experimentName']
      experiment_id = create_experiment['experimentID']
    else:
      # If experiment name is provided, skip creation and use existing
      logger.info(f"Retrieving experimentID for experiment {config.experiment_name}")
      experiment_id = get_chaos_experiment(
        client=client, 
        project_id=project_id, 
        environment_id=environment_id, 
        experiment_name=config.experiment_name
      )
    
    # Run chaos experiment if specified
    if config.run_experiment:
      logger.info(f"Running chaos experiment {config.experiment_name}")
      run_chaos_experiment(
        client=client, 
        project_id=project_id, 
        experiment_id=experiment_id, 
        experiment_name=config.experiment_name
      )
    else:
      logger.info("Skipping experiment run as per configuration")


if __name__ == "__main__":
  try:
    main()
  except Exception as e:
    logger.error(f"Script terminated with error: {e}")
    raise
