from abc import abstractmethod
from . import models as facility_models
from ..iri_router import AuthenticatedAdapter


class FacilityAdapter(AuthenticatedAdapter):
    """
    Facility-specific code is handled by the implementation of this interface.
    Use the `IRI_API_ADAPTER` environment variable (defaults to `app.demo_adapter.FacilityAdapter`)
    to install your facility adapter before the API starts.
    """

    @abstractmethod
    async def get_facility(
        self: "FacilityAdapter",
        modified_since: str | None = None,
    ) -> facility_models.Facility | None:
        pass
