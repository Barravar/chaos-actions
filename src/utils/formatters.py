"""Logging and formatting utilities for Litmus Chaos experiments.

This module provides functions to:
- Format timestamps
- Log experiment results
- Log fault details
"""

import logging
from datetime import datetime
from typing import Any, Optional

import yaml

# Note: ExperimentRunDetails import not needed here as we accept dict[str, Any]

# Initialize logger
logger = logging.getLogger(__name__)


def format_timestamp(timestamp: Optional[str | int]) -> str:
    """
    Format a timestamp string into a more readable format.

    Args:
      timestamp: Unix timestamp (seconds since epoch) as string or int,
                 or ISO format string (can be None).

    Returns:
      Formatted timestamp string, or "N/A" if the input is None or invalid.
    """
    if not timestamp:
        return "N/A"

    try:
        # First, try parsing as Unix timestamp (seconds)
        timestamp_int = int(timestamp) if isinstance(timestamp, str) else timestamp

        # Check if it's a reasonable Unix timestamp (between year 1970 and 2100)
        # Unix timestamps in seconds are typically 10 digits
        if 0 < timestamp_int < 4102444800:  # Jan 1, 2100
            dt = datetime.fromtimestamp(timestamp_int)
            return dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    except (ValueError, TypeError):
        pass

    # Fall back to ISO format parsing
    try:
        if isinstance(timestamp, str):
            dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            return dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    except (ValueError, AttributeError):
        pass

    logger.warning(f"Failed to parse timestamp: {timestamp}")
    return "N/A"


def _log_fault_details(chaos_data: dict[str, Any]) -> None:
    """
    Log details for all faults in an experiment.

    Args:
      chaos_data: Dictionary containing the experiment's chaos data.

    """
    fault_name = chaos_data.get("engineName", "Unknown Fault")
    fault_phase = chaos_data.get("experimentStatus", "Unknown Phase")
    fault_verdict = chaos_data.get("experimentVerdict", "Unknown Status")
    probe_success_percentage = chaos_data.get("probeSuccessPercentage", "N/A")

    logger.info(f"Fault: {fault_name}")
    logger.info(f"  Status: {fault_phase}")
    logger.info(f"  Verdict: {fault_verdict}")
    logger.info(f"  Probe Success Percentage: {probe_success_percentage}")

    probe_details = chaos_data.get("chaosResult", {}).get("status", {}).get("probeStatuses", [])
    if probe_details:
        logger.info("  Probes:")
        for probe in probe_details:
            probe_name = probe.get("name", "Unknown Probe")
            probe_verdict = probe.get("status", {}).get("verdict", "Unknown Verdict")
            probe_description = probe.get("status", {}).get("description", "No details available")
            logger.info(f"  - {probe_name}:")
            logger.info(f"      Verdict: {probe_verdict}")
            logger.info(f"      Description: {probe_description}")


def log_experiment_result(run_details: dict[str, Any]) -> None:
    """
    Log the experiment result in a human-readable format.

    Args:
      run_details: Dictionary containing experiment run details.
    """
    logger.info("=" * 100)
    logger.info("EXPERIMENT RESULT SUMMARY")
    logger.info("=" * 100)

    # Basic information
    experiment_name = run_details.get("experimentName", "Unknown")
    phase = run_details.get("phase", "Unknown")
    score = run_details.get("resiliencyScore")
    total_faults = run_details.get("totalFaults", "N/A")

    logger.info(f"Experiment Name: {experiment_name}")
    logger.info(f"Status: {phase}")
    logger.info(f"Resiliency Score: {score}")
    logger.info(f"Total Faults: {total_faults}")

    # Fault information
    logger.info("-" * 100)
    logger.info("FAULT DETAILS")
    logger.info("-" * 100)

    # Parse execution data if available
    execution_data = run_details.get("executionData", "")
    if execution_data:
        try:
            execution_dict = yaml.safe_load(execution_data)

            # Extract faults from execution data structure
            if isinstance(execution_dict, dict):
                chaos_nodes = execution_dict.get("nodes", {})
                for node_id, node_data in chaos_nodes.items():
                    if node_data.get("type") == "ChaosEngine":
                        _log_fault_details(node_data.get("chaosData", {}))
            else:
                logger.info("  Execution data is not in expected format")
        except Exception as e:
            logger.warning(f"Failed to parse execution data: {e}")
            logger.info("  Could not parse fault details")
    else:
        logger.info("  No execution data available")

    logger.info("=" * 100)
