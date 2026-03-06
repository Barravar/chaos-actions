"""Type definitions for Litmus Chaos Actions."""

from __future__ import annotations

from enum import Enum

try:  # pragma: no cover
    from typing import TypedDict
except ImportError:  # pragma: no cover
    from typing_extensions import TypedDict


class WeightageItem(TypedDict):
    """Represents a fault weightage configuration."""

    faultName: str
    weightage: int


class ExperimentData(TypedDict):
    """Type definition for experiment data returned from creation."""

    experimentID: str
    experimentName: str


class RunExperimentResponse(TypedDict):
    """Type definition for run experiment response."""

    runChaosExperiment: dict[str, str]


class ExperimentRunDetails(TypedDict, total=False):
    """Type definition for experiment run details.

    All fields are optional (total=False) as the response may vary.
    """

    experimentRunID: str
    experimentName: str
    phase: str
    resiliencyScore: float
    updatedAt: int
    executionData: str
    totalFaults: int


class ExperimentPhase(str, Enum):
    """Enumeration of experiment run phases."""

    PENDING = "Pending"
    QUEUED = "Queued"
    RUNNING = "Running"
    COMPLETED = "Completed"
    STOPPED = "Stopped"
    ERROR = "Error"
    TIMEOUT = "Timeout"


# Sets of experiment run phases for status checking
RUNNING_PHASES = {ExperimentPhase.PENDING, ExperimentPhase.QUEUED, ExperimentPhase.RUNNING}
SUCCESS_PHASES = {ExperimentPhase.COMPLETED}
FAILURE_PHASES = {ExperimentPhase.STOPPED, ExperimentPhase.ERROR, ExperimentPhase.TIMEOUT}

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
