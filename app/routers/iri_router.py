import os
import logging
import importlib
from fastapi import Request, Depends, HTTPException, APIRouter
from fastapi.security import APIKeyHeader

bearer_token = APIKeyHeader(name="Authorization")

class IriRouter(APIRouter):
    def __init__(self, router_adapter=None, **kwargs):
        super().__init__(**kwargs)
        self.create_adapter(router_adapter)


    def create_adapter(self, router_adapter):
        # Load the facility-specific adapter
        router_name = self.prefix.replace("/", "").strip()

        # find and load the actual implementation
        adapter_name = os.environ.get(f"IRI_API_ADAPTER_{router_name}", "app.demo_adapter.DemoAdapter")
        logging.getLogger().info(f"Using {router_name} adapter: {adapter_name}")
        parts = adapter_name.rsplit(".", 1)
        module = importlib.import_module(parts[0])    
        AdapterClass = getattr(module, parts[1])
        if not issubclass(AdapterClass, router_adapter):
            raise Exception(f"{adapter_name} should implement FacilityAdapter")
        logging.getLogger().info(f"\tSuccessfully loaded {router_name} adapter.")

        # assign it
        self.adapter = AdapterClass()


    def current_user(
        self,
        request : Request, 
        api_key: str = Depends(bearer_token),
    ):
        user_id = None
        try:
            user_id = self.adapter.get_current_user(request, api_key)
        except Exception as exc:
            logging.getLogger().error(f"Error parsing IRI_API_PARAMS: {exc}")
        if not user_id:
            raise HTTPException(status_code=403, detail="Unauthorized access")
        request.state.current_user_id = user_id
