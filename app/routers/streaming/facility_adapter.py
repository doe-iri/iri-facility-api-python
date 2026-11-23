import datetime
from abc import abstractmethod

from fastapi import HTTPException

from ...types.user import User
from ..iri_router import AuthenticatedAdapter
from ..status import models as status_models
from . import models as streaming_models


class FacilityAdapter(AuthenticatedAdapter):
    """
    Facility-specific streaming transport adapter (rfc-streaming-data-transport.md).
    Use the `IRI_API_ADAPTER_streaming` environment variable to install your
    facility adapter before the API starts.

    The adapter owns the control-plane service credential, admission control
    (RFC section 6.4), finite expiry (6.5), accounting and reconciliation (6.6),
    and project visibility. Every per-reservation method returns None when the
    reservation does not exist or is not visible to `user`; the router maps that
    to 404 so other projects' reservations are never revealed.

    Raise HTTPException for the RFC section 7.6 conditions: 403 (not authorized
    for the project, or no allocation), 409 (allocation limit, or the reservation
    has ended), 503 with Retry-After (no free instance, control plane down).
    Never log the reservation credential or the control-plane credential.
    """

    @abstractmethod
    async def create_reservation(
        self,
        resource: status_models.Resource,
        user: User,
        request: streaming_models.StreamReservationRequest,
    ) -> streaming_models.StreamReservation:
        """Admit, reserve an instance, mint a reservation-scoped credential, and return the
        reservation with `connection.token` (and `uri`, if any) set."""

    @abstractmethod
    async def list_reservations(
        self,
        resource: status_models.Resource,
        user: User,
        project_id: str | None,
        state: streaming_models.ReservationState | None,
        modified_since: datetime.datetime | None,
    ) -> list[streaming_models.StreamReservation]:
        """Return reservations on `resource` visible to `user`, optionally filtered."""

    @abstractmethod
    async def get_reservation(
        self,
        resource: status_models.Resource,
        user: User,
        reservation_id: str,
    ) -> streaming_models.StreamReservation | None:
        """Return one reservation, or None."""

    async def update_reservation(
        self,
        resource: status_models.Resource,
        user: User,
        reservation_id: str,
        patch: streaming_models.StreamReservationPatch,
    ) -> streaming_models.StreamReservation | None:
        """Extend `until` (admission applies to the added duration) and/or replace the sender
        allow-list. SHOULD be implemented; the default reports it as unsupported."""
        raise HTTPException(status_code=501, detail="Updating stream reservations is not supported by this facility.")

    @abstractmethod
    async def get_reservation_status(
        self,
        resource: status_models.Resource,
        user: User,
        reservation_id: str,
    ) -> streaming_models.StreamReservationStatus | None:
        """Read live status from the control plane, or None."""

    async def rotate_credential(
        self,
        resource: status_models.Resource,
        user: User,
        reservation_id: str,
    ) -> streaming_models.ConnectionBundle | None:
        """Issue a new reservation credential, revoke the previous one, and return the new
        connection bundle. MAY be implemented; set `StreamReservation.credential_rotation`
        when it is, so the HAL link is advertised."""
        raise HTTPException(status_code=501, detail="Rotating stream reservation credentials is not supported by this facility.")

    @abstractmethod
    async def release_reservation(
        self,
        resource: status_models.Resource,
        user: User,
        reservation_id: str,
    ) -> streaming_models.StreamReservation | None:
        """Revoke the credential and free the instance. Idempotent: releasing an ended
        reservation succeeds. Return the reservation, or None if it is not visible."""
