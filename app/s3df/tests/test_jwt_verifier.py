"""Unit tests for JwtVerifier — locally signed RSA JWTs, patched JWKS lookup."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.s3df.auth.jwt_verifier import JwtVerifier
from app.s3df.tests.conftest import make_token

ISSUER = "https://dex.test"
AUDIENCE = "iri-api"


def _verifier_with_key(public_key) -> JwtVerifier:
    verifier = JwtVerifier(
        jwks_url="https://dex.test/keys",
        issuer=ISSUER,
        audience=AUDIENCE,
        username_claim="name",
    )
    fake_signing_key = MagicMock()
    fake_signing_key.key = public_key
    verifier._jwks_client.get_signing_key_from_jwt = MagicMock(return_value=fake_signing_key)
    return verifier


@pytest.mark.asyncio
async def test_verify_returns_name_claim(rsa_keypair):
    verifier = _verifier_with_key(rsa_keypair.public_key)
    token = make_token(rsa_keypair, name="amithm")

    username = await verifier.verify(token)

    assert username == "amithm"
    assert isinstance(username, str)


@pytest.mark.asyncio
async def test_expired_token_raises_401(rsa_keypair):
    verifier = _verifier_with_key(rsa_keypair.public_key)
    token = make_token(rsa_keypair, exp_offset=-60)

    with pytest.raises(HTTPException) as exc:
        await verifier.verify(token)
    assert exc.value.status_code == 401
    assert "expired" in exc.value.detail.lower()


@pytest.mark.asyncio
async def test_wrong_issuer_raises_401(rsa_keypair):
    verifier = _verifier_with_key(rsa_keypair.public_key)
    token = make_token(rsa_keypair, issuer="https://attacker.example")

    with pytest.raises(HTTPException) as exc:
        await verifier.verify(token)
    assert exc.value.status_code == 401
    assert "issuer" in exc.value.detail.lower()


@pytest.mark.asyncio
async def test_wrong_audience_raises_401(rsa_keypair):
    verifier = _verifier_with_key(rsa_keypair.public_key)
    token = make_token(rsa_keypair, audience="some-other-app")

    with pytest.raises(HTTPException) as exc:
        await verifier.verify(token)
    assert exc.value.status_code == 401
    assert "audience" in exc.value.detail.lower()


@pytest.mark.asyncio
async def test_missing_name_claim_raises_401(rsa_keypair):
    verifier = _verifier_with_key(rsa_keypair.public_key)
    # Mint then strip the `name` claim by overriding with an empty value
    token = make_token(rsa_keypair, name="")

    with pytest.raises(HTTPException) as exc:
        await verifier.verify(token)
    assert exc.value.status_code == 401
    assert "name" in exc.value.detail.lower()


@pytest.mark.asyncio
async def test_jwks_client_failure_raises_401(rsa_keypair):
    from jwt import PyJWKClientError

    verifier = JwtVerifier(
        jwks_url="https://dex.test/keys",
        issuer=ISSUER,
        audience=AUDIENCE,
    )
    verifier._jwks_client.get_signing_key_from_jwt = MagicMock(
        side_effect=PyJWKClientError("kid not found")
    )
    token = make_token(rsa_keypair)

    with pytest.raises(HTTPException) as exc:
        await verifier.verify(token)
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_jwks_unreachable_raises_503(rsa_keypair):
    verifier = JwtVerifier(
        jwks_url="https://dex.test/keys",
        issuer=ISSUER,
        audience=AUDIENCE,
    )
    verifier._jwks_client.get_signing_key_from_jwt = MagicMock(
        side_effect=ConnectionError("dns failure")
    )
    token = make_token(rsa_keypair)

    with pytest.raises(HTTPException) as exc:
        await verifier.verify(token)
    assert exc.value.status_code == 503


@pytest.mark.asyncio
async def test_signature_from_different_key_raises_401(rsa_keypair):
    """Token signed by a different key — verifier holds the wrong public key."""
    from cryptography.hazmat.primitives.asymmetric import rsa

    other_private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    other_pub = other_private.public_key()

    # Verifier has a public key that does NOT match the signing key
    verifier = _verifier_with_key(other_pub)
    token = make_token(rsa_keypair)  # signed with rsa_keypair, not other_private

    with pytest.raises(HTTPException) as exc:
        await verifier.verify(token)
    assert exc.value.status_code == 401
