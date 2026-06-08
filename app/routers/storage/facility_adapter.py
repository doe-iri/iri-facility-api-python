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
    async def get_locations(
        self,
        resource: status_models.Resource,
        user: User,
        logicalpath: storage_models.LogicalName | None,
        project: str | None,
        allocation: str | None,
        intent: storage_models.StorageIntent | None,
    ) -> list[storage_models.StorageInstance]:
        """
        Return resolved storage paths for the user at the given resource. The returned
        instances also capture the access semantics of that resource context, so callers
        do not need a separate mounts endpoint.
        Results are optionally filtered by logical name, project/allocation, and intent.

        Intent semantics:
          - staging: exclude archive (too slow for staging workflows)
          - long-term-storage: return only archive
          - write: exclude paths that are read-only in a job context
          - read: no filtering (all accessible paths)
        """
        pass

    @abstractmethod
    async def get_access_endpoints(
        self,
        resource: status_models.Resource,
        user: User,
        protocol: storage_models.AccessProtocol | None,
        endpoint_id: str | None,
    ) -> list[storage_models.AccessEndpoint]:
        """
        Return the list of data access endpoints for the given storage resource.
        Each entry describes a protocol (Globus, XRootD, S3, ...) and the connection
        details needed to use it.
        Results are optionally filtered by protocol and/or endpoint ID.
        """
        pass
