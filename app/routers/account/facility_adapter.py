from abc import abstractmethod
from . import models as account_models
from ..common import Capability
from ..iri_router import AuthenticatedAdapter


class FacilityAdapter(AuthenticatedAdapter):
    """
    Facility-specific code is handled by the implementation of this interface.
    Use the `IRI_API_ADAPTER` environment variable (defaults to `app.demo_adapter.FacilityAdapter`) 
    to install your facility adapter before the API starts.
    """

    @abstractmethod
    async def get_capabilities(
        self : "FacilityAdapter",
        ) -> list[Capability]:
        pass


    @abstractmethod
    async def get_projects(
        self : "FacilityAdapter",
        user: account_models.User
        ) -> list[account_models.Project]:
        pass


    @abstractmethod
    async def get_project_allocations(
        self : "FacilityAdapter",
        project: account_models.Project,
        user: account_models.User
        ) -> list[account_models.ProjectAllocation]:
        pass


    @abstractmethod
    async def get_user_allocations(
        self : "FacilityAdapter",
        user: account_models.User,
        project_allocation: account_models.ProjectAllocation,
        ) -> list[account_models.UserAllocation]:
        pass
