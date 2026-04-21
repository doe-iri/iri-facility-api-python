"""
Shared S3DF auth mixin.

Provides a single concrete `get_current_user` for every S3DF facility adapter:
verify the Bearer JWT against Dex JWKS, then check CoAct membership. Adapters
inherit from this mixin instead of carrying any auth state of their own.
"""

from fastapi import HTTPException

from app.s3df.auth.jwt_verifier import ensure_pinned_key_refresh_started, get_jwt_verifier
from app.s3df.clients import get_coact_client
from app.s3df.config import settings

# Bootstrap the pinned Dex key + start the background refresh thread at module
# import time. Adapters are instantiated while routers are being imported
# (before uvicorn starts the event loop), so this runs before the first client
# request and has the cache warm by then. No-op when DEX_JWT_PUBLIC_KEY is unset.
if settings.dex_jwt_public_key:
    ensure_pinned_key_refresh_started()


class S3DFAuthenticatedAdapter:
    """Mixin: implements AuthenticatedAdapter.get_current_user via Dex JWT + CoAct."""

    async def get_current_user(self, api_key: str, client_ip: str | None) -> str:
        if not api_key:
            raise HTTPException(status_code=401, detail="Missing Authorization header")

        token = api_key[7:] if api_key.startswith("Bearer ") else api_key
        username = await get_jwt_verifier().verify(token)

        coact_user = await get_coact_client().get_user(username)
        if not coact_user:
            raise HTTPException(status_code=403, detail="User not authorized")

        return username
