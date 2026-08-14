from enum import Enum
from typing import List

from pydantic import BaseModel, Field

class IncidentSeverity(str, Enum):
    """Matches the severity vocabulary used in IncidentState (Level 2, Issue #6) - 
    keep these two definitions in sync if either changes."""
    # above one is docstring, its important to add.

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class IncidentDiagnosis(BaseModel):
    """Structures diagnosis extracted from an LLM's analysis of an incident/alert."""
    severity: IncidentSeverity = Field(description="Assessed severity of the incident")
    root_cause: str = Field(description="Concise statement of the most likely root cause")
    affected_services: List[str] = Field(
        default_factory=list, description="Service names implicated in this incident"
    )
    confidence_score: float = Field(
        ge=0.0, le=1.0, description="Model's confidence in this diagnosis, 0-1"
    )


class ExtractedEntities(BaseModel):
    """Structured entities extracted from free-text incident reports or alerts."""

    names: List[str] = Field(default_factory=list, description="Person or team names mentioned")
    dates: List[str] = Field(
        default_factory=list,
        description="Any dates or timestamps mentioned, exactly as written in the source text",
    )
    system_components: List[str] = Field(
        default_factory=list, description="Named systems, services, or infra components mentioned"
    )

