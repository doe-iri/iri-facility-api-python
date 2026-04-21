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

        # Dex IdP — JWKS-based JWT verification for incoming Bearer tokens.
        self.dex_jwks_url = os.getenv("DEX_JWKS_URL")
        self.dex_issuer = os.getenv("DEX_ISSUER")
        self.dex_audience = os.getenv("DEX_AUDIENCE")
        self.dex_username_claim = os.getenv("DEX_USERNAME_CLAIM", "name")
        # When set, the verifier reads this PEM instead of fetching JWKS live
        # each request. An in-process background task keeps it fresh; the
        # verifier reloads on mtime change.
        self.dex_jwt_public_key = os.getenv("DEX_JWT_PUBLIC_KEY")
        self.dex_jwt_refresh_interval_seconds = int(
            os.getenv("DEX_JWT_REFRESH_INTERVAL_SECONDS", "21600")
        )


settings = S3DFSettings()
