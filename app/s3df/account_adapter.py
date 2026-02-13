"""
S3DF Account Adapter

Implements the IRI Account FacilityAdapter interface using SLAC's coact-api.
Maps coact repos → IRI projects, clusters → capabilities, allocations → allocations.

Data Model Mapping (coact → IRI):
- Cluster → Capability (compute resources like roma, milano)
- Storage types → Capability (sdf-data, sdf-group, sdf-scratch)
- User → User
- Repo → Project
- RepoComputeAllocation → ProjectAllocation (with node_hours unit)
- RepoStorageAllocation → ProjectAllocation (with bytes/inodes units)
- UserAllocation (percent) → UserAllocation (calculated from project allocation)
"""

from ..routers.account import models as account_models
from ..routers.account import facility_adapter as account_adapter


# =============================================================================
# STATIC DUMMY DATA (simulating coact-api responses)
# =============================================================================

# Simulated coact Clusters (maps to IRI Capability)
COACT_CLUSTERS = [
    {
        "name": "roma",
        "nodecpucount": 128,
        "nodegpucount": 0,
        "nodememgb": 512,
    },
    {
        "name": "milano",
        "nodecpucount": 64,
        "nodegpucount": 4,
        "nodememgb": 256,
        "nodegpumemgb": 80,
    },
    {
        "name": "ampere",
        "nodecpucount": 128,
        "nodegpucount": 4,
        "nodememgb": 1024,
        "nodegpumemgb": 80,
    },
]

# Simulated coact Users
COACT_USERS = {
    "amurthy": {
        "username": "amurthy",
        "eppns": ["amurthy@slac.stanford.edu"],
        "fullname": "Amith Murthy",
        "preferredemail": "amurthy@slac.stanford.edu",
        "shell": "/bin/bash",
        "uidnumber": 12345,
    },
    "testuser": {
        "username": "testuser",
        "eppns": ["testuser@slac.stanford.edu"],
        "fullname": "Test User",
        "preferredemail": "testuser@slac.stanford.edu",
        "shell": "/bin/bash",
        "uidnumber": 99999,
    },
}

# Simulated coact Repos (maps to IRI Project)
COACT_REPOS = [
    {
        "_id": "repo_001",
        "name": "lcls",
        "facility": "s3df",
        "description": "LCLS X-ray Science Research",
        "principal": "amurthy",
        "leaders": ["amurthy"],
        "users": ["amurthy", "testuser"],
        "currentComputeAllocations": [
            {
                "_id": "comp_alloc_001",
                "repoid": "repo_001",
                "clustername": "roma",
                "allocated": 10.0,  # 10 nodes
                "userAllocations": [
                    {"username": "amurthy", "percent": 60.0},
                    {"username": "testuser", "percent": 40.0},
                ],
                "usage": {"resourceHours": 1250.5},
            },
            {
                "_id": "comp_alloc_002",
                "repoid": "repo_001",
                "clustername": "milano",
                "allocated": 4.0,  # 4 GPU nodes
                "userAllocations": [
                    {"username": "amurthy", "percent": 70.0},
                    {"username": "testuser", "percent": 30.0},
                ],
                "usage": {"resourceHours": 480.0},
            },
        ],
        "currentStorageAllocations": [
            {
                "_id": "stor_alloc_001",
                "repoid": "repo_001",
                "storagename": "sdfdata",
                "purpose": "data",
                "rootfolder": "/sdf/data/lcls",
                "gigabytes": 50000.0,  # 50 TB
                "inodes": 10000000,
                "usage": {"gigabytes": 32500.0, "inodes": 4500000},
            },
            {
                "_id": "stor_alloc_002",
                "repoid": "repo_001",
                "storagename": "sdfgroup",
                "purpose": "group",
                "rootfolder": "/sdf/group/lcls",
                "gigabytes": 5000.0,  # 5 TB
                "inodes": 1000000,
                "usage": {"gigabytes": 2100.0, "inodes": 350000},
            },
        ],
    },
    {
        "_id": "repo_002",
        "name": "rubin",
        "facility": "s3df",
        "description": "Rubin Observatory Data Processing",
        "principal": "amurthy",
        "leaders": ["amurthy"],
        "users": ["amurthy"],
        "currentComputeAllocations": [
            {
                "_id": "comp_alloc_003",
                "repoid": "repo_002",
                "clustername": "ampere",
                "allocated": 16.0,
                "userAllocations": [{"username": "amurthy", "percent": 100.0}],
                "usage": {"resourceHours": 2800.0},
            },
        ],
        "currentStorageAllocations": [
            {
                "_id": "stor_alloc_004",
                "repoid": "repo_002",
                "storagename": "sdfdata",
                "purpose": "data",
                "rootfolder": "/sdf/data/rubin",
                "gigabytes": 500000.0,  # 500 TB
                "inodes": 100000000,
                "usage": {"gigabytes": 180000.0, "inodes": 45000000},
            },
        ],
    },
]


class S3DFAccountAdapter(account_adapter.FacilityAdapter):
    """
    S3DF implementation of the IRI Account FacilityAdapter.
    Returns static dummy data for testing data model mappings.
    """
    
    def __init__(self):
        pass
    
    # -------------------------------------------------------------------------
    # AuthenticatedAdapter methods
    # -------------------------------------------------------------------------
    
    async def get_current_user(self, api_key: str, client_ip: str) -> str:
        """
        POC: api_key is the username (bypass mode).
        Production: Would introspect Globus token.
        """
        if api_key.startswith("Bearer "):
            return api_key[7:]
        return api_key
    
    async def get_user(self, user_id: str, api_key: str, client_ip: str | None) -> account_models.User:
        """
        coact.User → IRI.User mapping:
        - username → id
        - fullname → name
        """
        coact_user = COACT_USERS.get(user_id)
        return account_models.User(
            id=coact_user["username"] if coact_user else user_id,
            name=coact_user.get("fullname", user_id) if coact_user else user_id,
            api_key=api_key,
            client_ip=client_ip
        )
    
    # -------------------------------------------------------------------------
    # AccountFacilityAdapter methods
    # -------------------------------------------------------------------------
    
    async def get_capabilities(self) -> list[account_models.Capability]:
        """
        coact.Cluster → IRI.Capability (compute)
        Static storage types → IRI.Capability (storage)
        """
        capabilities = []
        
        # Map coact clusters to capabilities
        for cluster in COACT_CLUSTERS:
            gpu_info = f", {cluster['nodegpucount']} GPUs" if cluster.get('nodegpucount', 0) > 0 else ""
            capabilities.append(account_models.Capability(
                id=cluster["name"],
                name=f"{cluster['name'].upper()} ({cluster['nodecpucount']} CPUs{gpu_info}, {cluster['nodememgb']}GB/node)",
                units=[account_models.AllocationUnit.node_hours]
            ))
        
        # Add storage capabilities
        capabilities.extend([
            account_models.Capability(
                id="sdf-data",
                name="S3DF Data Storage - /sdf/data",
                units=[account_models.AllocationUnit.bytes, account_models.AllocationUnit.inodes]
            ),
            account_models.Capability(
                id="sdf-group",
                name="S3DF Group Storage - /sdf/group",
                units=[account_models.AllocationUnit.bytes, account_models.AllocationUnit.inodes]
            ),
            account_models.Capability(
                id="sdf-scratch",
                name="S3DF Scratch Storage - /sdf/scratch",
                units=[account_models.AllocationUnit.bytes, account_models.AllocationUnit.inodes]
            ),
        ])
        
        return capabilities
    
    async def get_projects(self, user: account_models.User) -> list[account_models.Project]:
        """
        coact.Repo → IRI.Project mapping:
        - _id → id
        - name → name
        - description → description
        - users + leaders + principal → user_ids
        """
        projects = []
        
        for repo in COACT_REPOS:
            all_users = set(repo.get("users", []) + repo.get("leaders", []) + [repo.get("principal", "")])
            if user.id in all_users:
                projects.append(account_models.Project(
                    id=repo["_id"],
                    name=repo["name"],
                    description=repo.get("description", ""),
                    user_ids=list(all_users)
                ))
        
        return projects
    
    async def get_project_allocations(
        self,
        project: account_models.Project,
        user: account_models.User
    ) -> list[account_models.ProjectAllocation]:
        """
        coact.RepoComputeAllocation → IRI.ProjectAllocation (node_hours)
        coact.RepoStorageAllocation → IRI.ProjectAllocation (bytes, inodes)
        
        Mapping:
        - allocated * 720 (hours/month) → node_hours allocation
        - gigabytes * 1e9 → bytes allocation
        """
        repo = next((r for r in COACT_REPOS if r["_id"] == project.id), None)
        if not repo:
            return []
        
        allocations = []
        HOURS_PER_MONTH = 24 * 30  # 720 hours
        
        # Map compute allocations
        for ca in repo.get("currentComputeAllocations", []):
            allocations.append(account_models.ProjectAllocation(
                id=ca["_id"],
                project_id=project.id,
                capability_id=ca["clustername"],
                entries=[account_models.AllocationEntry(
                    allocation=ca.get("allocated", 0) * HOURS_PER_MONTH,
                    usage=ca.get("usage", {}).get("resourceHours", 0),
                    unit=account_models.AllocationUnit.node_hours
                )]
            ))
        
        # Map storage allocations
        for sa in repo.get("currentStorageAllocations", []):
            usage = sa.get("usage", {})
            entries = []
            
            if sa.get("gigabytes"):
                entries.append(account_models.AllocationEntry(
                    allocation=sa["gigabytes"] * 1e9,
                    usage=usage.get("gigabytes", 0) * 1e9,
                    unit=account_models.AllocationUnit.bytes
                ))
            
            if sa.get("inodes"):
                entries.append(account_models.AllocationEntry(
                    allocation=float(sa["inodes"]),
                    usage=float(usage.get("inodes", 0)),
                    unit=account_models.AllocationUnit.inodes
                ))
            
            if entries:
                allocations.append(account_models.ProjectAllocation(
                    id=sa["_id"],
                    project_id=project.id,
                    capability_id=f"sdf-{sa.get('purpose', 'data')}",
                    entries=entries
                ))
        
        return allocations
    
    async def get_user_allocations(
        self,
        user: account_models.User,
        project_allocation: account_models.ProjectAllocation
    ) -> list[account_models.UserAllocation]:
        """
        coact.UserAllocation (percent on compute) → IRI.UserAllocation
        
        For compute: applies user's percentage to project allocation
        For storage: returns full allocation (coact doesn't track per-user storage)
        """
        for repo in COACT_REPOS:
            # Check compute allocations
            for ca in repo.get("currentComputeAllocations", []):
                if ca["_id"] == project_allocation.id:
                    user_percent = next(
                        (ua["percent"] for ua in ca.get("userAllocations", []) if ua["username"] == user.id),
                        100.0
                    )
                    return [account_models.UserAllocation(
                        id=f"{project_allocation.id}-{user.id}",
                        project_id=project_allocation.project_id,
                        project_allocation_id=project_allocation.id,
                        user_id=user.id,
                        entries=[account_models.AllocationEntry(
                            allocation=e.allocation * (user_percent / 100.0),
                            usage=e.usage * (user_percent / 100.0),
                            unit=e.unit
                        ) for e in project_allocation.entries]
                    )]
            
            # Check storage allocations (no per-user breakdown)
            for sa in repo.get("currentStorageAllocations", []):
                if sa["_id"] == project_allocation.id:
                    return [account_models.UserAllocation(
                        id=f"{project_allocation.id}-{user.id}",
                        project_id=project_allocation.project_id,
                        project_allocation_id=project_allocation.id,
                        user_id=user.id,
                        entries=project_allocation.entries
                    )]
        
        return []
