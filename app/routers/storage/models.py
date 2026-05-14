"""Models for storage location and mount API endpoints."""
from enum import Enum
from pydantic import Field, BaseModel


class LogicalName(str, Enum):
    """Well-known logical filesystem tier names across HPC facilities."""
    home = "home"
    scratch = "scratch"
    project = "project"
    campaign = "campaign"
    archive = "archive"
    shared = "shared"
    temporary = "temporary"


class StorageIntent(str, Enum):
    """Intended use hint to filter returned storage locations."""
    read = "read"
    write = "write"
    staging = "staging"
    long_term_storage = "long-term-storage"


class AccessPermissions(BaseModel):
    """POSIX-style access permissions for a storage location."""
    read: bool = Field(..., description="Read permission", example=True)
    write: bool = Field(..., description="Write permission", example=True)
    execute: bool = Field(..., description="Execute/traverse permission", example=True)


class StorageInstance(BaseModel):
    """
    A concrete storage instance visible through a resource for a given logical filesystem tier.
    """
    logical_name: LogicalName = Field(
        ...,
        description="Logical filesystem tier name",
        example="scratch",
    )
    path: str = Field(
        ...,
        description="Absolute resolved path for this user at the resource",
        example="/pscratch/sd/j/jbalcas",
    )
    filesystem: str | None = Field(
        default=None,
        description="Underlying filesystem type or label",
        example="lustre-scratch",
    )
    performance_tier: str | None = Field(
        default=None,
        description="Performance tier classification (high / medium / low / tape)",
        example="high",
    )
    quota_bytes: int | None = Field(
        default=None,
        description="Total quota in bytes (None = unlimited or unknown)",
        example=5000000000000,
    )
    available_bytes: int | None = Field(
        default=None,
        description="Available bytes remaining within the quota",
        example=4200000000000,
    )
    purge_policy_days: int | None = Field(
        default=None,
        description="Days of inactivity before automatic purge; None means no purge policy",
        example=30,
    )
    shared: bool = Field(
        default=False,
        description="True if the path is shared across multiple users or projects",
        example=False,
    )
    access: AccessPermissions = Field(
        ...,
        description="Access permissions through the queried resource context",
    )
