from abc import abstractmethod
from . import models as task_models
from ..account import models as account_models
from ..status import models as status_models
from ..iri_router import AuthenticatedAdapter


class FacilityAdapter(AuthenticatedAdapter):
    """
    Facility-specific code is handled by the implementation of this interface.
    Use the `IRI_API_ADAPTER` environment variable (defaults to `app.demo_adapter.FacilityAdapter`) 
    to install your facility adapter before the API starts.
    """


    @abstractmethod
    async def get_task(
        self : "FacilityAdapter",
        user: account_models.User, 
        task_id: str,
        ) -> task_models.Task|None:
        pass


    @abstractmethod
    async def get_tasks(
        self : "FacilityAdapter",
        user: account_models.User, 
        ) -> list[task_models.Task]:
        pass


    @abstractmethod
    async def put_task(
        self: "FacilityAdapter",
        user: account_models.User,
        resource: status_models.Resource|None,
        command: task_models.TaskCommand
    ) -> str:
        pass