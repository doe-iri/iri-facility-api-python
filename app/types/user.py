from pydantic import Field
from ..types.base import IRIBaseModel


class User(IRIBaseModel):
    """A user of the facility"""

    id: str = Field(..., description="Unique identifier of the user.", example="user-123")
    name: str = Field(..., description="Name of the user.", example="Jane Doe")
    api_key: str = Field(..., description="API key associated with this user.", example="AKIAIOSFODNN7EXAMPLE")
    client_ip: str|None = Field(default=None, description="IP address from which the user connects.", example="192.0.2.10")
    # we could expose more fields here (eg. email) but it might be against policy