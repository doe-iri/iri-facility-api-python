"""
Test fixtures: a self-contained RSA keypair so tests can mint and verify JWTs
without touching a real Dex/JWKS endpoint.
"""

from dataclasses import dataclass

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


@dataclass
class _KeyPair:
    private_pem: bytes
    public_pem: bytes
    public_key: object  # cryptography RSAPublicKey
    kid: str


@pytest.fixture
def rsa_keypair() -> _KeyPair:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_key = private_key.public_key()
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return _KeyPair(
        private_pem=private_pem,
        public_pem=public_pem,
        public_key=public_key,
        kid="test-kid-1",
    )


def make_token(
    keypair: _KeyPair,
    *,
    issuer: str = "https://dex.test",
    audience: str = "iri-api",
    name: str = "amithm",
    exp_offset: int = 3600,
    extra_claims: dict | None = None,
) -> str:
    """Mint a signed JWT for tests. Caller can override claims/exp."""
    import time

    now = int(time.time())
    payload = {
        "iss": issuer,
        "aud": audience,
        "exp": now + exp_offset,
        "iat": now,
        "name": name,
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(
        payload,
        keypair.private_pem,
        algorithm="RS256",
        headers={"kid": keypair.kid},
    )
