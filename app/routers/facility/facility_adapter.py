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

    @abstractmethod
    async def list_sites(
        self: "FacilityAdapter",
        modified_since: str | None = None,
        name: str | None = None,
        offset: int | None = None,
        limit: int | None = None,
        short_name: str | None = None,
    ) -> list[facility_models.Site]:
        pass

    @abstractmethod
    async def get_site(
        self: "FacilityAdapter",
        site_id: str,
        modified_since: str | None = None,
    ) -> facility_models.Site | None:
        pass

    @abstractmethod
    async def get_site_location(
        self: "FacilityAdapter",
        site_id: str,
        modified_since: str | None = None,
    ) -> facility_models.Location | None:
        pass

    @abstractmethod
    async def list_locations(
        self: "FacilityAdapter",
        modified_since: str | None = None,
        name: str | None = None,
        offset: int | None = None,
        limit: int | None = None,
        short_name: str | None = None,
        country_name: str | None = None,
    ) -> list[facility_models.Location]:
        pass

    @abstractmethod
    async def get_location(
        self: "FacilityAdapter",
        location_id: str,
        modified_since: str | None = None,
    ) -> facility_models.Location | None:
        pass
