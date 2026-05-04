"""
S3DF Facility Adapter — static facility and site metadata for SLAC/S3DF.

The /facility endpoints are unauthenticated and return static data describing
SLAC National Accelerator Laboratory and the S3DF computing facility.
"""

import datetime

from fastapi import HTTPException

from app.routers.facility import models as facility_models
from app.routers.facility import facility_adapter
import uuid


class S3DFFacilityAdapter(facility_adapter.FacilityAdapter):
    """Returns static facility/site metadata for SLAC S3DF."""

    def __init__(self):
        now = datetime.datetime.now(datetime.timezone.utc)

        self.site = facility_models.Site(
            id=str(uuid.uuid4()),
            name="SLAC National Accelerator Laboratory",          
            description="We explore how the universe works at the biggest, smallest and fastest scales and invent powerful tools used by scientists around the globe. Our research helps solve real-world problems and advances the interests of the nation.",   
            last_modified=now,
            short_name="SLAC",
            operating_organization="SLAC National Accelerator Laboratory",  
            country_name="United States",
            locality_name="Menlo Park",           
            state_or_province_name="California",
            street_address="2575 Sand Hill Road",          
            latitude=37.419245954174606,              
            longitude=-122.20446351561414,             
            resource_ids=[],           
        )

        self.facility = facility_models.Facility(
            id=str(uuid.uuid4()),
            name="SLAC Shared Science Data Facility",                 
            description="S3DF is a compute, storage, and network architecture designed to support massive scale analytics required by SLAC experimental facilities and programs, including LCLS/LCLS-II, Vera C. Rubin Observatory, UED, and the Stanford-SLAC cryoEM Center (S2C2)", 
            last_modified=now,
            short_name="S3DF",           
            organization_name="S3DF",   
            support_uri="https://s3df.slac.stanford.edu",
            self_uri="https://s3df-dev.slac.stanford.edu/api/v1/facility",        
            site_ids=[self.site.id],
        )

    async def get_facility(self, modified_since: str | None = None) -> facility_models.Facility | None:
        if modified_since:
            ms = datetime.datetime.fromisoformat(str(modified_since))
            if self.facility.last_modified <= ms:
                return None
        return self.facility

    async def list_sites(
        self,
        modified_since: str | None = None,
        name: str | None = None,
        offset: int | None = None,
        limit: int | None = None,
        short_name: str | None = None,
    ) -> list[facility_models.Site]:
        sites = [self.site]

        if name:
            sites = [s for s in sites if name.lower() in s.name.lower()]
        if short_name:
            sites = [s for s in sites if s.short_name == short_name]
        if modified_since:
            ms = datetime.datetime.fromisoformat(str(modified_since))
            sites = [s for s in sites if s.last_modified > ms]

        o = offset or 0
        l = limit or len(sites)
        return sites[o : o + l]

    async def get_site(self, site_id: str, modified_since: str | None = None) -> facility_models.Site | None:
        if site_id != self.site.id:
            return None

        if modified_since:
            ms = datetime.datetime.fromisoformat(str(modified_since))
            if self.site.last_modified <= ms:
                raise HTTPException(status_code=304, headers={"Last-Modified": self.site.last_modified.isoformat()})

        return self.site
