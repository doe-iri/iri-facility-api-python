from abc import abstractmethod
from ...types.user import User
from . import models
from ..iri_router import AuthenticatedAdapter


class FacilityAdapter(AuthenticatedAdapter):
    """
    Facility-specific code is handled by the implementation of this interface.
    Use the `IRI_API_ADAPTER_<domain>` environment variable to install your
    facility adapter before the API starts.
    """

    @abstractmethod
    async def get_servers(
        self: "FacilityAdapter",
        user: User,
    ) -> models.ServerList:
        pass


    @abstractmethod
    async def get_clusters(
        self: "FacilityAdapter",
        user: User,
        server_id: str,
    ) -> models.ClusterList:
        pass


    @abstractmethod
    async def get_projects(
        self: "FacilityAdapter",
        user: User,
        server_id: str,
        cluster_id: str,
    ) -> models.ProjectList:
        pass


    @abstractmethod
    async def create_namespace(
        self: "FacilityAdapter",
        user: User,
        server_id: str,
        cluster_id: str,
        namespace_request: models.NamespaceCreateRequest
    ) -> models.Namespace:
        pass


    @abstractmethod
    async def create_kubeconfig(
        self: "FacilityAdapter",
        user: User,
        server_id: str,
        kubeconfig_request: models.KubeconfigRequest
    ) -> models.Namespace:
        pass
