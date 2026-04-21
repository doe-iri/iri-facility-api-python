#!/usr/bin/env python
"""
Fetch Dex's JWKS, extract the active RSA signing key, and write it as a PEM
file the IRI app reads via DEX_JWT_PUBLIC_KEY.

Day-to-day this is handled automatically by an in-process refresh task in
`app.s3df.auth.jwt_verifier`. This CLI is for:
  - Pre-boot bootstrapping (populate the file before the server starts).
  - Ad-hoc manual refresh when debugging.

Usage:
    DEX_JWKS_URL=https://dex.slac.stanford.edu/keys \\
    DEX_JWT_PUBLIC_KEY=/opt/iri/etc/dex-pub.pem \\
    refresh-dex-jwks.py
"""
import os
import sys

from app.s3df.auth.jwt_verifier import _fetch_and_write_pem


def main() -> int:
    try:
        jwks_url = os.environ["DEX_JWKS_URL"]
    except KeyError:
        sys.exit("DEX_JWKS_URL is required")

    dest = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("DEX_JWT_PUBLIC_KEY")
    if not dest:
        sys.exit("Pass destination path as argv[1] or set DEX_JWT_PUBLIC_KEY")

    kid = _fetch_and_write_pem(jwks_url, dest)
    print(f"wrote pinned key to {dest} (kid={kid})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
