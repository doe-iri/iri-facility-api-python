"""Streaming data transport reservation API router (rfc-streaming-data-transport.md, section 7)."""

import datetime
from typing import Annotated

from fastapi import Body, Depends, Header, HTTPException, Query, Request, Response, status as http_status

from ...idempotency import build_body_hash, build_cache_key, run_with_idempotency
from ...types.hal import OPERATION_RELATIONS
from ...types.http import forbidExtraQueryParams, modifiedSinceDatetime
from ...types.scalars import ResourceType, urn_has_complete_prefix
from ...types.user import User
from .. import iri_router
from ..error_handlers import DEFAULT_RESPONSES
from ..iri_meta import iri_meta_dict
from ..status import models as status_models
from ..status.status import router as status_router
from . import facility_adapter, models

router = iri_router.IriRouter(
    facility_adapter.FacilityAdapter,
    prefix="/streaming",
    tags=["streaming"],
)

# The whole section is optional for a facility (RFC section 10); per-operation conformance is in each description.
_META = ("in_development", "optional")
_NO_STORE = {"Cache-Control": "no-store"}


async def _streaming_resource(resource_id: str) -> status_models.Resource:
    resource = await status_router.adapter.get_resource(resource_id)
    if not resource or not urn_has_complete_prefix(ResourceType.service_streaming_transport.value, resource.resource_type):
        raise HTTPException(status_code=404, detail="Streaming transport resource not found")
    return resource


def _check_resource_limits(
    resource: status_models.Resource,
    until: datetime.datetime | None,
    sender_addresses: list[str] | None,
    ip_family: models.IpFamily | None = None,
    slot_strategy: str | None = None,
) -> None:
    """Reject requests that the Resource's profile attributes already rule out (RFC section 7.6, 400).

    An absent attribute means "not provided", so the adapter decides. max_reservation_duration is
    left to the adapter, which also applies default_reservation_duration.
    """
    attrs = resource.attributes or {}
    if ip_family and "ip_families" in attrs and ip_family.value not in attrs["ip_families"]:
        raise HTTPException(status_code=400, detail=f"ip_family '{ip_family.value}' is not supported by this resource")
    if slot_strategy and "slot_strategies" in attrs and slot_strategy not in attrs["slot_strategies"]:
        raise HTTPException(status_code=400, detail=f"slot_strategy '{slot_strategy}' is not supported by this resource")
    max_senders = attrs.get("max_senders_per_reservation")
    if sender_addresses is not None and max_senders is not None and len(sender_addresses) > max_senders:
        raise HTTPException(status_code=400, detail=f"At most {max_senders} sender addresses are allowed")
    if until is not None and until <= datetime.datetime.now(datetime.timezone.utc):
        raise HTTPException(status_code=400, detail="until must be in the future")


def _not_found() -> HTTPException:
    return HTTPException(status_code=404, detail="Reservation not found")


def _public(reservation: models.StreamReservation) -> models.StreamReservation:
    """Strip the credential: GET, list, and PATCH responses never carry it (RFC section 7.4)."""
    return reservation.model_copy(update={"connection": reservation.connection.without_credential()})


@router.post(
    "/{resource_id}/reservations",
    summary="Reserve a load balancer instance",
    description=(
        "Reserve one load balancer instance of the streaming transport Resource, charged to a project allocation. "
        "Returns 201 with the reservation, including the reservation credential (returned only here and on rotation), "
        "and a Location header. Fails with 403 if the caller may not charge the project, 409 if an allocation limit "
        "is reached, and 503 if no instance is free.\n\n"
        "- **Idempotency-Key**: optional client-generated UUID. A retry with the same key and body returns the "
        "original reservation instead of reserving, and charging for, a second instance.\n\n"
        "Conformance: MUST when the streaming section is implemented."
    ),
    status_code=http_status.HTTP_201_CREATED,
    response_model=models.StreamReservation,
    response_model_exclude_unset=True,
    responses=DEFAULT_RESPONSES,
    operation_id="createStreamReservation",
    openapi_extra=iri_meta_dict(*_META, relations=[OPERATION_RELATIONS["create-stream-reservation"]]),
)
async def create_reservation(
    resource_id: str,
    reservation_request: models.StreamReservationRequest,
    request: Request,
    response: Response,
    user: User = Depends(router.current_user),
    _forbid=Depends(forbidExtraQueryParams()),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    resource = await _streaming_resource(resource_id)
    rr = reservation_request
    _check_resource_limits(resource, rr.until, rr.sender_addresses, rr.ip_family, rr.slot_strategy)

    def adapter_fn():
        return router.adapter.create_reservation(resource=resource, user=user, request=rr)

    if idempotency_key:
        return await run_with_idempotency(
            request.app.state.idempotency_store,
            build_cache_key(user.id, idempotency_key, f"create_stream_reservation:{resource_id}"),
            build_body_hash(rr.model_dump(mode="json")),
            adapter_fn,
            status_code=http_status.HTTP_201_CREATED,
            headers_fn=lambda body: {"Location": body["self_uri"], **_NO_STORE},
        )
    reservation = await adapter_fn()
    response.headers["Location"] = reservation.self_uri
    response.headers.update(_NO_STORE)
    return reservation


@router.get(
    "/{resource_id}/reservations",
    summary="List stream reservations",
    description="List reservations on the streaming transport Resource that are visible to the caller. Never includes credentials.\n\nConformance: MUST.",
    response_model=list[models.StreamReservation],
    response_model_exclude_unset=True,
    responses=DEFAULT_RESPONSES,
    operation_id="listStreamReservations",
    openapi_extra=iri_meta_dict(*_META, relations=[OPERATION_RELATIONS["query-stream-reservations"]]),
)
async def list_reservations(
    resource_id: str,
    request: Request,
    project_id: Annotated[str | None, Query(description="Only reservations charged to this project")] = None,
    state: Annotated[models.ReservationState | None, Query(description="Only reservations in this state")] = None,
    modified_since: Annotated[str | None, Query(description="Only reservations modified at or after this ISO 8601 time")] = None,
    user: User = Depends(router.current_user),
    _forbid=Depends(forbidExtraQueryParams("project_id", "state", "modified_since")),
):
    resource = await _streaming_resource(resource_id)
    reservations = await router.adapter.list_reservations(
        resource=resource,
        user=user,
        project_id=project_id,
        state=state,
        modified_since=modifiedSinceDatetime(modified_since, None),
    )
    return [_public(r) for r in reservations]


@router.get(
    "/{resource_id}/reservations/{reservation_id}",
    summary="Get a stream reservation",
    description="Get one reservation. Never includes the credential.\n\nConformance: MUST.",
    response_model=models.StreamReservation,
    response_model_exclude_unset=True,
    responses=DEFAULT_RESPONSES,
    operation_id="getStreamReservation",
    openapi_extra=iri_meta_dict(*_META),
)
async def get_reservation(
    resource_id: str,
    reservation_id: str,
    request: Request,
    user: User = Depends(router.current_user),
    _forbid=Depends(forbidExtraQueryParams()),
):
    resource = await _streaming_resource(resource_id)
    reservation = await router.adapter.get_reservation(resource=resource, user=user, reservation_id=reservation_id)
    if reservation is None:
        raise _not_found()
    return _public(reservation)


@router.patch(
    "/{resource_id}/reservations/{reservation_id}",
    summary="Extend a stream reservation or replace its senders",
    description=(
        "JSON Merge Patch: extend `until` and/or replace `sender_addresses`. Admission control applies to the added "
        "duration; 409 if the allocation cannot cover it or the reservation has ended.\n\nConformance: SHOULD."
    ),
    response_model=models.StreamReservation,
    response_model_exclude_unset=True,
    responses=DEFAULT_RESPONSES,
    operation_id="updateStreamReservation",
    openapi_extra=iri_meta_dict(*_META),
)
async def update_reservation(
    resource_id: str,
    reservation_id: str,
    patch: Annotated[models.StreamReservationPatch, Body(media_type="application/merge-patch+json")],
    request: Request,
    user: User = Depends(router.current_user),
    _forbid=Depends(forbidExtraQueryParams()),
):
    resource = await _streaming_resource(resource_id)
    _check_resource_limits(resource, patch.until, patch.sender_addresses)
    reservation = await router.adapter.update_reservation(resource=resource, user=user, reservation_id=reservation_id, patch=patch)
    if reservation is None:
        raise _not_found()
    return _public(reservation)


@router.get(
    "/{resource_id}/reservations/{reservation_id}/status",
    summary="Get live stream reservation status",
    description="Live status read from the control plane: senders, registered receivers, and health issues.\n\nConformance: MUST.",
    response_model=models.StreamReservationStatus,
    response_model_exclude_unset=True,
    responses=DEFAULT_RESPONSES,
    operation_id="getStreamReservationStatus",
    openapi_extra=iri_meta_dict(*_META, relations=[OPERATION_RELATIONS["get-stream-reservation-status"]]),
)
async def get_reservation_status(
    resource_id: str,
    reservation_id: str,
    request: Request,
    user: User = Depends(router.current_user),
    _forbid=Depends(forbidExtraQueryParams()),
):
    resource = await _streaming_resource(resource_id)
    status = await router.adapter.get_reservation_status(resource=resource, user=user, reservation_id=reservation_id)
    if status is None:
        raise _not_found()
    return status


@router.post(
    "/{resource_id}/reservations/{reservation_id}/credentials",
    summary="Rotate the stream reservation credential",
    description=(
        "Issue a new reservation credential and revoke the previous one. Returns the new connection bundle, "
        "including the credential. Rotation may disconnect registered receivers.\n\nConformance: MAY."
    ),
    response_model=models.ConnectionBundle,
    responses=DEFAULT_RESPONSES,
    operation_id="rotateStreamReservationCredential",
    openapi_extra=iri_meta_dict(*_META, relations=[OPERATION_RELATIONS["rotate-stream-credential"]]),
)
async def rotate_credential(
    resource_id: str,
    reservation_id: str,
    request: Request,
    response: Response,
    user: User = Depends(router.current_user),
    _forbid=Depends(forbidExtraQueryParams()),
):
    resource = await _streaming_resource(resource_id)
    bundle = await router.adapter.rotate_credential(resource=resource, user=user, reservation_id=reservation_id)
    if bundle is None:
        raise _not_found()
    response.headers.update(_NO_STORE)
    return bundle


@router.delete(
    "/{resource_id}/reservations/{reservation_id}",
    summary="Release a stream reservation",
    description="Revoke the credential and free the instance. Idempotent: releasing an ended reservation returns 204.\n\nConformance: MUST.",
    status_code=http_status.HTTP_204_NO_CONTENT,
    response_model=None,
    responses=DEFAULT_RESPONSES,
    operation_id="releaseStreamReservation",
    openapi_extra=iri_meta_dict(*_META),
)
async def release_reservation(
    resource_id: str,
    reservation_id: str,
    request: Request,
    user: User = Depends(router.current_user),
    _forbid=Depends(forbidExtraQueryParams()),
):
    resource = await _streaming_resource(resource_id)
    if await router.adapter.release_reservation(resource=resource, user=user, reservation_id=reservation_id) is None:
        raise _not_found()
    return None
