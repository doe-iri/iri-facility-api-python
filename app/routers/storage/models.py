"""Models for storage location and mount API endpoints."""
from enum import Enum
from pydantic import Field, BaseModel
from typing import Optional


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


class AccessProtocol(str, Enum):
    """Supported data access protocols."""
    globus = "globus"
    xrootd = "xrootd"
    s3 = "s3"


class AccessCapability(str, Enum):
    """Data operations supported by an access endpoint."""
    list = "list"
    read = "read"
    write = "write"
    transfer = "transfer"
    streaming = "streaming"


class AccessEndpoint(BaseModel):
    """
    A single data access endpoint for a storage resource.
    Protocol-specific connection fields are present only for the relevant protocol.
    """
    id: str = Field(..., description="Unique identifier for this access endpoint", example="globus-cfs-demo")
    resource_id: str = Field(..., description="ID of the storage resource this endpoint belongs to")
    protocol: AccessProtocol = Field(..., description="Data access protocol")
    display_name: Optional[str] = Field(default=None, description="Human-readable name for this endpoint", example="Demo CFS Globus")
    auth_type: str = Field(..., description="Authentication mechanism required to use this endpoint", example="globus")
    capabilities: list[AccessCapability] = Field(..., description="Supported data operations")
    # Globus-specific
    endpoint_id: Optional[str] = Field(default=None, description="Globus endpoint UUID (Globus only)", example="5e0cdbd2-3f1a-4e57-beed-b95scbb83b7c")
    uri: Optional[str] = Field(default=None, description="Full Globus URI (Globus only)", example="globus://5e0cdbd2-3f1a-4e57-beed-b95scbb83b7c/")
    root_path: Optional[str] = Field(default=None, description="Root path within the endpoint (Globus only)", example="/")
    # XRootD-specific
    endpoint: Optional[str] = Field(default=None, description="XRootD server address (XRootD only)", example="root://cfs.demo.example/")
    # S3-specific
    bucket: Optional[str] = Field(default=None, description="S3 bucket name (S3 only)", example="demo-cfs")
    region: Optional[str] = Field(default=None, description="AWS region (S3 only)", example="us-east-1")
    endpoint_url: Optional[str] = Field(default=None, description="S3-compatible endpoint URL for non-AWS providers (S3 only)", example="https://s3.demo.example")
