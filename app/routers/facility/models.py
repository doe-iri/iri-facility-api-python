"""Facility-related models."""
from pydantic import Field, HttpUrl, computed_field

from ...request_context import get_url_prefix
from ...types.base import NamedObject


class Site(NamedObject):
    """A physical site that hosts resources and is part of a facility."""
    def _self_path(self) -> str:
        return f"/facility/sites/{self.id}"

    short_name: str|None = Field(default=None, description="Common or short name of the Site.", example="DOE Site")
    operating_organization: str|None = Field(..., description="Organization operating the Site.", example="Department of Energy Facility")
    country_name: str|None = Field(default=None, description="Country name of the Location.", example="United States")
    locality_name: str|None = Field(default=None, description="City or locality name of the Location.", example="Science City")
    state_or_province_name: str|None = Field(default=None, description="State or province name of the Location.", example="US State")
    street_address: str|None = Field(default=None, description="Street address of the Location.", example="1 Science Pkwy")
    unlocode: str|None = Field(default=None, description="United Nations trade and transport location code.", example="US000")
    altitude: float|None = Field(default=None, description="Altitude of the Location.", example=1.0)
    latitude: float|None = Field(default=None, description="Latitude of the Location.", example=10.0)
    longitude: float|None = Field(default=None, description="Longitude of the Location.", example=-100.0)
    resource_ids: list[str] = Field(default_factory=list, exclude=True)

    @computed_field(description="URIs of Resources hosted at this Site.")
    @property
    def resource_uris(self) -> list[str]:
        """Return the list of resource URIs for this site."""
        return [f"{get_url_prefix()}/status/resources/{resource_id}" for resource_id in self.resource_ids]

    @classmethod
    def find(cls, items, name=None, description=None, modified_since=None, short_name=None, country_name=None):
        """Find Locations matching the given criteria."""
        items = super().find(items, name=name, description=description, modified_since=modified_since)
        if short_name:
            items = [item for item in items if item.short_name == short_name]
        if country_name:
            items = [item for item in items if item.country_name == country_name]
        return items


class Facility(NamedObject):
    """ Facility representation, including associated Sites."""
    def _self_path(self) -> str:
        return "/facility"

    short_name: str|None = Field(default=None, description="Common or short name of the Facility.", example="DOE Facility")
    organization_name: str|None = Field(default=None, description="Operating organization's name.", example="Department of Energy Facility")
    support_uri: HttpUrl|None = Field(default=None, description="Link to facility support portal.", example="https://support.example-facility.org")
    site_ids: list[str] = Field(default_factory=list, exclude=True)

    @computed_field(description="URIs of associated Sites.")
    @property
    def site_uris(self) -> list[str]:
        """Return the list of site URIs for this facility."""
        return [f"{get_url_prefix()}/facility/sites/{site_id}" for site_id in self.site_ids]
