from fastapi import Request
from abc import ABC, abstractmethod
from ..status import models as status_models
from ..account import models as account_models
from . import models as compute_models


class FacilityAdapter(ABC):
    """
    Facility-specific code is handled by the implementation of this interface.
    Use the `IRI_API_ADAPTER` environment variable (defaults to `app.demo_adapter.FacilityAdapter`) 
    to install your facility adapter before the API starts.
    """


    @abstractmethod
    def get_current_user(
        self : "FacilityAdapter",
        request: Request,
        api_key: str
        ) -> str:
        """
            Decode the api_key and return the authenticated user's id.
            This method is not called directly, rather authorized endpoints "depend" on it.
            (https://fastapi.tiangolo.com/tutorial/dependencies/)
        """
        pass


    @abstractmethod
    def get_user(
        self : "FacilityAdapter",
        request: Request,
        user_id: str
        ) -> account_models.User:
        pass


    @abstractmethod
    def submit_job(
        self: "FacilityAdapter",
        resource: status_models.Resource, 
        user: account_models.User, 
        job_spec: compute_models.JobSpec,
    ) -> compute_models.Job:
        pass


    @abstractmethod
    def update_job(
        self: "FacilityAdapter",
        resource: status_models.Resource, 
        user: account_models.User, 
        job_spec: compute_models.JobSpec,
        job_id: str,
    ) -> compute_models.Job:
        pass


    @abstractmethod
    def get_job(
        self: "FacilityAdapter",
        resource: status_models.Resource, 
        user: account_models.User, 
        job_id: str,
    ) -> compute_models.Job:
        pass

    
    @abstractmethod
    def get_jobs(
        self: "FacilityAdapter",
        resource: status_models.Resource, 
        user: account_models.User, 
        offset : int,
        limit : int,
        filters: dict[str, object] | None = None,
    ) -> list[compute_models.Job]:
        pass

    
    @abstractmethod
    def cancel_job(
        self: "FacilityAdapter",
        resource: status_models.Resource, 
        user: account_models.User, 
        job_id: str,
    ) -> bool:
        pass
