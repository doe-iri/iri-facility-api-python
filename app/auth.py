from fastapi import Request, Depends, HTTPException
from fastapi.security import APIKeyHeader
import logging


bearer_token = APIKeyHeader(name="Authorization")


def current_user(
    request : Request, 
    api_key: str = Depends(bearer_token),
):
    user_id = None
    try:
        user_id = request.app.state.adapter.get_current_user(request, api_key)
    except Exception as exc:
        logging.getLogger().error(f"Error parsing IRI_API_PARAMS: {exc}")
    if not user_id:
        raise HTTPException(status_code=403, detail="Unauthorized access")
    request.state.current_user_id = user_id
