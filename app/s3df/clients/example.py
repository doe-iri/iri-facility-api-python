#!/usr/bin/env python3
"""
Example usage of the CoAct GraphQL Client

This script demonstrates how to use the coact client to query S3DF resources.
Run with: python -m app.s3df.clients.example
"""

import asyncio
import logging
import os
import sys

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
LOG = logging.getLogger(__name__)


async def main():
    """Main example function."""
    from app.s3df.clients import get_coact_client
    from app.s3df.config import settings
    
    # Get the coact client (uses settings for basic auth / coactimp)
    client = get_coact_client()
    
    # Example username (change this to test with different users)
    username = os.getenv("TEST_USERNAME", "amithm")
    
    LOG.info("=" * 80)
    LOG.info("coact GraphQL Client - Connection Test")
    LOG.info("=" * 80)
    LOG.info(f"  Endpoint:   {client.api_url}")
    LOG.info(f"  Auth mode:  {'Basic Auth' if client.use_basic_auth else 'coactimp header'}")
    LOG.info(f"  Service user: {client.service_user}")
    LOG.info(f"  Test user:  {username}")
    LOG.info(f"  Password set: {'yes' if client.service_password else 'NO — set COACT_SERVICE_PASSWORD'}")
    LOG.info("=" * 80)
    
    try:
        # =====================================================================
        # 1. Get current user info
        # =====================================================================
        LOG.info("\n1. Getting user information...")
        user = await client.get_whoami(username=username)
        if user:
            LOG.info(f"   ✓ Username: {user.get('username')}")
            LOG.info(f"   ✓ Full Name: {user.get('fullname')}")
            LOG.info(f"   ✓ Email: {user.get('preferredemail')}")
            LOG.info(f"   ✓ UID: {user.get('uidnumber')}")
        else:
            LOG.warning("   ✗ Could not retrieve user info")
        
        # =====================================================================
        # 2. Get all clusters (compute capabilities)
        # =====================================================================
        LOG.info("\n2. Getting compute clusters...")
        clusters = await client.get_clusters()
        if clusters:
            LOG.info(f"   ✓ Found {len(clusters)} clusters:")
            for cluster in clusters:
                cpus = cluster.get('nodecpucount', 0)
                gpus = cluster.get('nodegpucount', 0)
                mem = cluster.get('nodememgb', 0)
                gpu_info = f", {gpus} GPUs" if gpus > 0 else ""
                LOG.info(f"      - {cluster.get('name')}: {cpus} CPUs{gpu_info}, {mem} GB RAM")
        else:
            LOG.warning("   ✗ No clusters found")
        
        # =====================================================================
        # 3. Get user's repos (projects)
        # =====================================================================
        LOG.info("\n3. Getting user's repos (projects)...")
        repos = await client.get_my_repos(username=username)
        if repos:
            LOG.info(f"   ✓ Found {len(repos)} repos:")
            for repo in repos:
                LOG.info(f"      - {repo.get('name')} ({repo.get('facility')})")
                LOG.info(f"        Description: {repo.get('description', 'N/A')}")
                LOG.info(f"        Principal: {repo.get('principal')}")
                
                # =========================================================
                # 4. Get compute allocations for this repo
                # =========================================================
                repo_id = repo.get('_id')
                if repo_id:
                    LOG.info(f"\n4. Getting compute allocations for repo '{repo.get('name')}'...")
                    compute_allocs = await client.get_repo_compute_allocations(
                        repo_id=repo_id,
                        username=username,
                        current_only=True
                    )
                    
                    if compute_allocs:
                        LOG.info(f"   ✓ Found {len(compute_allocs)} compute allocations:")
                        for alloc in compute_allocs:
                            cluster = alloc.get('clustername')
                            nodes = alloc.get('allocated', 0)
                            percent = alloc.get('percent_of_facility', 0)
                            LOG.info(f"      - {cluster}: {nodes} nodes ({percent}% of facility)")
                            
                            # Get user allocations within this allocation
                            alloc_id = alloc.get('_id')
                            if alloc_id:
                                user_allocs = await client.get_user_allocations(
                                    repo_id=repo_id,
                                    allocation_id=alloc_id,
                                    username=username
                                )
                                if user_allocs:
                                    LOG.info("        User allocations:")
                                    for ua in user_allocs:
                                        LOG.info(f"          · {ua.get('username')}: {ua.get('percent')}%")
                    else:
                        LOG.info("   ✗ No compute allocations found")
                    
                    # =========================================================
                    # 5. Get storage allocations for this repo
                    # =========================================================
                    LOG.info(f"\n5. Getting storage allocations for repo '{repo.get('name')}'...")
                    storage_allocs = await client.get_repo_storage_allocations(
                        repo_id=repo_id,
                        username=username,
                        current_only=True
                    )
                    
                    if storage_allocs:
                        LOG.info(f"   ✓ Found {len(storage_allocs)} storage allocations:")
                        for alloc in storage_allocs:
                            storage_name = alloc.get('storagename')
                            purpose = alloc.get('purpose')
                            gb = alloc.get('gigabytes', 0)
                            inodes = alloc.get('inodes', 0)
                            root = alloc.get('rootfolder', 'N/A')
                            LOG.info(f"      - {storage_name} ({purpose}): {gb:,.0f} GB, {inodes:,} inodes")
                            LOG.info(f"        Path: {root}")
                    else:
                        LOG.info("   ✗ No storage allocations found")
                
                LOG.info("")  # Blank line between repos
        else:
            LOG.warning("   ✗ No repos found for this user")
        
        # =====================================================================
        # 6. Get all facilities
        # =====================================================================
        LOG.info("\n6. Getting facilities...")
        facilities = await client.get_facilities()
        if facilities:
            LOG.info(f"   ✓ Found {len(facilities)} facilities:")
            for facility in facilities:
                LOG.info(f"      - {facility.get('name')}: {facility.get('description')}")
                czars = facility.get('czars', [])
                if czars:
                    LOG.info(f"        Czars: {', '.join(czars)}")
        else:
            LOG.warning("   ✗ No facilities found")
        
        LOG.info("\n" + "=" * 80)
        LOG.info("Example completed successfully!")
        
    except Exception as e:
        LOG.error(f"Error during example execution: {e}", exc_info=True)
        return 1
    
    return 0


if __name__ == "__main__":
    # Check if coact API URL is configured
    from app.s3df.config import settings
    
    if not settings.coact_api_url:
        LOG.error("COACT_API_URL is not configured!")
        LOG.error("Set it with: export COACT_API_URL='https://coact.slac.stanford.edu/graphql-service'")
        sys.exit(1)
    
    if settings.coact_use_basic_auth and not settings.coact_service_password:
        LOG.error("COACT_SERVICE_PASSWORD is not set but COACT_USE_BASIC_AUTH=true!")
        LOG.error("Set it with: export COACT_SERVICE_PASSWORD='<sdf-bot password>'")
        sys.exit(1)
    
    # Run the async main function
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
