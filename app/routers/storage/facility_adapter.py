from abc import abstractmethod

from ...types.user import User
from ..status import models as status_models
from . import models as storage_models
from ..iri_router import AuthenticatedAdapter


class FacilityAdapter(AuthenticatedAdapter):
    """
    Facility-specific storage location adapter.
    Use the `IRI_API_ADAPTER_storage` environment variable
    (defaults to `app.demo_adapter.DemoAdapter`) to install your implementation.
    """

    @abstractmethod
    async def get_logical_names(self) -> list[storage_models.LogicalName]:
        """Return the logical filesystem tier names supported at this facility."""
        pass

    @abstractmethod
    async def get_locations(
        self,
        resource: status_models.Resource,
        user: User,
        logicalpath: storage_models.LogicalName | None,
        project: str | None,
        allocation: str | None,
        intent: storage_models.StorageIntent | None,
    ) -> list[storage_models.StorageLocation]:
        """
        Return resolved storage paths for the user at the given resource.
        Results are optionally filtered by logical name, project/allocation, and intent.

        Intent semantics:
          - staging: exclude archive (too slow for staging workflows)
          - long-term-storage: return only archive
          - write: exclude paths that are read-only in a job context
          - read: no filtering (all accessible paths)
        """
        pass

    @abstractmethod
    async def get_mounts(
        self,
        resource: status_models.Resource,
        user: User,
        project: str | None,
        intent: storage_models.StorageIntent | None,
    ) -> list[storage_models.StorageMount]:
        """
        Return all storage volumes mounted at the resource. The access permissions
        in each StorageMount reflect what the user can do *through this resource_id*:
        a compute resource shows in-job permissions; a login / DTN / Globus resource
        shows what that endpoint can do. Callers select the appropriate resource_id
        for the context they need (e.g. compute resource for jobs, Globus collection
        for transfers).
        """
        pass
