from app.s3df.clients.coact import CoactClient
from fastapi import HTTPException

class CoactAuthProvider:
    """Temporary whitelist-based auth: user must exist in coact."""
    def __init__(self, coact_client: CoactClient):
        self.coact_client = coact_client

    async def validate_user(self, user_id: str) -> None:
        coact_user = await self.coact_client.get_user(user_id)
        if not coact_user:
            raise HTTPException(status_code=403, detail="User not authorized")



