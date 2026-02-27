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

import json
import os
import time
import uuid
import yaml
from datetime import datetime

from .config import LitmusConfig, LoggerConfig, RetryConfig
from .client import LitmusClient
from .exceptions import LitmusRestError, LitmusGraphQLError
from .queries import LitmusGraphQLQueries
from .models import SaveChaosExperimentRequest
from .utils import (
    serialize,
    read_manifest_content,
    validate_manifest_structure,
    handle_graphql_errors,
    handle_rest_errors
)

# Initialize logger
logger = LoggerConfig.setup_logger()

# Constants for experiment run phases
EXPERIMENT_PHASE_PENDING = "Pending"
EXPERIMENT_PHASE_QUEUED = "Queued"
EXPERIMENT_PHASE_RUNNING = "Running"
EXPERIMENT_PHASE_COMPLETED = "Completed"
EXPERIMENT_PHASE_STOPPED = "Stopped"
EXPERIMENT_PHASE_ERROR = "Error" 
EXPERIMENT_PHASE_TIMEOUT = "Timeout"

# Sets of experiment run phases for status checking
RUNNING_PHASES = {EXPERIMENT_PHASE_PENDING, EXPERIMENT_PHASE_QUEUED, EXPERIMENT_PHASE_RUNNING}
SUCCESS_PHASES = {EXPERIMENT_PHASE_COMPLETED}
FAILURE_PHASES = {EXPERIMENT_PHASE_STOPPED, EXPERIMENT_PHASE_ERROR, EXPERIMENT_PHASE_TIMEOUT}

# Constants for experiment run polling
INITIAL_POLL_DELAY_SECONDS = 10  # Delay before first status check
POLL_INTERVAL_SECONDS = 5  # Default interval between status checks
POLL_TIMEOUT_SECONDS = 1800  # Default timeout (30 minutes)
MAX_BACKOFF_SECONDS = 30  # Maximum backoff interval
MAX_BACKOFF_EXPONENT = 5  # Cap for exponential backoff to prevent excessive waits

# Constants for retry and validation
PAGINATION_WARNING_THRESHOLD = 100  # Number of items that may indicate pagination issues
RETRY_DELAY_SECONDS = 2  # Delay between retries when listing experiment runs
MAX_LIST_ATTEMPTS = 3  # Maximum attempts to retrieve experiment run list


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
    logger.error(f"Project {project_name} not found. Check if the project exists and try again.")
    raise LitmusRestError(f"Project {project_name} not found in Litmus REST API response")

  # Print projectID for debugging
  logger.debug(f"Project {project_name} has ID {project_info.get('projectID')}")
  return project_info.get("projectID")


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
  variables = {
    "projectID": project_id,
    "request": {"filter": {"name": environment_name}}
  }

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


@handle_graphql_errors("retrieve infrastructure ID")
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


@handle_graphql_errors("retrieve experiment ID")
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


def _generate_experiment_id() -> str:
  """
  Generate a unique experiment ID.
  
  Returns:
    A unique 8-character hexadecimal ID.
  """
  return f"{uuid.uuid4().hex[:8]}"


def _prepare_manifest_metadata(manifest_content: str, experiment_id: str) -> tuple[dict, str, str]:
  """
  Parse manifest, validate structure, and prepare metadata.
  
  Args:
    manifest_content: YAML manifest content as a string.
    experiment_id: Unique experiment ID to append to the name.
    
  Returns:
    A tuple of (manifest_dict, experiment_name, experiment_description).
    
  Raises:
    ValueError: If the manifest is invalid or cannot be parsed.
  """
  try:
    manifest_dict = yaml.safe_load(manifest_content)
    # Validate manifest structure before accessing fields
    validate_manifest_structure(manifest_dict)
    metadata = manifest_dict.get("metadata", {})

    # Set experiment name based on manifest fields: use 'name' if present, otherwise use 'generateName'
    base_name = metadata.get('name') or metadata.get('generateName', '').rstrip('-')
    experiment_name = f"{base_name}-{experiment_id}"
    
    # Set experiment description from annotations if available, otherwise use empty string
    experiment_description = metadata.get("annotations", {}).get("description", "").strip()
    
    # Set the name field in metadata to match the experiment name (required by API)
    manifest_dict["metadata"]["name"] = experiment_name
    # Remove generateName if present to avoid conflicts
    if "generateName" in manifest_dict["metadata"]:
      del manifest_dict["metadata"]["generateName"]
      
    return manifest_dict, experiment_name, experiment_description
      
  except yaml.YAMLError as e:
    logger.error(f"Error parsing YAML manifest for experiment name and description: {e}")
    raise ValueError(f"Invalid YAML manifest: {e}") from e


def _serialize_manifest_to_json(manifest_dict: dict) -> str:
  """
  Convert manifest dictionary to compact JSON string.
  
  Args:
    manifest_dict: Parsed manifest dictionary.
    
  Returns:
    Compact JSON string representation of the manifest.
    
  Raises:
    ValueError: If the manifest cannot be serialized to JSON.
  """
  try:
    manifest_json_str = json.dumps(manifest_dict, separators=(',', ':'))
    logger.debug(f"Serialized manifest to compact JSON ({len(manifest_json_str)} bytes)")
    return manifest_json_str
  except (TypeError, ValueError) as e:
    logger.error(f"Error converting manifest to JSON: {e}")
    raise ValueError(f"Error converting manifest to JSON: {e}") from e


@handle_graphql_errors("create chaos experiment")
def create_chaos_experiment(client: LitmusClient, project_id: str, litmus_infra_id: str, experiment_manifest: str) -> dict:
  """
  Create a chaos experiment workflow in Litmus.

  Args:
    client: The LitmusClient instance to use for the call.
    project_id: ID of the project.
    litmus_infra_id: ID of the chaos infrastructure.
    experiment_manifest: The experiment manifest as a YAML string (will be converted to JSON).
    
  Returns:
    The experiment data as a dictionary containing experiment ID and name.
    
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
  experiment_id = _generate_experiment_id()

  # Parse and prepare manifest metadata
  manifest_dict, experiment_name, experiment_description = _prepare_manifest_metadata(
    manifest_content, experiment_id
  )
  
  # Convert manifest to JSON
  manifest_json_str = _serialize_manifest_to_json(manifest_dict)
  
  # Create experiment request
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
  response = client._graphql_call(
    query=LitmusGraphQLQueries.SAVE_EXPERIMENT,
    variables=variables
  )
  
  # Prepare custom data for return
  # Note: The API doesn't return the experimentID in the response, so we return the one we generated
  experiment_data = {"experimentID": experiment_id, "experimentName": experiment_name}
  return experiment_data


@handle_graphql_errors("run chaos experiment")
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

  response = client._graphql_call(
    query=LitmusGraphQLQueries.RUN_EXPERIMENT,
    variables=variables
  )
  return response


def format_timestamp(timestamp_ms: int | str | None) -> str:
  """
  Format a millisecond timestamp to human-readable string.
  
  Args:
    timestamp_ms: Timestamp in milliseconds since epoch.
    
  Returns:
    Formatted timestamp string or "N/A" if invalid.
  """  
  if not timestamp_ms:
    return "N/A"
  
  try:
    dt = datetime.fromtimestamp(int(timestamp_ms) / 1000)
    return dt.strftime("%Y-%m-%d %H:%M:%S")
  except (ValueError, TypeError, OSError) as e:
    logger.debug(f"Failed to parse timestamp {timestamp_ms}: {e}")
    return str(timestamp_ms)


def log_experiment_result(experiment_run: dict, run_id: str) -> None:
  """
  Log detailed experiment run results including fault-level details.
  
  Args:
    experiment_run: Experiment run data from the API.
    run_id: ID of the experiment run.
  """
  phase = experiment_run.get("phase")
  score = experiment_run.get("resiliencyScore")
  updated_at = experiment_run.get("updatedAt")
  execution_data = experiment_run.get("executionData", "")
  
  formatted_time = format_timestamp(updated_at)
  
  # Log summary
  logger.info("=" * 100)
  logger.info("EXPERIMENT RUN COMPLETED")
  logger.info("=" * 100)
  logger.info(f"Run ID: {run_id}")
  logger.info(f"Experiment Name: {experiment_run.get('experimentName', 'N/A')}")
  logger.info(f"Status: {phase}")
  logger.info(f"Resiliency Score: {score}")
  logger.info(f"Updated At: {formatted_time}")
  
  # Log fault details
  _log_fault_details(execution_data, experiment_run.get('totalFaults', 'N/A'))
  
  logger.info("=" * 100)


def _log_fault_details(execution_data: str, total_faults: int | str) -> None:
  """
  Parse and log fault-level details from execution data.
  
  Args:
    execution_data: JSON string containing execution details.
    total_faults: Total number of faults in the experiment.
  """
  if not execution_data:
    return
  
  try:
    exec_dict = json.loads(execution_data)
    chaos_nodes = exec_dict.get("nodes", {})
    
    # Filter and display ChaosEngine nodes (faults)
    for node_id, node_data in chaos_nodes.items():
      if node_data.get("type") == "ChaosEngine":
        _log_single_fault(node_data)
    
    logger.info("-" * 100)
    logger.info(f"Total Faults: {total_faults}")
  except json.JSONDecodeError as e:
    logger.debug(f"Could not parse execution data: {e}")
  except Exception as e:
    logger.debug(f"Error processing fault details: {e}")


def _log_single_fault(node_data: dict) -> None:
  """
  Log details for a single chaos fault.
  
  Args:
    node_data: Node data for a ChaosEngine fault.
  """
  fault_name = node_data.get('name', 'N/A')
  fault_phase = node_data.get('phase', 'N/A')
  
  chaos_data = node_data.get("chaosData", {})
  chaos_result = chaos_data.get("chaosResult", {})
  fault_status = chaos_result.get('verdict', chaos_result.get('status', 'N/A'))
  
  logger.info("-" * 100)
  logger.info(f"Fault: {fault_name}")
  logger.info(f"  Phase: {fault_phase}")
  logger.info(f"  Status: {fault_status}")
  
  # Display additional fault details if available
  if chaos_result:
    probe_success_percentage = chaos_result.get('probeSuccessPercentage')
    fail_step = chaos_result.get('failStep')
    
    if probe_success_percentage is not None:
      logger.info(f"  Probe Success: {probe_success_percentage}%")
    if fail_step:
      logger.info(f"  Failed at: {fail_step}")


def wait_experiment_completion(client: LitmusClient, project_id: str, experiment_id: str, notify_id: str, poll_interval: int = POLL_INTERVAL_SECONDS, timeout_seconds: int = POLL_TIMEOUT_SECONDS) -> dict:
  """
  Wait for a chaos experiment run to complete by polling its status.

  Args:
    client: The LitmusClient instance to use for the call.
    project_id: ID of the project.
    experiment_id: ID of the experiment to monitor.
    notify_id: ID provided by run_chaos_experiment to track the specific run.
    poll_interval: Time interval (in seconds) between status checks (default: 10 seconds).
    timeout_seconds: Maximum time to wait for completion before timing out (default: 30 minutes).

  Returns:
    The final status of the experiment run as a dictionary.

  Raises:
    LitmusGraphQLError: If the request fails or if the experiment run does not complete within the timeout.
  """
  # Record the start time to implement timeout logic
  start_time = time.time()
  logger.info(f"Starting experiment run monitoring (timeout: {timeout_seconds}s, poll interval: {poll_interval}s)")

  # Delay the first status check to allow the experiment run to be registered in the system
  logger.info(f"Waiting {INITIAL_POLL_DELAY_SECONDS}s for experiment run to be registered...")
  logger.info(f"Monitor status at: {client.config.litmus_url}/project/{project_id}/experiments/{experiment_id}/runs")
  time.sleep(INITIAL_POLL_DELAY_SECONDS)

  # STEP 1: List the experiment runs by experiment ID with validation
  # To mitigate race conditions, we'll verify the run was created very recently and retry if needed
  # Variables for the GraphQL query to list experiment runs filtered by experiment ID and sorted by most recent
  list_runs_vars = {
    "projectID": project_id,
    "request": {"experimentIDs": [experiment_id], "sort": {"field": "TIME", "ascending": False}}
  }

  run_id = None
  
  for attempt in range(MAX_LIST_ATTEMPTS):
    try:
      response = client._graphql_call(
        query=LitmusGraphQLQueries.LIST_EXPERIMENT_RUN,
        variables=list_runs_vars
      )
      experiment_runs = response.get("listExperimentRun", {}).get("experimentRuns", [])
      
      if not experiment_runs:
        if attempt < MAX_LIST_ATTEMPTS - 1:
          logger.warning(f"No experiment runs found yet (attempt {attempt + 1}/{MAX_LIST_ATTEMPTS}), retrying in {RETRY_DELAY_SECONDS}s...")
          time.sleep(RETRY_DELAY_SECONDS)
          continue
        else:
          logger.error(f"No experiment runs found for experimentID {experiment_id} after {MAX_LIST_ATTEMPTS} attempts")
          raise LitmusGraphQLError(f"No experiment runs found for experimentID {experiment_id}")
      
      # Get the most recent run
      most_recent_run = experiment_runs[0]
      run_id = most_recent_run.get("experimentRunID")
      
      # Validation: Log if there are multiple recent runs (potential race condition indicator)
      if len(experiment_runs) > 1:
        logger.warning(f"Found {len(experiment_runs)} experiment runs for this experiment. Using most recent: {run_id}")
      
      logger.info(f"Monitoring experiment run: {run_id} (notifyID: {notify_id})")
      break

    except KeyError as e:
      logger.error(f"Missing required key in experiment run response: {e}")
      raise LitmusGraphQLError(f"Invalid response structure: missing key {e}") from e
    except (AttributeError, TypeError) as e:
      logger.error(f"Error retrieving experiment runs for experiment {experiment_id}: {e}")
      raise LitmusGraphQLError(f"Error retrieving experiment runs for experiment {experiment_id}: {e}") from e
  
  if run_id is None:
    raise LitmusGraphQLError(f"Failed to retrieve experiment run ID after {MAX_LIST_ATTEMPTS} attempts")

  # STEP 2: Poll the experiment run status until it reaches a terminal state (e.g., Succeeded, Failed, Aborted) or until timeout
  # Variables for the GraphQL query to get experiment run status by run ID and notifyID
  # Using both IDs provides additional verification that we're tracking the correct run
  get_run_vars = {
    "projectID": project_id,
    "experimentRunID": run_id,
    "notifyID": notify_id
  }
  
  poll_count = 0  # Track actual poll attempts for backoff calculation
  # Loop to poll experiment run status
  while True:
    try:
      response = client._graphql_call(
        query=LitmusGraphQLQueries.GET_EXPERIMENT_RUN,
        variables=get_run_vars
      )
      experiment_run = response.get("getExperimentRun", {})
      
      if not experiment_run:
        logger.error(f"No experiment run found for experimentRunID {run_id} and notifyID {notify_id}")
        raise LitmusGraphQLError(f"No experiment run found for experimentRunID {run_id} and notifyID {notify_id}")
      
      # Verify we're still tracking the same run
      returned_run_id = experiment_run.get("experimentRunID")
      if returned_run_id and returned_run_id != run_id:
        logger.error(f"Run ID mismatch: expected {run_id}, got {returned_run_id}")
        raise LitmusGraphQLError(f"Run ID mismatch: tracking {run_id} but API returned {returned_run_id}")
      
      phase = experiment_run.get("phase")
      
      if phase not in RUNNING_PHASES:
        # Experiment has reached a terminal state
        log_experiment_result(experiment_run, run_id)
        
        if phase in SUCCESS_PHASES:
          logger.info(f"✓ Experiment run {run_id} completed successfully")
          return experiment_run
        elif phase in FAILURE_PHASES:
          logger.error(f"✗ Experiment run {run_id} failed: {phase}")
          raise LitmusGraphQLError(f"Experiment run {run_id} failed: {phase}")
        else:
          # Unknown terminal state - log warning but return the result
          logger.warning(f"Experiment run {run_id} completed with status: {phase}")
          return experiment_run

    except KeyError as e:
      logger.error(f"Missing required key in experiment run status response: {e}")
      raise LitmusGraphQLError(f"Invalid response structure: missing key {e}") from e
    except (AttributeError, TypeError) as e:
      logger.error(f"Error retrieving status for experiment run {run_id}: {e}")
      raise LitmusGraphQLError(f"Error retrieving status for experiment run {run_id}: {e}") from e

    # Check for timeout
    elapsed_time = time.time() - start_time
    logger.info(f"Experiment run {run_id} is currently in phase: {phase}. Elapsed time: {int(elapsed_time)} seconds")
    if elapsed_time > timeout_seconds:
      logger.error(f"Timed out waiting for experiment run {run_id} to complete after {timeout_seconds} seconds")
      raise LitmusGraphQLError(f"Timed out waiting for experiment run {run_id} to complete after {timeout_seconds} seconds")

    # Wait before polling again with exponential backoff
    # Calculate backoff based on actual poll count and cap the exponent to prevent extremely long waits
    poll_count += 1
    backoff_time = min(poll_interval * (2 ** min(poll_count, MAX_BACKOFF_EXPONENT)), MAX_BACKOFF_SECONDS)
    logger.debug(f"Next poll in {backoff_time}s (attempt {poll_count + 1})")
    time.sleep(backoff_time)


def main(config: LitmusConfig | None = None, retry_config: RetryConfig | None = None) -> None:
  """
  Main function to orchestrate the script execution.
  
  Args:
    config: Litmus configuration. If None, loads from environment variables.
    retry_config: Retry configuration. If None, uses default values.
  """
  # Load configuration from environment if not provided
  if config is None:
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
      experiment_name = create_experiment['experimentName']
      experiment_id = create_experiment['experimentID']
    else:
      # If experiment name is provided instead, skip creation and work with existing experiment
      logger.info(f"Retrieving experimentID for experiment {experiment_name}")
      experiment_id = get_chaos_experiment(
        client=client, 
        project_id=project_id, 
        environment_id=environment_id, 
        experiment_name=experiment_name
      )
    
    # Run chaos experiment if specified
    if config.run_experiment:
      logger.info(f"Running chaos experiment {experiment_name}")
      run_experiment = run_chaos_experiment(
        client=client, 
        project_id=project_id, 
        experiment_id=experiment_id, 
        experiment_name=experiment_name
      )
      notify_id = run_experiment.get("runExperiment", {}).get("notifyID")

      wait_experiment_completion(
        client=client, 
        project_id=project_id, 
        experiment_id=experiment_id,
        notify_id=notify_id
      )

    else:
      logger.info("Skipping experiment run as per configuration")


if __name__ == "__main__":
  try:
    main()
  except Exception as e:
    logger.error(f"Script terminated with error: {e}")
    raise
