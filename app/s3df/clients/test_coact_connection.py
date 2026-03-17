"""
Standalone script to test coact-api connectivity.
Run with: python -m app.s3df.clients.test_coact_connection
"""
import asyncio
import logging

logging.basicConfig(level=logging.INFO)

from app.s3df.clients.coact import get_coact_client

async def main():
    client = get_coact_client()
    

    print("\n--- Testing get_all_repos ---")
    repos = await client.get_all_repos()
    print(repos)

    count = 0
    limit = 5
    for repo in repos:
        print(f"\n--- Testing get_repo_compute_allocation for {repo['Id']} ---")
        if count <= limit:
            repo_info = await client.get_repo_compute_allocation(repo_id=repo["Id"])
            if repo_info:
                count = len(repos)  # if we successfully get allocation info for at least one repo, skip the rest to avoid hitting rate limits  
                print(repo_info)
        else:
            print(f"...skipping remaining repos after {limit} tests")
            break
        count += 1






if __name__ == "__main__":
    asyncio.run(main())