"""Experiment data models."""

from dataclasses import dataclass, field

from ..litmus_types import (
  ExperimentID, ExperimentName, ExperimentDescription, ExperimentManifest,
  InfraID, ExperimentType, LitmusTags
)


@dataclass
class ExperimentRunRequest:
  """
  Represents a request to run a Litmus Chaos experiment.
  
  Attributes:
    experimentID: ID of the experiment to run
    experimentRunID: ID of the specific experiment run
    experimentName: Name of the experiment
    infraID: Infrastructure ID where experiment runs
    executionData: Execution data for the run
    notifyID: Notification ID for alerts
    revisionID: Revision ID for versioning
    completed: Whether the run is completed
    isRemoved: Whether the run has been removed
    updatedBy: User who updated the run
  """
  experimentID: ExperimentID
  experimentRunID: ExperimentID
  experimentName: ExperimentName
  infraID: InfraID
  executionData: str = ""
  notifyID: str = ""
  revisionID: str = ""
  completed: bool = False
  isRemoved: bool = False
  updatedBy: str = ""


@dataclass
class SaveChaosExperimentRequest:
  """
  Represents a request to save a Litmus Chaos experiment.
  
  Attributes:
    id: Experiment ID
    name: Experiment name
    description: Experiment description
    manifest: YAML manifest as string
    infraID: Infrastructure ID
    type: Type of experiment
    tags: List of tags for categorization
  """
  id: ExperimentID
  name: ExperimentName
  description: ExperimentDescription
  manifest: ExperimentManifest
  infraID: InfraID
  type: ExperimentType = "All"
  tags: LitmusTags = field(default_factory=list)
