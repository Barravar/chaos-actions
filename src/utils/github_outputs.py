"""GitHub Actions output utilities."""

from __future__ import annotations

import json
import os
from typing import Any

import yaml

from ..config import LoggerConfig
from ..litmus_types import ExperimentRunDetails

logger = LoggerConfig.setup_logger()


def extract_fault_results(execution_data: str) -> list[dict[str, Any]]:
    """
    Extract fault results from execution data.

    Args:
      execution_data: YAML-formatted execution data from experiment run.

    Returns:
      List of dictionaries containing fault details.
    """
    fault_results: list[dict[str, Any]] = []

    if not execution_data:
        return fault_results

    try:
        execution_dict = yaml.safe_load(execution_data)

        if isinstance(execution_dict, dict):
            chaos_nodes = execution_dict.get("nodes", {})
            for node_id, node_data in chaos_nodes.items():
                if node_data.get("type") == "ChaosEngine":
                    chaos_data = node_data.get("chaosData", {})
                    engine_name = chaos_data.get("engineName", "Unknown")

                    chaos_result = chaos_data.get("chaosResult", {})
                    experiment_status = chaos_result.get("status", {}).get("experimentStatus", {})

                    fault_result = {
                        "fault_name": engine_name,
                        "verdict": experiment_status.get("verdict", "Unknown"),
                        "fail_step": experiment_status.get("failStep", "N/A"),
                        "probe_success_percentage": experiment_status.get(
                            "probeSuccessPercentage", "N/A"
                        ),
                    }

                    # Add probe details if available
                    probe_statuses = chaos_result.get("status", {}).get("probeStatuses", [])
                    if probe_statuses:
                        fault_result["probes"] = [
                            {
                                "name": probe.get("name", "Unknown"),
                                "type": probe.get("type", "Unknown"),
                                "status": probe.get("status", {}).get("verdict", "Unknown"),
                                "description": probe.get("status", {}).get(
                                    "description", "No details available"
                                ),
                            }
                            for probe in probe_statuses
                        ]

                    fault_results.append(fault_result)

    except Exception as e:
        logger.warning(f"Failed to extract fault results from execution data: {e}")

    return fault_results


def write_github_output(name: str, value: str | int | float | dict[str, Any] | list[Any]) -> None:
    """
    Write an output to GitHub Actions output file.

    Args:
      name: The name of the output.
      value: The value to write. Dicts and lists are JSON-serialized.
    """
    github_output_file = os.getenv("GITHUB_OUTPUT")
    if not github_output_file:
        logger.debug(f"GITHUB_OUTPUT not set, skipping output: {name}={value}")
        return

    try:
        # Convert complex types to JSON
        if isinstance(value, (dict, list)):
            output_value = json.dumps(value, indent=None)
        else:
            output_value = str(value)

        # Write to GitHub output file
        with open(github_output_file, "a") as f:
            # For multi-line values, use heredoc format
            if "\n" in output_value:
                f.write(f"{name}<<EOF\n")
                f.write(f"{output_value}\n")
                f.write("EOF\n")
            else:
                f.write(f"{name}={output_value}\n")

        logger.debug(f"GitHub Actions output written: {name}")

    except Exception as e:
        logger.warning(f"Failed to write GitHub Actions output '{name}': {e}")


def write_experiment_outputs(run_details: ExperimentRunDetails | dict[str, Any]) -> None:
    """
    Write experiment results as GitHub Actions outputs.

    Args:
      run_details: Dictionary containing experiment run details.
    """
    # Extract and write experiment result
    experiment_result = run_details.get("phase", "Unknown")
    write_github_output("EXPERIMENT_RESULT", experiment_result)

    # Extract and write resiliency score
    resiliency_score = run_details.get("resiliencyScore", 0.0)
    write_github_output("RESILIENCY_SCORE", resiliency_score)

    # Extract and write fault results
    execution_data = run_details.get("executionData", "")
    fault_results = extract_fault_results(execution_data)
    write_github_output("FAULT_RESULTS", fault_results)

    logger.info(
        f"Experiment outputs written: result={experiment_result}, "
        f"score={resiliency_score}, faults={len(fault_results)}"
    )
