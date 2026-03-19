from typing import Protocol

class S3DFAuthProvider(Protocol):
    """Auth mechanism abstraction — swap this to change from whitelist to token introspection."""
    async def validate_user(self, user_id: str) -> None:
        """Raises HTTPException(403) if user is not authorized."""
        ...
