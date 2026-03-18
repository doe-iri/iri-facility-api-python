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
from app.s3df.clients import get_coact_client

# Simulated coact Users
COACT_USERS = {
    "amithm": {
        "username": "amithm",
        "eppns": ["amithm@slac.stanford.edu"],
        "fullname": "Amith Murthy",
        "preferredemail": "amithm@slac.stanford.edu",
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


class S3DFAccountAdapter(account_adapter.FacilityAdapter):
    """
    S3DF implementation of the IRI Account FacilityAdapter.
    Returns static dummy data for testing data model mappings.
    """
    
    def __init__(self):
        self.coact_client = get_coact_client()
    
    # -------------------------------------------------------------------------
    # AuthenticatedAdapter methods
    # -------------------------------------------------------------------------
    
    async def get_current_user(self, api_key: str, client_ip: str) -> str:
        """
            Production: Would introspect amsc token.
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
        coact_user = await self.coact_client.get_user(user_id)
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
        clusters = await self.coact_client.get_clusters()

        for cluster in clusters:
            gpu_info = f", {cluster['nodegpucount']} GPUs" if cluster.get('nodegpucount', 0) > 0 else ""
            capabilities.append(account_models.Capability(
                id=cluster["name"],
                name=f"{cluster['name'].upper()} ({cluster['nodecpucount']} CPUs{gpu_info}, {cluster['nodememgb']}GB/node)",
                units=[account_models.AllocationUnit.node_hours]
            ))
        
        # Add storage capabilities

        # capabilities.extend([
        #     account_models.Capability(
        #         id="sdf-data",
        #         name="S3DF Data Storage - /sdf/data",
        #         units=[account_models.AllocationUnit.bytes, account_models.AllocationUnit.inodes]
        #     ),
        #     account_models.Capability(
        #         id="sdf-group",
        #         name="S3DF Group Storage - /sdf/group",
        #         units=[account_models.AllocationUnit.bytes, account_models.AllocationUnit.inodes]
        #     ),
        #     account_models.Capability(
        #         id="sdf-scratch",
        #         name="S3DF Scratch Storage - /sdf/scratch",
        #         units=[account_models.AllocationUnit.bytes, account_models.AllocationUnit.inodes]
        #     ),
        # ])
        
        return capabilities
    
    async def get_projects(self, user: account_models.User) -> list[account_models.Project]:
        """
        coact.Repo → IRI.Project mapping:
        - Id → id
        - name → name
        - description → description
        - users + leaders + principal → user_ids
        """
        projects = []
        repos = await self.coact_client.get_user_repos(user)

        for repo in repos:
            all_users = set(repo.get("users", []) + repo.get("leaders", []) + [repo.get("principal", "")])
            # if user.id in all_users:

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
        
        repo_allocations = await self.coact_client.get_repo_compute_allocation(repo_id=project.id)

        allocations = []
        
        # Map compute allocations
        for comp_alloc in repo_allocations:
            # comp_alloc_usage = [usage for usage in COACT_REPO_OVERALL_COMPUTE_USAGE if usage["allocation_id"] == comp_alloc["_id"]][0]
            overall_usage = comp_alloc['usage'][0]
            allocations.append(account_models.ProjectAllocation(
                id=comp_alloc["_id"],
                project_id=project.id,
                capability_id=comp_alloc["clustername"],
                entries=[account_models.AllocationEntry(
                    allocation=comp_alloc.get("allocated", 0),
                    usage= overall_usage.get("resourceHours", 0) if overall_usage else 0,
                    unit=account_models.AllocationUnit.node_hours
                )]
            ))
        
        # Map storage allocations
        return allocations
    
    async def get_user_allocations(
        self,
        user: account_models.User,
        project_allocation: account_models.ProjectAllocation
    ) -> list[account_models.UserAllocation]:
        """
        coact.UserAllocation (percent on compute) → IRI.UserAllocation
        
        For compute: applies user's percentage to project allocation
        For storage: returns full allocation 
        """

        # For this POC, we only have compute allocations with user percentages.
        
        compute_alloc = await self.coact_client.get_repo_compute_allocation(repo_id=project_allocation.project_id)
        if not compute_alloc:
            # return nothing 
            return []


        # Placeholder user percentage based on current understanding of coact data model and existing data in user_allocations collection. This is a simplification for the POC.
        user_percent = await self.coact_client.get_user_allocation(repo_id=project_allocation.project_id, allocation_id=project_allocation.id) or 100
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
