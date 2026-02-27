"""Facility-related models."""
from pydantic import Field, HttpUrl, computed_field

from ... import config
from ...types.base import NamedObject


class Site(NamedObject):
    """A physical site that hosts resources and is part of a facility."""
    def _self_path(self) -> str:
        return f"/facility/sites/{self.id}"

    short_name: str|None = Field(default=None, description="Common or short name of the Site.", example="NERSC")
    operating_organization: str|None = Field(..., description="Organization operating the Site.", example="Lawrence Berkeley National Laboratory")
    country_name: str|None = Field(default=None, description="Country name of the Location.", example="United States")
    locality_name: str|None = Field(default=None, description="City or locality name of the Location.", example="Berkeley")
    state_or_province_name: str|None = Field(default=None, description="State or province name of the Location.", example="California")
    street_address: str|None = Field(default=None, description="Street address of the Location.", example="1 Cyclotron Rd")
    unlocode: str|None = Field(default=None, description="United Nations trade and transport location code.", example="USOAK")
    altitude: float|None = Field(default=None, description="Altitude of the Location.", example=52.0)
    latitude: float|None = Field(default=None, description="Latitude of the Location.", example=37.8762)
    longitude: float|None = Field(default=None, description="Longitude of the Location.", example=-122.2506)
    resource_ids: list[str] = Field(default_factory=list, exclude=True)

    @computed_field(description="URIs of Resources hosted at this Site.")
    @property
    def resource_uris(self) -> list[str]:
        """Return the list of resource URIs for this site."""
        return [f"{config.API_URL_ROOT}{config.API_PREFIX}{config.API_URL}/status/resources/{resource_id}" for resource_id in self.resource_ids]

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

    short_name: str|None = Field(default=None, description="Common or short name of the Facility.", example="ESnet")
    organization_name: str|None = Field(default=None, description="Operating organization's name.", example="Energy Sciences Network")
    support_uri: HttpUrl|None = Field(default=None, description="Link to facility support portal.", example="https://support.es.net")
    site_ids: list[str] = Field(default_factory=list, exclude=True)

    @computed_field(description="URIs of associated Sites.")
    @property
    def site_uris(self) -> list[str]:
        """Return the list of site URIs for this facility."""
        return [f"{config.API_URL_ROOT}{config.API_PREFIX}{config.API_URL}/facility/sites/{site_id}" for site_id in self.site_ids]
