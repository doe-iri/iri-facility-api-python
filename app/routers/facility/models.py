"""Facility-related models."""
from typing import Optional
from pydantic import Field, HttpUrl
from ..models import NamedObject

class Facility(NamedObject):
    short_name: Optional[str] = Field(None, description="Common or short name of the Facility.")
    organization_name: Optional[str] = Field(None, description="Operating organization's name.")
    facility_uri: Optional[HttpUrl] = Field(None, description="URI of this facility.")
    support_uri: Optional[HttpUrl] = Field(None, description="Link to facility support portal.")
    country_name: Optional[str] = Field(None, description="Country name of the Location.")
    locality_name: Optional[str] = Field(None, description="City or locality name of the Location.")
    state_or_province_name: Optional[str] = Field(None, description="State or province name of the Location.")
    street_address: Optional[str] = Field(None, description="Street address of the Location.")
    unlocode: Optional[str] = Field(None, description="United Nations trade and transport location code.")
    altitude: Optional[float] = Field(None, description="Altitude of the Location.")
    latitude: Optional[float] = Field(None, description="Latitude of the Location.")
    longitude: Optional[float] = Field(None, description="Longitude of the Location.")

    def _self_path(self) -> str:
        return f"/facility/facilities/{self.id}"
