"""
S3DF Configuration

Environment-driven settings for connecting to S3DF services.
"""

import os
from dataclasses import dataclass


@dataclass
class S3DFSettings:
    """Configuration for S3DF coact-api integration."""
    
    def __init__(self):
        self.coact_api_url = os.getenv("COACT_API_URL", "https://coact-dev.slac.stanford.edu/graphql-service-dev")
        self.coact_service_user = os.getenv("COACT_SERVICE_USER")
        self.coact_service_password = os.getenv("COACT_SERVICE_PASSWORD")  
        self.coact_use_basic_auth = True 
        
        # Facility identification
        self.facility_name = os.getenv("S3DF_FACILITY_NAME", "s3df")
        

        # HTTP header coact-api uses to identify the caller.
        # 'coactimp' is the impersonation header read by the coact Strawberry context;
        # set to a username to query as that user, or leave empty to use the server default.
        self.coact_auth_header = os.getenv("COACT_AUTH_HEADER", "coactimp")


settings = S3DFSettings()
