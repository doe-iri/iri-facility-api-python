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
        self.coact_api_url = os.getenv("COACT_API_URL", "https://coact.slac.stanford.edu/graphql")
        self.coact_service_user = os.getenv("COACT_SERVICE_USER", "sdf-bot")
        self.coact_service_password = os.getenv("COACT_SERVICE_PASSWORD")  # Required for basic auth
        self.coact_use_basic_auth = os.getenv("COACT_USE_BASIC_AUTH", "false").lower() == "true"
        
        # Facility identification
        self.facility_name = os.getenv("S3DF_FACILITY_NAME", "s3df")
        
        # Authentication mode: "bypass" for dev (username in token), "globus" for production
        self.auth_mode = os.getenv("S3DF_AUTH_MODE", "bypass")

        # HTTP header coact-api uses to identify the caller.
        # 'coactimp' is the impersonation header read by the coact Strawberry context;
        # set to a username to query as that user, or leave empty to use the server default.
        self.coact_auth_header = os.getenv("COACT_AUTH_HEADER", "coactimp")


settings = S3DFSettings()
