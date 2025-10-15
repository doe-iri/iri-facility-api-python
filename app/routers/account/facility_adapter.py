from fastapi import Request
from abc import ABC, abstractmethod
from . import models as account_models


class FacilityAdapter(ABC):
    """
    Facility-specific code is handled by the implementation of this interface.
    Use the `IRI_API_ADAPTER` environment variable (defaults to `app.demo_adapter.FacilityAdapter`) 
    to install your facility adapter before the API starts.
    """

    @abstractmethod
    def get_capabilities(
        self : "FacilityAdapter",
        ) -> list[account_models.Capability]:
        pass


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
    def get_projects(
        self : "FacilityAdapter",
        request: Request,
        user: account_models.User
        ) -> list[account_models.Project]:
        pass


    @abstractmethod
    def get_project_allocations(
        self : "FacilityAdapter",
        request: Request,
        project: account_models.Project,
        user: account_models.User
        ) -> list[account_models.ProjectAllocation]:
        pass


    @abstractmethod
    def get_user_allocations(
        self : "FacilityAdapter",
        request: Request,
        user: account_models.User,
        project_allocation: account_models.ProjectAllocation,
        ) -> list[account_models.UserAllocation]:
        pass
