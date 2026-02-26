"""Manifest utilities for reading and processing experiment manifests."""

import os
import logging

logger = logging.getLogger(__name__)


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
