"""Models for account-related API endpoints, including users, projects, and allocations."""
import datetime
from pydantic import Field, computed_field, field_validator

from ... import config
from ...types.base import IRIBaseModel
from ...types.scalars import AllocationUnit


class Project(IRIBaseModel):
    """A project and its users at a facility"""

    id: str = Field(..., description="Unique identifier of the project.", example="proj-abc123")
    name: str = Field(..., description="Human-readable name of the project.", example="Climate Simulation")
    description: str = Field(..., description="Detailed description of the project.", example="Research project studying atmospheric dynamics.")
    user_ids: list[str] = Field(..., description="List of user identifiers participating in the project.", example=["user-123", "user-456"])

    @field_validator("last_modified", mode="before")
    @classmethod
    def _norm_dt_field(cls, v):
        return cls.normalize_dt(v)

    last_modified: datetime.datetime = Field(..., description="Timestamp of the last modification of the project.", example="2026-02-21T14:30:00Z")

    @computed_field(description="URI to this project resource")
    @property
    def self_uri(self) -> str:
        """Return the URI for this project resource."""
        return f"{config.API_URL_ROOT}{config.API_PREFIX}{config.API_URL}/account/projects/{self.id}"


class AllocationEntry(IRIBaseModel):
    """Base class for allocations."""

    allocation: float = Field(..., description="Total allocation amount granted.", example=100000.0)  # how much this allocation can spend
    usage: float = Field(..., description="Amount of allocation consumed.", example=52342.5)  # how much this allocation has spent
    unit: AllocationUnit = Field(..., description="Unit of the allocation (e.g., node_hours, bytes).", example="node_hours")


class ProjectAllocation(IRIBaseModel):
    """
    A project's allocation for a capability. (aka. repo)
    This allocation is a piece of the total allocation for the capability. (eg. 5% of the total node hours of Perlmutter GPU nodes)
    A project would at least have a storage and job repos, maybe more than 1 of each.
    """

    # how much this allocation can spend
    id: str = Field(..., description="Unique identifier of the project allocation.", example="alloc-001")
    project_id: str = Field(exclude=True, description="Internal identifier of the associated project.")
    capability_id: str = Field(exclude=True, description="Internal identifier of the associated capability.")
    entries: list[AllocationEntry] = Field(..., description="Allocation entries describing usage and limits.")

    @computed_field(description="URI of the associated project resource")
    @property
    def project_uri(self) -> str:
        """Return the URI for the associated project resource."""
        return f"{config.API_URL_ROOT}{config.API_PREFIX}{config.API_URL}/account/projects/{self.project_id}"

    @computed_field(description="URI of the associated capability resource")
    @property
    def capability_uri(self) -> str:
        """Return the URI for the associated capability."""
        return f"{config.API_URL_ROOT}{config.API_PREFIX}{config.API_URL}/account/capabilities/{self.capability_id}"


class UserAllocation(IRIBaseModel):
    """
    A user's allcation in a project.
    This allocation is a piece of the project's allocation.
    """

    id: str = Field(..., description="Unique identifier of the user allocation.", example="user-alloc-42")
    project_id: str = Field(exclude=True, description="Internal identifier of the associated project.")
    project_allocation_id: str = Field(exclude=True, description="Internal identifier of the associated project allocation.")
    user_id: str = Field(..., description="Identifier of the user receiving this allocation.", example="user-123")
    entries: list[AllocationEntry] = Field(..., description="Allocation entries describing usage and limits.")

    @computed_field(description="URI of the associated project allocation")
    @property
    def project_allocation_uri(self) -> str:
        """Return the URI for the associated project allocation."""
        return f"{config.API_URL_ROOT}{config.API_PREFIX}{config.API_URL}/account/projects/{self.project_id}/project_allocations/{self.project_allocation_id}"
