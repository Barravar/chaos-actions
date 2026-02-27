"""Manifest utilities for reading and processing experiment manifests."""

import os
import logging
from typing import Any

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
      f"Manifest kind '{manifest_dict.get('kind')}' is not in expected kinds: {expected_kinds}"
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
      with open(experiment_manifest, 'r') as file:
        manifest_content = file.read()
        logger.debug(f"Read experiment manifest from file {experiment_manifest}, length: {len(manifest_content)}")
    except Exception as e:
      logger.error(f"Error reading experiment manifest file {experiment_manifest}: {e}")
      raise ValueError(f"Error reading experiment manifest file {experiment_manifest}: {e}") from e
  else:
    manifest_content = experiment_manifest
    logger.debug(f"Using experiment manifest from environment variable, length: {len(manifest_content)}")
  
  return manifest_content
