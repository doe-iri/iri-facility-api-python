"""Models for account-related API endpoints, including users, projects, and allocations."""
import datetime
from pydantic import Field, computed_field, field_validator, model_validator

from ...request_context import get_url_prefix
from ...types.base import IRIBaseModel
from ...types.scalars import AllocationUnit, AllocationUnitValue


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
        return f"{get_url_prefix()}/account/projects/{self.id}"


class AllocationEntry(IRIBaseModel):
    """Base class for allocations."""

    allocation: float = Field(..., description="Total allocation amount granted.", example=100000.0)  # how much this allocation can spend
    usage: float = Field(..., description="Amount of allocation consumed.", example=52342.5)  # how much this allocation has spent
    unit: AllocationUnitValue = Field(..., description="DOE IRI URN for the allocation unit.", example=AllocationUnit.node_hours)


class AllocationPeriod(IRIBaseModel):
    """Optional validity window shared by project and user allocations."""

    start: datetime.datetime | None = Field(
        default=None,
        description="Time at which the allocation becomes valid. Omitted when the facility does not report a start time.",
        example="2026-01-01T00:00:00Z",
    )
    end: datetime.datetime | None = Field(
        default=None,
        description="Time at which the allocation stops being valid. Omitted when the facility does not report an end time. When both start and end are present, end is not earlier than start.",
        example="2026-12-31T23:59:59Z",
    )

    @field_validator("start", "end", mode="before")
    @classmethod
    def _norm_period_dt(cls, v):
        return cls.normalize_dt(v)

    @model_validator(mode="after")
    def _check_period_order(self):
        if self.start is not None and self.end is not None and self.end < self.start:
            raise ValueError("allocation end must not be earlier than start")
        return self


class ProjectAllocation(AllocationPeriod):
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
        return f"{get_url_prefix()}/account/projects/{self.project_id}"

    @computed_field(description="URI of the associated capability resource")
    @property
    def capability_uri(self) -> str:
        """Return the URI for the associated capability."""
        return f"{get_url_prefix()}/account/capabilities/{self.capability_id}"


class WhoAmI(IRIBaseModel):
    """The authenticated caller's username"""

    username: str = Field(..., description="Unique identifier of the authenticated user.", example="user-123")


class UserAllocation(AllocationPeriod):
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
        return f"{get_url_prefix()}/account/projects/{self.project_id}/project_allocations/{self.project_allocation_id}"
