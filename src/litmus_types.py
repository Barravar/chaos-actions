"""Type definitions for Litmus Chaos Actions."""

from typing import TypedDict

class WeightageItem(TypedDict):
  """Represents a fault weightage configuration."""
  faultName: str
  weightage: int

# Type aliases for better code readability and type safety
ExperimentID = str
ExperimentName = str
ExperimentDescription = str
ExperimentManifest = str
ExperimentType = str
LitmusTags = list[str]
CronSyntax = str
Weightages = list[WeightageItem]
InfraID = str
