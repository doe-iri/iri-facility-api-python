"""Models for the streaming data transport API (rfc-streaming-data-transport.md, section 7)."""

import enum
import ipaddress
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, computed_field, model_validator

from ...request_context import get_url_prefix
from ...types.base import IRIBaseModel, NamedObject
from ...types.hal import build_hal_link
from ...types.scalars import AllocationUnit, AllocationUnitValue, StrictDateTime


def _validate_sender_address(value: str) -> str:
    """Accept an IPv4/IPv6 literal (no host names) that is not a special-purpose address (RFC section 12)."""
    try:
        addr = ipaddress.ip_address(value.strip())
    except ValueError as exc:
        raise ValueError(f"'{value}' is not an IPv4 or IPv6 address literal") from exc
    if addr.is_loopback or addr.is_link_local or addr.is_multicast or addr.is_unspecified or addr.is_reserved:
        raise ValueError(f"'{value}' is a special-purpose address and cannot be a sender")
    return str(addr)


SenderAddress = Annotated[str, AfterValidator(_validate_sender_address)]


def _omit_none(value) -> bool:
    return value is None


class IpFamily(str, enum.Enum):
    """IP family of a reservation."""

    ipv4 = "ipv4"
    ipv6 = "ipv6"
    dual_stack = "dual_stack"


class ReservationState(str, enum.Enum):
    """Reservation lifecycle state (RFC section 7.5). Transitions are monotonic."""

    active = "active"
    released = "released"
    expired = "expired"
    failed = "failed"


class Severity(str, enum.Enum):
    """Severity of a control-plane health issue."""

    warning = "warning"
    error = "error"
    critical = "critical"


class StreamReservationRequest(BaseModel):
    """Request to reserve one load balancer instance against a project allocation (RFC section 7.2)."""

    model_config = ConfigDict(extra="forbid")

    project_id: str = Field(..., min_length=1, description="Project to charge. The adapter verifies the caller is authorized for it.", example="p1")
    capability_id: str | None = Field(default=None, description="Capability to charge. Required only when the Resource lists more than one Capability.", example="ejfat-lb")
    name: str = Field(..., min_length=1, max_length=64, description="Human-readable label. Not unique.", example="detector-run-42")
    until: StrictDateTime | None = Field(default=None, description="Requested end time. Defaults to now plus the Resource's default_reservation_duration.")
    sender_addresses: list[SenderAddress] = Field(default_factory=list, description="Initial sender allow-list: IPv4 or IPv6 literals.", example=["198.51.100.10"])
    ip_family: IpFamily | None = Field(default=None, description="One of the Resource's ip_families.")
    slot_strategy: str | None = Field(default=None, description="One of the Resource's slot_strategies. Default is technology-defined.", example="dynamic")


class StreamReservationPatch(BaseModel):
    """JSON Merge Patch for a reservation: extend `until` and/or replace `sender_addresses`."""

    model_config = ConfigDict(extra="forbid")

    until: StrictDateTime | None = Field(default=None, description="New end time; must be later than the current one.")
    sender_addresses: list[SenderAddress] | None = Field(default=None, description="Replacement sender allow-list. Use [] to clear it.")

    @model_validator(mode="after")
    def _check_fields(self):
        if not self.model_fields_set:
            raise ValueError("patch must set until and/or sender_addresses")
        # In merge-patch, null deletes a member; neither member can be deleted.
        for field in self.model_fields_set:
            if getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class Charge(BaseModel):
    """Amount charged so far in one allocation unit."""

    unit: AllocationUnitValue = Field(..., description="DOE IRI allocation-unit URN.", example=AllocationUnit.instance_hours)
    amount: float = Field(..., ge=0, description="Amount charged in that unit.", example=2.533333)


class ConnectionBundle(BaseModel):
    """What senders and receivers need to use a reservation (RFC section 7.4).

    `token` and `uri` are secrets: present only in the reserve and credential-rotation responses.
    Absent fields are omitted, not serialized as null.
    """

    data_ipv4_address: str | None = Field(default=None, exclude_if=_omit_none, description="Data-plane IPv4 address senders send to.")
    data_ipv6_address: str | None = Field(default=None, exclude_if=_omit_none, description="Data-plane IPv6 address senders send to.")
    data_min_port: int | None = Field(default=None, exclude_if=_omit_none, description="Lowest accepted destination UDP port.")
    data_max_port: int | None = Field(default=None, exclude_if=_omit_none, description="Highest accepted destination UDP port.")
    sync_ipv4_address: str | None = Field(default=None, exclude_if=_omit_none, description="Synchronization IPv4 address.")
    sync_ipv6_address: str | None = Field(default=None, exclude_if=_omit_none, description="Synchronization IPv6 address.")
    sync_udp_port: int | None = Field(default=None, exclude_if=_omit_none, description="Synchronization UDP port.")
    control_plane_host: str | None = Field(default=None, exclude_if=_omit_none, description="Control-plane host receivers register with.")
    control_plane_port: int | None = Field(default=None, exclude_if=_omit_none, description="Control-plane port receivers register with.")
    control_plane_tls: bool | None = Field(default=None, exclude_if=_omit_none, description="Whether the control-plane endpoint requires TLS.")
    token: str | None = Field(default=None, exclude_if=_omit_none, repr=False, description="Reservation credential. Secret; only in reserve and rotation responses.")
    token_expires_at: StrictDateTime | None = Field(default=None, exclude_if=_omit_none, description="When the credential stops working; no later than the reservation's until.")
    uri: str | None = Field(
        default=None, exclude_if=_omit_none, repr=False, description="Technology connection URI embedding the token (EJFAT: ejfat[s]://...). Secret; only in reserve and rotation responses."
    )

    def without_credential(self) -> "ConnectionBundle":
        """Copy for GET/list responses: drop the token and any URI that may embed it."""
        return self.model_copy(update={"token": None, "uri": None})


class StreamReservation(NamedObject):
    """Exclusive assignment of one load balancer instance to one project for a bounded interval (RFC section 7.3)."""

    def _self_path(self) -> str:
        return f"/streaming/{self.resource_id}/reservations/{self.id}"

    resource_id: str = Field(..., exclude=True)
    project_id: str = Field(..., exclude=True)
    capability_id: str = Field(..., exclude=True)
    project_allocation_id: str = Field(..., exclude=True)
    credential_rotation: bool = Field(default=False, exclude=True, description="Whether the adapter implements credential rotation for this reservation.")

    state: ReservationState = Field(..., description="Lifecycle state.", example="active")
    created_at: StrictDateTime = Field(..., description="Start of the charged interval.")
    until: StrictDateTime = Field(..., description="Effective scheduled end.")
    ended_at: StrictDateTime | None = Field(..., description="Actual end, or null while active.")
    sender_addresses: list[str] = Field(default_factory=list, description="Effective sender allow-list as last observed at the control plane.")
    ip_family: IpFamily | None = Field(default=None, description="Effective IP family.")
    slot_strategy: str | None = Field(default=None, description="Effective slot strategy.")
    charges: list[Charge] = Field(default_factory=list, description="Amount charged so far per allocation unit.")
    connection: ConnectionBundle = Field(..., description="Connection details. The credential is present only in reserve and rotation responses.")

    @computed_field(description="The streaming transport Resource")
    @property
    def resource_uri(self) -> str:
        return f"{get_url_prefix()}/status/resources/{self.resource_id}"

    @computed_field(description="The Project charged")
    @property
    def project_uri(self) -> str:
        return f"{get_url_prefix()}/account/projects/{self.project_id}"

    @computed_field(description="The Capability charged")
    @property
    def capability_uri(self) -> str:
        return f"{get_url_prefix()}/account/capabilities/{self.capability_id}"

    @computed_field(description="The Project Allocation charged")
    @property
    def project_allocation_uri(self) -> str:
        return f"{get_url_prefix()}/account/projects/{self.project_id}/project_allocations/{self.project_allocation_id}"

    def _extra_links(self) -> dict:
        links: dict = {}
        # Status and rotation act on the live control-plane instance, so only an active reservation offers them.
        if self.state == ReservationState.active:
            links["iri:get-stream-reservation-status"] = build_hal_link(f"{self.self_uri}/status", media_type=None)
            if self.credential_rotation:
                links["iri:rotate-stream-credential"] = build_hal_link(f"{self.self_uri}/credentials", media_type=None)
        return links


class HealthIssue(BaseModel):
    """Issue reported by the control plane."""

    severity: Severity = Field(..., description="Issue severity.")
    type: str = Field(..., description="Technology-defined issue type.")
    message: str = Field(..., description="Human-readable message.")
    detected_at: StrictDateTime | None = Field(default=None, description="When the issue was detected.")


class ReceiverCounters(BaseModel):
    """Receiver-reported counters. Informational only; never used for accounting."""

    events_received: int | None = None
    events_reassembled: int | None = None
    reassembly_errors: int | None = None
    bytes_received: int | None = None
    packets_received: int | None = None


class ReceiverStatus(BaseModel):
    """One receiver registered with the control plane."""

    session_id: str = Field(..., description="Control-plane session identifier.")
    name: str | None = Field(default=None, description="Receiver name.")
    ip_address: str = Field(..., description="Address the receiver registered.")
    udp_port: int | None = Field(default=None, description="Receiver UDP port.")
    port_range: int | None = Field(default=None, description="Technology-defined receiver port range.")
    ready: bool = Field(..., description="Whether the receiver reports ready.")
    fill_percent: float | None = Field(default=None, description="Receiver queue fill, 0 to 1.")
    control_signal: float | None = Field(default=None, description="Receiver control signal.")
    slots_assigned: int | None = Field(default=None, description="Load-balancing slots assigned.")
    last_updated: StrictDateTime | None = Field(default=None, description="When the receiver last reported state.")
    health_issues: list[HealthIssue] = Field(default_factory=list)
    counters: ReceiverCounters | None = None


class StreamReservationStatus(IRIBaseModel):
    """Live reservation status, read on demand from the control plane (RFC section 7.7)."""

    observed_at: StrictDateTime = Field(..., description="When the control plane produced this status.")
    expires_at: StrictDateTime | None = Field(default=None, description="Control-plane expiry; differs from until only during reconciliation.")
    sender_addresses: list[str] = Field(default_factory=list, description="Current allow-list at the control plane.")
    receivers: list[ReceiverStatus] = Field(default_factory=list, description="Registered receivers.")
    health_issues: list[HealthIssue] = Field(default_factory=list, description="Reservation-level issues.")
