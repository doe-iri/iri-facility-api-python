from abc import abstractmethod
from ...types.user import User
from ..status import models as status_models
from . import models as compute_models
from ..iri_router import AuthenticatedAdapter


class FacilityAdapter(AuthenticatedAdapter):
    """
    Facility-specific code is handled by the implementation of this interface.
    Use the `IRI_API_ADAPTER` environment variable (defaults to `app.demo_adapter.FacilityAdapter`)
    to install your facility adapter before the API starts.
    """

    @abstractmethod
    async def submit_job(self: "FacilityAdapter", resource: status_models.Resource, user: User, job_spec: compute_models.JobSpec) -> compute_models.Job:
        pass

    @abstractmethod
    async def update_job(self: "FacilityAdapter", resource: status_models.Resource, user: User, job_spec: compute_models.JobSpec, job_id: str) -> compute_models.Job:
        pass

    @abstractmethod
    async def get_job(
        self: "FacilityAdapter",
        resource: status_models.Resource,
        user: User,
        job_id: str,
        historical: bool = False,
        include_spec: bool = False,
    ) -> compute_models.Job:
        pass

    @abstractmethod
    async def get_jobs(
        self: "FacilityAdapter",
        resource: status_models.Resource,
        user: User,
        offset: int,
        limit: int,
        filters: dict[str, object] | None = None,
        historical: bool = False,
        include_spec: bool = False,
    ) -> list[compute_models.Job]:
        pass

    @abstractmethod
    async def cancel_job(self: "FacilityAdapter", resource: status_models.Resource, user: User, job_id: str) -> bool:
        pass
