"""Manifest utilities for reading and processing experiment manifests."""

import json
import logging
import os
import uuid
from typing import Any

import yaml

logger = logging.getLogger(__name__)


def validate_manifest_structure(manifest_dict: dict[str, Any]) -> None:
    """
    Validate that the experiment manifest has required fields.

    Args:
      manifest_dict: Parsed manifest dictionary.

    Raises:
      ValueError: If required fields are missing or invalid.
    """
    # Check for required top-level fields
    if not isinstance(manifest_dict, dict):
        raise ValueError("Manifest must be a dictionary")

    # Validate apiVersion
    if "apiVersion" not in manifest_dict:
        raise ValueError("Manifest missing required field: apiVersion")

    # Validate kind
    if "kind" not in manifest_dict:
        raise ValueError("Manifest missing required field: kind")

    expected_kinds = ["Workflow", "ChaosEngine", "ChaosExperiment"]
    if manifest_dict.get("kind") not in expected_kinds:
        logger.warning(
            f"Manifest kind '{manifest_dict.get('kind')}' is not in expected "
            f"kinds: {expected_kinds}"
        )

    # Validate metadata
    if "metadata" not in manifest_dict:
        raise ValueError("Manifest missing required field: metadata")

    metadata = manifest_dict.get("metadata", {})
    if not isinstance(metadata, dict):
        raise ValueError("Manifest metadata must be a dictionary")

    # Check for name or generateName
    if "name" not in metadata and "generateName" not in metadata:
        raise ValueError("Manifest metadata must contain 'name' or 'generateName'")

    # Validate spec exists
    if "spec" not in manifest_dict:
        raise ValueError("Manifest missing required field: spec")

    if not isinstance(manifest_dict.get("spec"), dict):
        raise ValueError("Manifest spec must be a dictionary")

    logger.debug("Manifest structure validation passed")


def read_manifest_content(experiment_manifest: str) -> str:
    """
    Read manifest content from a file path or return the content directly.

    Args:
      experiment_manifest: Path to the YAML file or the manifest content as a string.

    Returns:
      The manifest content as a string.

    Raises:
      ValueError: If the manifest file cannot be read.
    """
    if os.path.isfile(experiment_manifest):
        try:
            with open(experiment_manifest, "r") as file:
                manifest_content = file.read()
                logger.debug(
                    f"Read experiment manifest from file {experiment_manifest}, "
                    f"length: {len(manifest_content)}"
                )
        except Exception as e:
            logger.error(f"Error reading experiment manifest file {experiment_manifest}: {e}")
            raise ValueError(
                f"Error reading experiment manifest file {experiment_manifest}: {e}"
            ) from e
    else:
        manifest_content = experiment_manifest
        logger.debug(
            f"Using experiment manifest from environment variable, length: {len(manifest_content)}"
        )

    return manifest_content


def generate_experiment_id() -> str:
    """
    Generate a unique experiment ID using standard UUID format.

    Returns:
      A standard UUID string with hyphens (e.g., 'a1b2c3d4-e5f6-a7b8-c9d0-e1f2a3b4c5d6').
    """
    return str(uuid.uuid4())


def prepare_manifest_metadata(
    manifest_content: str, experiment_id: str
) -> tuple[dict[str, Any], str, str]:
    """
    Parse manifest, validate structure, and prepare metadata.

    Args:
      manifest_content: YAML manifest content as a string.
      experiment_id: Unique experiment ID (first 8 chars appended to name for brevity).

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

        # Set experiment name based on manifest fields:
        # use 'name' if present, otherwise use 'generateName'
        base_name = metadata.get("name") or metadata.get("generateName", "").rstrip("-")
        # Use only first 8 characters of UUID for experiment name
        # (full UUID used for experiment ID)
        experiment_name = f"{base_name}-{experiment_id[:8]}"

        # Set experiment description from annotations if available,
        # otherwise use empty string
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


def serialize_manifest_to_json(manifest_dict: dict[str, Any]) -> str:
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
        manifest_json_str = json.dumps(manifest_dict, separators=(",", ":"))
        logger.debug(f"Serialized manifest to compact JSON ({len(manifest_json_str)} bytes)")
        return manifest_json_str
    except (TypeError, ValueError) as e:
        logger.error(f"Error converting manifest to JSON: {e}")
        raise ValueError(f"Error converting manifest to JSON: {e}") from e
