from enum import Enum
from typing import Annotated, Any
from ...types.base import IRIBaseModel

from pydantic import Field, StringConstraints, field_validator

# --- Shared types -----------------------------------------------------------

# Kubernetes DNS-1123 label rules. Provider-specific naming rules belong in the adapter.
UrlSafeName = Annotated[
    str,
    StringConstraints(min_length=1, max_length=63, pattern=r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$"),
]

# Opaque provider-assigned identifier. The router must never parse or validate its format.
OpaqueId = Annotated[str, StringConstraints(min_length=1, max_length=255)]


# --- Servers ----------------------------------------------------------------

class ServerCapabilities(IRIBaseModel):
    supports_projects: bool = Field(
        description="Whether this server has a project (grouping) concept."
    )
    project_required_for_namespace: bool = Field(
        description="If true, namespace creation requires project_id."
    )
    supports_kubeconfig: bool = Field(
        description="Whether a kubeconfig can be generated for this server."
    )


class Server(IRIBaseModel):
    id: UrlSafeName
    display_name: str
    labels: dict[str, str] = Field(
        default_factory=dict, description="Generic labels, e.g. environment=prod."
    )
    capabilities: ServerCapabilities


class ServerList(IRIBaseModel):
    items: list[Server]


# --- Clusters ---------------------------------------------------------------

class ClusterState(str, Enum):
    ACTIVE = "active"
    PROVISIONING = "provisioning"
    UPDATING = "updating"
    UNAVAILABLE = "unavailable"
    ERROR = "error"
    UNKNOWN = "unknown"


class Cluster(IRIBaseModel):
    id: OpaqueId
    name: str
    state: ClusterState
    labels: dict[str, str] = Field(default_factory=dict)
    metadata: dict[str, str] = Field(
        default_factory=dict,
        description="Provider-specific extras. Clients must not depend on specific keys.",
    )


class ClusterList(IRIBaseModel):
    items: list[Cluster]


# --- Projects (optional grouping) --------------------------------------------

class Project(IRIBaseModel):
    id: OpaqueId
    name: str
    role: str | None = Field(default=None, description="The caller's role in this project, if known.")
    metadata: dict[str, str] = Field(default_factory=dict)


class ProjectList(IRIBaseModel):
    """An empty list is ambiguous on its own. Check the server's supports_projects capability."""
    items: list[Project]


# --- Namespaces -------------------------------------------------------------

class NamespaceCreateRequest(IRIBaseModel):
    id: UrlSafeName
    project_id: OpaqueId | None = Field(
        default=None,
        description="Required when the server's project_required_for_namespace is true.",
    )
    # Labels only, no annotations. Provider-significant keys (e.g. Rancher's project
    # annotation) must be rejected or stripped by the adapter, ideally via an allowlist.
    labels: dict[str, str] = Field(default_factory=dict)


class Namespace(IRIBaseModel):
    id: str
    cluster_id: OpaqueId
    project_id: OpaqueId | None = None
    labels: dict[str, str] = Field(default_factory=dict)
    metadata: dict[str, str] = Field(default_factory=dict)


# --- Kubeconfig -------------------------------------------------------------

class KubeconfigRequest(IRIBaseModel):
    cluster_ids: list[OpaqueId] | None = Field(
        default=None,
        description="Restrict the kubeconfig to these clusters. Omit for all accessible clusters.",
    )

    @field_validator("cluster_ids")
    @classmethod
    def _non_empty_unique(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return v
        if not v:
            raise ValueError("cluster_ids must not be empty; omit it to include all clusters")
        if len(set(v)) != len(v):
            raise ValueError("cluster_ids must not contain duplicates")
        return v


# --- Errors -----------------------------------------------------------------

class ErrorCode(str, Enum):
    """Mirrors the domain exceptions adapters raise."""
    NOT_FOUND = "not_found"
    FORBIDDEN = "forbidden"
    CONFLICT = "conflict"
    UNAVAILABLE = "unavailable"
    UNSUPPORTED = "unsupported"
    INVALID_INPUT = "invalid_input"


class ErrorResponse(IRIBaseModel):
    code: ErrorCode
    message: str
