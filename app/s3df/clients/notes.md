# CoAct GraphQL Client

This module provides a Python client for interacting with the SLAC coact-api GraphQL endpoint.

## Overview

The `CoactClient` class provides typed methods for querying S3DF resources including:
- Users and authentication
- Repos (projects)
- Clusters (compute resources)
- Compute and storage allocations
- Usage data

## Installation

The required dependencies are already included in `pyproject.toml`:
```toml
dependencies = [
    "gql[httpx]>=3.5.0",
]
```

## Configuration

Set the following environment variables:

| Variable | Purpose | Default |
|----------|---------|---------|
| `COACT_API_URL` | GraphQL endpoint | `https://coact.slac.stanford.edu/graphql` |
| `COACT_SERVICE_USER` | Service account username | `""` |

Example `.env`:
```bash
COACT_API_URL=https://coact-dev.slac.stanford.edu/graphql
COACT_SERVICE_USER=iri-service
```

## Usage

### Basic Client Setup

```python
from app.s3df.clients import CoactClient, get_coact_client

# Option 1: Use singleton instance
client = get_coact_client()

# Option 2: Create custom instance
client = CoactClient(
    api_url="https://coact-dev.slac.stanford.edu/graphql",
    service_user="my-service-account"
)
```

### User Queries

```python
# Get current user info (whoami)
user = await client.get_whoami(username="amurthy")
print(f"User: {user['username']}, Full name: {user['fullname']}")

# Get specific user
user = await client.get_user(username="testuser", requesting_user="amurthy")
print(f"UID: {user['uidnumber']}, Shell: {user['shell']}")
```

### Repo (Project) Queries

```python
# Get all repos for a user
repos = await client.get_my_repos(username="amurthy")
for repo in repos:
    print(f"Repo: {repo['name']} - {repo['description']}")

# Get specific repo by ID
repo = await client.get_repo(repo_id="507f1f77bcf86cd799439011", username="amurthy")
print(f"Principal: {repo['principal']}, Leaders: {repo['leaders']}")
```

### Cluster (Capability) Queries

```python
# Get all clusters
clusters = await client.get_clusters()
for cluster in clusters:
    print(f"{cluster['name']}: {cluster['nodecpucount']} CPUs, {cluster['nodegpucount']} GPUs")

# Get specific cluster
cluster = await client.get_cluster(cluster_name="roma")
print(f"Memory: {cluster['nodememgb']} GB, Charge factor: {cluster['chargefactor']}")
```

### Allocation Queries

```python
# Get compute allocations for a repo
allocations = await client.get_repo_compute_allocations(
    repo_id="507f1f77bcf86cd799439011",
    username="amurthy",
    current_only=True
)
for alloc in allocations:
    print(f"Cluster: {alloc['clustername']}, Allocated nodes: {alloc['allocated']}")

# Get storage allocations
storage = await client.get_repo_storage_allocations(
    repo_id="507f1f77bcf86cd799439011",
    username="amurthy"
)
for alloc in storage:
    print(f"{alloc['storagename']}: {alloc['gigabytes']} GB, {alloc['inodes']} inodes")

# Get user allocations within a compute allocation
user_allocs = await client.get_user_allocations(
    repo_id="507f1f77bcf86cd799439011",
    allocation_id="507f1f77bcf86cd799439012",
    username="amurthy"
)
for ua in user_allocs:
    print(f"User: {ua['username']}, Percent: {ua['percent']}%")
```

### Usage Data

```python
# Get usage for a specific allocation
usage = await client.get_allocation_usage(
    repo_id="507f1f77bcf86cd799439011",
    allocation_id="507f1f77bcf86cd799439012",
    username="amurthy"
)
print(f"Resource hours used: {usage['usage'][0]['resourceHours']}")

# Per-user usage breakdown
for user_usage in usage['perUserUsage']:
    print(f"{user_usage['username']}: {user_usage['resourceHours']} hours")
```

### Facility Queries

```python
# Get all facilities
facilities = await client.get_facilities()
for facility in facilities:
    print(f"{facility['name']}: {facility['description']}")

# Get specific facility
facility = await client.get_facility(facility_name="s3df")
print(f"Czars: {facility['czars']}")
```

## Integration with Account Adapter

The coact client is designed to be used within the S3DF account adapter:

```python
from app.s3df.clients import get_coact_client
from app.routers.account import models as account_models

class S3DFAccountAdapter:
    def __init__(self):
        self.coact = get_coact_client()
    
    async def get_projects(self, user: account_models.User) -> list[account_models.Project]:
        # Get repos from coact
        repos = await self.coact.get_my_repos(username=user.id)
        
        # Transform to IRI Project model
        projects = []
        for repo in repos:
            projects.append(account_models.Project(
                id=repo['_id'],
                name=repo['name'],
                description=repo.get('description', ''),
                user_ids=repo['users'] + repo['leaders'] + [repo['principal']]
            ))
        
        return projects
```

## Error Handling

The client logs errors and returns safe defaults:
- Failed queries return `None` (for single items) or `[]` (for lists)
- GraphQL errors are logged with context
- Transport errors are propagated up

```python
try:
    user = await client.get_user(username="nonexistent")
    if user is None:
        print("User not found")
except Exception as e:
    print(f"API error: {e}")
```

## Authentication and Impersonation

The client supports user impersonation via the `X-Impersonate-User` header:

```python
# Service account queries data as a specific user
repos = await client.get_my_repos(username="amurthy")
# This sets X-Impersonate-User: amurthy in the request
```

For production deployments, configure a service account with appropriate permissions in coact.

## GraphQL Query Customization

For advanced use cases, use the generic `execute_query` method:

```python
custom_query = """
    query CustomQuery($filter: String!) {
        repos(filter: {name: $filter}) {
            name
            facility
            customField
        }
    }
"""

result = await client.execute_query(
    query=custom_query,
    variables={"filter": "lcls"},
    username="amurthy"
)
repos = result.get("repos", [])
```

## Development Notes

### Query Structure

All queries follow GraphQL best practices:
- Named queries with descriptive names
- Explicit field selection (no wildcards)
- Variables for dynamic inputs
- Proper type annotations (MongoId, String, etc.)

### Data Model Alignment

The coact-api uses Strawberry GraphQL with MongoDB ObjectIds. Key types:
- `MongoId`: MongoDB ObjectId (serialized as string)
- `CoactDatetime`: ISO 8601 datetime strings
- `Int64`: Large integers (jobs, usage)

### Testing

Mock the client for testing:

```python
from unittest.mock import AsyncMock

async def test_get_repos():
    client = CoactClient()
    client.execute_query = AsyncMock(return_value={
        "myRepos": [{"_id": "123", "name": "test"}]
    })
    
    repos = await client.get_my_repos(username="testuser")
    assert len(repos) == 1
    assert repos[0]["name"] == "test"
```

## Troubleshooting

### Connection Issues

If you see `TransportQueryError`:
1. Verify `COACT_API_URL` is accessible
2. Check VPN/network access to SLAC infrastructure
3. Confirm GraphQL endpoint is running

### Authentication Failures

If impersonation isn't working:
1. Verify service account has admin/czar privileges in coact
2. Check `X-Impersonate-User` header is being sent
3. Review coact-api logs for authorization errors

### Query Failures

If specific queries fail:
1. Test the query directly in coact GraphiQL interface
2. Verify MongoDB IDs are valid (24-character hex strings)
3. Check that nested fields exist in the schema

## Further Reading

- [coact-api GraphQL Schema](https://coact.slac.stanford.edu/graphql) - Interactive schema explorer
- [S3DF Integration Analysis](../../../docs/s3df-integration-analysis.md) - Architecture overview
- [S3DF POC Setup Guide](../../../docs/s3df-poc-setup.md) - Deployment instructions
