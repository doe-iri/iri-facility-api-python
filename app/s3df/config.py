"""
S3DF Configuration

Environment-driven settings for connecting to S3DF services.
"""

import os
from dataclasses import dataclass


@dataclass
class S3DFSettings:
    """Configuration settings for S3DF adapter."""
    
    # coact-api connection
    coact_api_url: str = os.getenv("COACT_API_URL", "https://coact.slac.stanford.edu/graphql")
    coact_service_user: str = os.getenv("COACT_SERVICE_USER", "")
    
    # Facility identification
    facility_name: str = os.getenv("S3DF_FACILITY_NAME", "s3df")
    
    # Authentication mode: "bypass" for dev (username in token), "globus" for production
    auth_mode: str = os.getenv("S3DF_AUTH_MODE", "bypass")


settings = S3DFSettings()
