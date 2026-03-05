"""Experiment monitoring and status polling services for Litmus Chaos.

This module provides functions to:
- Wait for experiment completion
- Poll experiment status
- Retrieve experiment run IDs
"""

import logging
import time
from typing import Optional

from ..client import LitmusClient
from ..exceptions import ExperimentTimeoutError, LitmusGraphQLError
from ..litmus_types import FAILURE_PHASES, RUNNING_PHASES, SUCCESS_PHASES, ExperimentRunDetails
from ..queries import LitmusGraphQLQueries
from ..utils import handle_graphql_errors, log_experiment_result

# Initialize logger
logger = logging.getLogger(__name__)

# Polling configuration
POLL_INTERVAL_SECONDS = 5
POLL_TIMEOUT_SECONDS = 1800  # 30 minutes
MAX_BACKOFF_SECONDS = 30
STATUS_LOG_INTERVAL_SECONDS = 30  # Log status update every 30 seconds when phase hasn't changed

# Constants for retry and validation
RETRY_DELAY_SECONDS = 2  # Delay between retries when listing experiment runs
MAX_LIST_ATTEMPTS = 3  # Maximum attempts to retrieve experiment run list

# Phase constants
UNKNOWN_PHASE = "UNKNOWN"

# GraphQL field names
SORT_FIELD_TIME = "TIME"
EXPERIMENT_IDS_FIELD = "experimentIDs"
SORT_FIELD_NAME = "field"
SORT_ASCENDING_FIELD = "ascending"


def _calculate_backoff_time(elapsed: float) -> float:
    """
    Calculate the backoff time for polling based on elapsed time.

    Args:
      elapsed: Time elapsed since polling started in seconds.

    Returns:
      The backoff time in seconds.
    """
    backoff_time = min(POLL_INTERVAL_SECONDS * (elapsed / 60), MAX_BACKOFF_SECONDS)
    return max(backoff_time, POLL_INTERVAL_SECONDS)


def _retrieve_experiment_run_id(
    client: LitmusClient, project_id: str, experiment_id: str, notify_id: str
) -> str:
    """
    Retrieve the experiment run ID for a given experiment.

    Args:
      client: The LitmusClient instance to use for the call.
      project_id: ID of the project.
      experiment_id: ID of the experiment.
      notify_id: ID provided by run_chaos_experiment to track the specific run.

    Returns:
      The experiment run ID as a string.

    Raises:
      LitmusGraphQLError: If the experiment run cannot be retrieved.
    """
    list_runs_vars = {
        "projectID": project_id,
        "request": {
            EXPERIMENT_IDS_FIELD: [experiment_id],
            "sort": {SORT_FIELD_NAME: SORT_FIELD_TIME, SORT_ASCENDING_FIELD: False},
        },
    }

    for attempt in range(MAX_LIST_ATTEMPTS):
        try:
            response = client._graphql_call(
                query=LitmusGraphQLQueries.LIST_EXPERIMENT_RUN, variables=list_runs_vars
            )
            experiment_runs = response.get("listExperimentRun", {}).get("experimentRuns", [])

            if not experiment_runs:
                if attempt < MAX_LIST_ATTEMPTS - 1:
                    logger.warning(
                        f"No experiment runs found yet "
                        f"(attempt {attempt + 1}/{MAX_LIST_ATTEMPTS}), "
                        f"retrying in {RETRY_DELAY_SECONDS}s..."
                    )
                    time.sleep(RETRY_DELAY_SECONDS)
                    continue
                else:
                    logger.error(
                        f"No experiment runs found for experimentID "
                        f"{experiment_id} after {MAX_LIST_ATTEMPTS} attempts"
                    )
                    raise LitmusGraphQLError(
                        f"No experiment runs found for experimentID {experiment_id}"
                    )

            # Get the most recent run
            most_recent_run = experiment_runs[0]
            run_id = most_recent_run.get("experimentRunID")

            # Validate that we got a run ID
            if not run_id:
                # Log the actual response structure to help debug
                logger.debug(f"Experiment run data: {most_recent_run}")
                if attempt < MAX_LIST_ATTEMPTS - 1:
                    logger.warning(
                        f"Experiment run found but experimentRunID is missing "
                        f"(attempt {attempt + 1}/{MAX_LIST_ATTEMPTS}), "
                        f"retrying in {RETRY_DELAY_SECONDS}s..."
                    )
                    time.sleep(RETRY_DELAY_SECONDS)
                    continue
                else:
                    logger.error(
                        f"Experiment run found but experimentRunID is still missing "
                        f"after {MAX_LIST_ATTEMPTS} attempts"
                    )
                    raise LitmusGraphQLError(
                        "Experiment run found but experimentRunID is missing or empty"
                    )

            # Validation: Log if there are multiple recent runs (potential race condition indicator)
            if len(experiment_runs) > 1:
                logger.warning(
                    f"Found {len(experiment_runs)} experiment runs for this experiment. "
                    f"Using most recent: {run_id}"
                )

            logger.info(f"Monitoring experiment run: {run_id}")
            assert isinstance(run_id, str)
            return run_id

        except KeyError as e:
            logger.error(f"Missing required key in experiment run response: {e}")
            raise LitmusGraphQLError(f"Invalid response structure: missing key {e}") from e
        except (AttributeError, TypeError) as e:
            logger.error(f"Error retrieving experiment runs for experiment {experiment_id}: {e}")
            raise LitmusGraphQLError(
                f"Error retrieving experiment runs for experiment {experiment_id}: {e}"
            ) from e

    raise LitmusGraphQLError(
        f"Failed to retrieve experiment run ID after {MAX_LIST_ATTEMPTS} attempts"
    )


@handle_graphql_errors("get experiment run details")
def _poll_experiment_status(
    client: LitmusClient, project_id: str, experiment_run_id: str, notify_id: str
) -> ExperimentRunDetails:
    """
    Poll the experiment status once.

    Args:
      client: The LitmusClient instance to use for the call.
      project_id: ID of the project.
      experiment_run_id: ID of the experiment run.
      notify_id: Notification ID from running the experiment.

    Returns:
      ExperimentRunDetails containing phase and other run details.

    Raises:
      LitmusGraphQLError: If the request fails.
    """
    variables = {
        "projectID": project_id,
        "experimentRunID": experiment_run_id,
        "notifyID": notify_id,
    }

    response = client._graphql_call(
        query=LitmusGraphQLQueries.GET_EXPERIMENT_RUN, variables=variables
    )

    experiment_run = response.get("getExperimentRun", {})

    if not experiment_run:
        logger.error(
            f"No experiment run found for experimentRunID {experiment_run_id} "
            f"and notifyID {notify_id}"
        )
        raise LitmusGraphQLError(
            f"No experiment run found for experimentRunID {experiment_run_id} "
            f"and notifyID {notify_id}"
        )

    # Verify we're still tracking the same run
    returned_run_id = experiment_run.get("experimentRunID")
    if returned_run_id and experiment_run_id and returned_run_id != experiment_run_id:
        logger.error(f"Run ID mismatch: expected {experiment_run_id}, got {returned_run_id}")
        raise LitmusGraphQLError(
            f"Run ID mismatch: tracking {experiment_run_id} " f"but API returned {returned_run_id}"
        )

    return experiment_run  # type: ignore[no-any-return]


def wait_experiment_completion(
    client: LitmusClient,
    project_id: str,
    experiment_id: str,
    notify_id: str,
    timeout_seconds: int = POLL_TIMEOUT_SECONDS,
) -> ExperimentRunDetails:
    """
    Wait for the experiment to complete and return the final status.

    This function:
    1. Retrieves the experiment run ID from the notify ID
    2. Polls the experiment status at regular intervals
    3. Uses exponential backoff for polling
    4. Waits until the experiment reaches a terminal state (success or failure)
    5. Raises appropriate exceptions for timeout or failure states

    Args:
      client: The LitmusClient instance to use for the call.
      project_id: ID of the project.
      experiment_id: ID of the experiment.
      notify_id: Notification ID from running the experiment.
      timeout_seconds: Maximum time to wait in seconds (default: 1800).

    Returns:
      ExperimentRunDetails containing the final experiment run status.

    Raises:
      ExperimentTimeoutError: If the experiment does not complete within the timeout.
      LitmusGraphQLError: If any API requests fail.

    Note:
      Failed experiments (phase in FAILURE_PHASES) are logged as errors but do not raise
      exceptions, as they represent valid experiment outcomes rather than script errors.
    """
    # Retrieve the experiment run ID
    experiment_run_id = _retrieve_experiment_run_id(client, project_id, experiment_id, notify_id)

    # Poll experiment status
    start_time = time.time()
    last_phase: Optional[str] = None
    last_log_time = start_time

    while True:
        elapsed = time.time() - start_time

        # Check timeout
        if elapsed >= timeout_seconds:
            logger.error(
                f"Experiment run {experiment_run_id} timed out after {timeout_seconds} seconds"
            )
            raise ExperimentTimeoutError(
                f"Experiment run {experiment_run_id} timed out after {timeout_seconds} seconds"
            )

        # Get current run details
        run_details = _poll_experiment_status(client, project_id, experiment_run_id, notify_id)
        phase = run_details.get("phase", UNKNOWN_PHASE)

        # Log phase change or periodic status update
        time_since_last_log = time.time() - last_log_time
        if phase != last_phase:
            logger.info(f"Experiment run {experiment_run_id} is in phase: {phase}")
            last_phase = phase
            last_log_time = time.time()
        elif time_since_last_log >= STATUS_LOG_INTERVAL_SECONDS:
            # Log status update every STATUS_LOG_INTERVAL_SECONDS to show progress
            logger.info(
                f"Experiment run {experiment_run_id} still in phase: {phase} "
                f"(elapsed: {int(elapsed)}s)"
            )
            last_log_time = time.time()

        # Check if experiment is complete and return details
        if phase not in RUNNING_PHASES:
            if phase in SUCCESS_PHASES:
                logger.info(
                    f"Experiment run {experiment_run_id} completed successfully "
                    f"with status: {phase}"
                )
            elif phase in FAILURE_PHASES:
                # Log failed experiments - these are valid outcomes, not script errors
                logger.error(f"Experiment run {experiment_run_id} failed with status: {phase}")
            else:
                logger.warning(
                    f"Experiment run {experiment_run_id} is in an unexpected status: {phase}"
                )

            # Log detailed results for all faults in the experiment
            # TypedDict is compatible with dict[str, Any]
            log_experiment_result(run_details)  # type: ignore[arg-type]
            return run_details

        # Calculate backoff time and sleep
        backoff_time = _calculate_backoff_time(elapsed)
        logger.debug(f"Next poll in {backoff_time:.1f}s (total elapsed: {int(elapsed)}s)")
        time.sleep(backoff_time)
