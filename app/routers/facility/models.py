"""Facility-related models."""

from typing import Optional

from pydantic import Field, HttpUrl, computed_field

from ... import config
from ...types.base import NamedObject


class Site(NamedObject):
    def _self_path(self) -> str:
        return f"/facility/sites/{self.id}"

    short_name: Optional[str] = Field(None, description="Common or short name of the Site.")
    operating_organization: str = Field(..., description="Organization operating the Site.")
    country_name: Optional[str] = Field(None, description="Country name of the Location.")
    locality_name: Optional[str] = Field(None, description="City or locality name of the Location.")
    state_or_province_name: Optional[str] = Field(None, description="State or province name of the Location.")
    street_address: Optional[str] = Field(None, description="Street address of the Location.")
    unlocode: Optional[str] = Field(None, description="United Nations trade and transport location code.")
    altitude: Optional[float] = Field(None, description="Altitude of the Location.")
    latitude: Optional[float] = Field(None, description="Latitude of the Location.")
    longitude: Optional[float] = Field(None, description="Longitude of the Location.")
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
    def _self_path(self) -> str:
        return "/facility"

    short_name: Optional[str] = Field(None, description="Common or short name of the Facility.")
    organization_name: Optional[str] = Field(None, description="Operating organization's name.")
    support_uri: Optional[HttpUrl] = Field(None, description="Link to facility support portal.")
    site_ids: list[str] = Field(default_factory=list, exclude=True)

    @computed_field(description="URIs of associated Sites.")
    @property
    def site_uris(self) -> list[str]:
        """Return the list of site URIs for this facility."""
        return [f"{config.API_URL_ROOT}{config.API_PREFIX}{config.API_URL}/facility/sites/{site_id}" for site_id in self.site_ids]
