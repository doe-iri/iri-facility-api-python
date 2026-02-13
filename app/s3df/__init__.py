"""
S3DF Facility Adapter for IRI API

This module provides the S3DF-specific implementations of the IRI Facility API adapters,
connecting to SLAC's coact-api for account, compute, and resource management.
"""

from .account_adapter import S3DFAccountAdapter
from .config import settings

__all__ = ["S3DFAccountAdapter", "settings"]
