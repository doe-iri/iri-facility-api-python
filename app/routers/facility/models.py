"""Facility-related models."""
from typing import List, Optional
from pydantic import Field, HttpUrl
from ..models import NamedObject

class Site(NamedObject):
    def _self_path(self) -> str:
        return f"/facility/sites/{self.id}"
    short_name: Optional[str] = Field(None, description="Common or short name of the Site.")
    operating_organization: str = Field(..., description="Organization operating the Site.")
    location_uri: Optional[HttpUrl] = Field(None, description="URI of Location containing this Site.")
    resource_uris: List[HttpUrl] = Field(default_factory=list, description="URIs of Resources hosted at this Site.")

class Location(NamedObject):
    def _self_path(self) -> str:
        return f"/facility/locations/{self.id}"
    short_name: Optional[str] = Field(None, description="Common or short name of the Location.")
    country_name: Optional[str] = Field(None, description="Country name of the Location.")
    locality_name: Optional[str] = Field(None, description="City or locality name of the Location.")
    state_or_province_name: Optional[str] = Field(None, description="State or province name of the Location.")
    street_address: Optional[str] = Field(None, description="Street address of the Location.")
    unlocode: Optional[str] = Field(None, description="United Nations trade and transport location code.")
    altitude: Optional[float] = Field(None, description="Altitude of the Location.")
    latitude: Optional[float] = Field(None, description="Latitude of the Location.")
    longitude: Optional[float] = Field(None, description="Longitude of the Location.")
    site_uris: List[HttpUrl] = Field(default_factory=list, description="URIs of Sites contained in this Location.")

class Facility(NamedObject):
    def _self_path(self) -> str:
        return f"/facility/facilities/{self.id}"
    short_name: Optional[str] = Field(None, description="Common or short name of the Facility.")
    organization_name: Optional[str] = Field(None, description="Operating organization’s name.")
    support_uri: Optional[HttpUrl] = Field(None, description="Link to facility support portal.")
    site_uris: List[HttpUrl] = Field(default_factory=list, description="URIs of associated Sites.")
    location_uris: List[HttpUrl] = Field(default_factory=list, description="URIs of associated Locations.")
    resource_uris: List[HttpUrl] = Field(default_factory=list, description="URIs of contained Resources.")
    event_uris: List[HttpUrl] = Field(default_factory=list, description="URIs of Events in this Facility.")
    incident_uris: List[HttpUrl] = Field(default_factory=list, description="URIs of Incidents in this Facility.")
    capability_uris: List[HttpUrl] = Field(default_factory=list, description="URIs of Capabilities offered by the Facility.")
    project_uris: List[HttpUrl] = Field(default_factory=list, description="URIs of Projects associated with this Facility.")
    project_allocation_uris: List[HttpUrl] = Field(default_factory=list, description="URIs of Project Allocations.")
    user_allocation_uris: List[HttpUrl] = Field(default_factory=list, description="URIs of User Allocations.")
