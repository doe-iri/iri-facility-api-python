"""HTTP-related types and utilities for the IRI Facility API"""
import datetime
from email.utils import parsedate_to_datetime
from urllib.parse import parse_qs

from fastapi import HTTPException, Request, status

from .scalars import StrictDateTime

# -----------------------------------------------------------------------
# modifiedSinceDatetime: combine modified_since (ISO8601) and If-Modified-Since (RFC1123)
# If both are provided, the most recent timestamp is used. Strict validation is applied to both formats.
# modified_since must be a valid ISO8601 datetime string.
# If-Modified-Since must be a valid RFC1123 datetime string.
# TODO: If-Modified-Since is not yet supported/used by the API.

def modifiedSinceDatetime(
    modified_since: str | None,
    header_modified_since: str | None
) -> datetime.datetime | None:
    """
    Combine modified_since (ISO8601) and If-Modified-Since (RFC1123).
    If both are provided, the most recent timestamp is used.
    """

    parsed_times: list[datetime.datetime] = []

    # Query param (ISO 8601)
    if modified_since is not None:
        try:
            dt = StrictDateTime.validate(modified_since)
            parsed_times.append(dt)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid modified_since query param: {exc}",
            ) from exc

    # Header (RFC 1123)
    if header_modified_since is not None:
        try:
            dt = parsedate_to_datetime(header_modified_since)
            if dt is None:
                raise ValueError("Invalid RFC1123 date")
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=datetime.timezone.utc)
            parsed_times.append(dt.astimezone(datetime.timezone.utc))
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid If-Modified-Since header format (must be RFC1123)",
            ) from exc

    if not parsed_times:
        return None

    # Stricter constraint wins
    return max(parsed_times)

# -----------------------------------------------------------------------
# forbidExtraQueryParams: a dependency to forbid extra query parameters

def forbidExtraQueryParams(*allowedParams: str, multiParams: set[str] | None = None):
    """Dependency to forbid extra query parameters. If allowedParams contains "*", all params are allowed."""
    multiParams = multiParams or set()

    async def checker(req: Request):
        if "*" in allowedParams:
            return

        raw_qs = req.scope.get("query_string", b"")
        parsed = parse_qs(raw_qs.decode("utf-8", errors="strict"), keep_blank_values=True)

        allowed = set(allowedParams)

        for key, values in parsed.items():
            if key not in allowed:
                raise HTTPException(status_code=422,
                                    detail=[{"type": "extra_forbidden",
                                             "loc": ["query", key],
                                             "msg": f"Unexpected query parameter: {key}"}])


            if len(values) > 1 and key not in multiParams:
                raise HTTPException(status_code=422,
                                    detail=[{"type": "duplicate_forbidden",
                                             "loc": ["query", key],
                                             "msg": f"Duplicate query parameter: {key}"}])

    return checker
