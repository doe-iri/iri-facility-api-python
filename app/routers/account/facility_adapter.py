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
        api_key: str,
        ip_address: str|None,
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
        user_id: str,
        api_key: str,
        ) -> account_models.User:
        pass


    @abstractmethod
    def get_projects(
        self : "FacilityAdapter",
        user: account_models.User
        ) -> list[account_models.Project]:
        pass


    @abstractmethod
    def get_project_allocations(
        self : "FacilityAdapter",
        project: account_models.Project,
        user: account_models.User
        ) -> list[account_models.ProjectAllocation]:
        pass


    @abstractmethod
    def get_user_allocations(
        self : "FacilityAdapter",
        user: account_models.User,
        project_allocation: account_models.ProjectAllocation,
        ) -> list[account_models.UserAllocation]:
        pass
