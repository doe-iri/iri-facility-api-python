"""Unit tests for the S3DFAuthenticatedAdapter mixin."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.s3df.auth.authenticated_adapter import S3DFAuthenticatedAdapter


class _Adapter(S3DFAuthenticatedAdapter):
    """Concrete instantiation of the mixin for testing."""


@pytest.fixture
def adapter():
    return _Adapter()


@pytest.mark.asyncio
async def test_returns_username_when_jwt_and_coact_pass(adapter):
    verifier = MagicMock()
    verifier.verify = AsyncMock(return_value="amithm")
    coact = MagicMock()
    coact.get_user = AsyncMock(return_value={"username": "amithm"})

    with patch("app.s3df.auth.authenticated_adapter.get_jwt_verifier", return_value=verifier), \
         patch("app.s3df.auth.authenticated_adapter.get_coact_client", return_value=coact):
        result = await adapter.get_current_user("Bearer some.jwt.token", "10.0.0.1")

    assert result == "amithm"
    verifier.verify.assert_awaited_once_with("some.jwt.token")
    coact.get_user.assert_awaited_once_with("amithm")


@pytest.mark.asyncio
async def test_strips_bearer_prefix(adapter):
    verifier = MagicMock()
    verifier.verify = AsyncMock(return_value="user")
    coact = MagicMock()
    coact.get_user = AsyncMock(return_value={"username": "user"})

    with patch("app.s3df.auth.authenticated_adapter.get_jwt_verifier", return_value=verifier), \
         patch("app.s3df.auth.authenticated_adapter.get_coact_client", return_value=coact):
        await adapter.get_current_user("Bearer raw_token", None)

    verifier.verify.assert_awaited_once_with("raw_token")


@pytest.mark.asyncio
async def test_accepts_token_without_bearer_prefix(adapter):
    verifier = MagicMock()
    verifier.verify = AsyncMock(return_value="user")
    coact = MagicMock()
    coact.get_user = AsyncMock(return_value={"username": "user"})

    with patch("app.s3df.auth.authenticated_adapter.get_jwt_verifier", return_value=verifier), \
         patch("app.s3df.auth.authenticated_adapter.get_coact_client", return_value=coact):
        await adapter.get_current_user("raw_token", None)

    verifier.verify.assert_awaited_once_with("raw_token")


@pytest.mark.asyncio
async def test_missing_authorization_raises_401(adapter):
    with pytest.raises(HTTPException) as exc:
        await adapter.get_current_user("", None)
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_jwt_verify_failure_propagates(adapter):
    verifier = MagicMock()
    verifier.verify = AsyncMock(side_effect=HTTPException(status_code=401, detail="Invalid token"))

    with patch("app.s3df.auth.authenticated_adapter.get_jwt_verifier", return_value=verifier):
        with pytest.raises(HTTPException) as exc:
            await adapter.get_current_user("Bearer bad.token", None)

    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_coact_membership_miss_raises_403(adapter):
    verifier = MagicMock()
    verifier.verify = AsyncMock(return_value="ghost_user")
    coact = MagicMock()
    coact.get_user = AsyncMock(return_value=None)

    with patch("app.s3df.auth.authenticated_adapter.get_jwt_verifier", return_value=verifier), \
         patch("app.s3df.auth.authenticated_adapter.get_coact_client", return_value=coact):
        with pytest.raises(HTTPException) as exc:
            await adapter.get_current_user("Bearer good.jwt", None)

    assert exc.value.status_code == 403
    assert "not authorized" in exc.value.detail.lower()
