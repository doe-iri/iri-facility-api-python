"""
coact GraphQL Client

Provides typed methods for interacting with the coact-api GraphQL endpoint.
Supports both UI-style header auth (coactimp) and service basic auth.
"""

import logging
import base64
from typing import List, Optional, Dict, Any

from gql import gql, Client
from gql.transport.httpx import HTTPXTransport
from gql.transport.exceptions import TransportQueryError

from app.s3df.config import settings

LOG = logging.getLogger(__name__)


class CoactClient:
    """GraphQL client for coact-api service."""

    def __init__(
        self,
        api_url: Optional[str] = None,
        service_user: Optional[str] = None,
        service_password: Optional[str] = None,
        use_basic_auth: bool = False
    ):
        """
        Initialize the coact GraphQL client.

        Args:
            api_url: GraphQL endpoint URL (defaults to settings.coact_api_url)
            service_user: Service account username (defaults to settings.coact_service_user)
            service_password: Service account password (for basic auth)
            use_basic_auth: If True, use Basic auth instead of coactimp headers
        """
        self.api_url = api_url or settings.coact_api_url
        self.service_user = service_user or settings.coact_service_user
        self.service_password = service_password
        self.use_basic_auth = use_basic_auth
        self._client: Optional[Client] = None

        LOG.info(f"Initialized CoactClient for endpoint: {self.api_url} (basic_auth={use_basic_auth})")

    def _get_client(self, username: Optional[str] = None) -> Client:
        """
        Get or create a GQL client with appropriate headers.

        Args:
            username: Username for impersonation (coactimp mode) or ignored (basic auth mode)

        Returns:
            Configured GQL Client instance
        """
        headers = {"Content-Type": "application/json"}

        if self.use_basic_auth:
            # Basic Authentication for /graphql-service endpoint
            if not self.service_password:
                raise ValueError("service_password required when use_basic_auth=True")
            
            credentials = base64.b64encode(
                f"{self.service_user}:{self.service_password}".encode()
            ).decode("ascii")
            headers["Authorization"] = f"Basic {credentials}"
            
            LOG.debug(f"Using Basic auth as {self.service_user}")
        else:
            # UI-style headers for /graphql endpoint
            headers["coactimp"] = username or "null"
            headers["coactshowall"] = "true"
            
            if username:
                LOG.debug(f"Setting coactimp header for user: {username}")

        transport = HTTPXTransport(
            url=self.api_url,
            headers=headers,
            timeout=30.0
        )

        return Client(transport=transport, fetch_schema_from_transport=False)

    async def execute_query(
        self,
        query: str,
        variables: Optional[Dict[str, Any]] = None,
        username: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Execute a GraphQL query.

        Args:
            query: GraphQL query string
            variables: Query variables
            username: Username for impersonation

        Returns:
            Query result dictionary

        Raises:
            TransportQueryError: If the query fails
        """
        client = self._get_client(username)
        
        try:
            async with client as session:
                result = await session.execute(
                    gql(query),
                    variable_values=variables or {}
                )
                return result
        except TransportQueryError as e:
            LOG.error(f"GraphQL query failed: {e}")
            raise
        except Exception as e:
            LOG.error(f"Unexpected error executing query: {e}")
            raise

    # =========================================================================
    # User Queries
    # =========================================================================

    async def get_whoami(self, username: str) -> Optional[Dict[str, Any]]:
        """
        Get current user information.

        Args:
            username: Username to query as

        Returns:
            User object with username, fullname, eppns, etc.
        """
        query = """
            query WhoAmI {
                whoami {
                    username
                    fullname
                    uidnumber
                    eppns
                    preferredemail
                    shell
                    publichtml
                    isbot
                }
            }
        """

        try:
            result = await self.execute_query(query, username=username)
            return result.get("whoami")
        except Exception as e:
            LOG.error(f"Failed to get whoami for user {username}: {e}")
            return None

    async def get_user(self, username: str, requesting_user: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Get specific user by username.

        Args:
            username: Username to retrieve
            requesting_user: Username making the request (for impersonation)

        Returns:
            User object
        """
        query = """
            query GetUser($username: String!) {
                users(filter: {username: $username}) {
                    username
                    fullname
                    uidnumber
                    eppns
                    preferredemail
                    shell
                    publichtml
                    isbot
                    facilities
                }
            }
        """

        try:
            result = await self.execute_query(
                query,
                variables={"username": username},
                username=requesting_user
            )
            users = result.get("users", [])
            return users[0] if users else None
        except Exception as e:
            LOG.error(f"Failed to get user {username}: {e}")
            return None

    # =========================================================================
    # Repo (Project) Queries
    # =========================================================================

    async def get_my_repos(self, username: str) -> List[Dict[str, Any]]:
        """
        Get all repos (projects) for a user.

        Args:
            username: Username to query repos for

        Returns:
            List of repo objects
        """
        query = """
            query MyRepos {
                myRepos {
                    _id
                    name
                    facility
                    principal
                    leaders
                    users
                    group
                    description
                    computerequirement
                }
            }
        """

        try:
            result = await self.execute_query(query, username=username)
            return result.get("myRepos", [])
        except Exception as e:
            LOG.error(f"Failed to get repos for user {username}: {e}")
            return []

    async def get_repo(self, repo_id: str, username: str) -> Optional[Dict[str, Any]]:
        """
        Get specific repo by ID.

        Args:
            repo_id: Repo (project) ID
            username: Username making the request

        Returns:
            Repo object with details
        """
        query = """
            query GetRepo($repoId: MongoId!) {
                repo(_id: $repoId) {
                    _id
                    name
                    facility
                    principal
                    leaders
                    users
                    description
                    computerequirement
                }
            }
        """

        try:
            result = await self.execute_query(
                query,
                variables={"repoId": repo_id},
                username=username
            )
            return result.get("repo")
        except Exception as e:
            LOG.error(f"Failed to get repo {repo_id}: {e}")
            return None

    # =========================================================================
    # Cluster (Compute Capability) Queries
    # =========================================================================

    async def get_clusters(self, facility: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get all compute clusters.

        Args:
            facility: Optional facility name filter

        Returns:
            List of cluster objects
        """
        query = """
            query GetClusters {
                clusters {
                    _id
                    name
                    nodecpucount
                    nodecpucountdivisor
                    nodegpucount
                    nodememgb
                    nodegpumemgb
                    chargefactor
                    nodecpusmt
                    members
                    memberprefixes
                }
            }
        """

        try:
            result = await self.execute_query(query)
            clusters = result.get("clusters", [])
            
            # Filter by facility if specified
            if facility:
                # Note: clusters don't have facility field directly in the model
                # This might need adjustment based on actual API behavior
                pass
                
            return clusters
        except Exception as e:
            LOG.error(f"Failed to get clusters: {e}")
            return []

    async def get_cluster(self, cluster_name: str) -> Optional[Dict[str, Any]]:
        """
        Get specific cluster by name.

        Args:
            cluster_name: Name of the cluster

        Returns:
            Cluster object
        """
        query = """
            query GetCluster($name: String!) {
                clusters(filter: {name: $name}) {
                    _id
                    name
                    nodecpucount
                    nodecpucountdivisor
                    nodegpucount
                    nodememgb
                    nodegpumemgb
                    chargefactor
                    nodecpusmt
                    members
                    memberprefixes
                }
            }
        """

        try:
            result = await self.execute_query(query, variables={"name": cluster_name})
            clusters = result.get("clusters", [])
            return clusters[0] if clusters else None
        except Exception as e:
            LOG.error(f"Failed to get cluster {cluster_name}: {e}")
            return None

    # =========================================================================
    # Allocation Queries
    # =========================================================================

    async def get_repo_compute_allocations(
        self,
        repo_id: str,
        username: str,
        current_only: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Get compute allocations for a repo.

        Args:
            repo_id: Repo (project) ID
            username: Username making the request
            current_only: If True, only return current allocations

        Returns:
            List of RepoComputeAllocation objects
        """
        # Query for current allocations uses the currentComputeAllocations field
        if current_only:
            query = """
                query GetRepoComputeAllocations($repoId: MongoId!) {
                    repo(_id: $repoId) {
                        currentComputeAllocations {
                            _id
                            repoid
                            clustername
                            start
                            end
                            percent_of_facility
                            burst_percent_of_facility
                            allocated
                            burst_allocated
                        }
                    }
                }
            """
        else:
            # For all allocations, we'd need a different query
            # This would require direct collection access
            query = """
                query GetRepoComputeAllocations($repoId: MongoId!) {
                    repo(_id: $repoId) {
                        currentComputeAllocations {
                            _id
                            repoid
                            clustername
                            start
                            end
                            percent_of_facility
                            burst_percent_of_facility
                            allocated
                            burst_allocated
                        }
                    }
                }
            """

        try:
            result = await self.execute_query(
                query,
                variables={"repoId": repo_id},
                username=username
            )
            repo = result.get("repo")
            if not repo:
                return []
            return repo.get("currentComputeAllocations", [])
        except Exception as e:
            LOG.error(f"Failed to get compute allocations for repo {repo_id}: {e}")
            return []

    async def get_repo_storage_allocations(
        self,
        repo_id: str,
        username: str,
        current_only: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Get storage allocations for a repo.

        Args:
            repo_id: Repo (project) ID
            username: Username making the request
            current_only: If True, only return current allocations

        Returns:
            List of RepoStorageAllocation objects
        """
        query = """
            query GetRepoStorageAllocations($repoId: MongoId!) {
                repo(_id: $repoId) {
                    currentStorageAllocations {
                        _id
                        repoid
                        storagename
                        purpose
                        rootfolder
                        start
                        end
                        gigabytes
                        inodes
                    }
                }
            }
        """

        try:
            result = await self.execute_query(
                query,
                variables={"repoId": repo_id},
                username=username
            )
            repo = result.get("repo")
            if not repo:
                return []
            return repo.get("currentStorageAllocations", [])
        except Exception as e:
            LOG.error(f"Failed to get storage allocations for repo {repo_id}: {e}")
            return []

    async def get_user_allocations(
        self,
        repo_id: str,
        allocation_id: str,
        username: str
    ) -> List[Dict[str, Any]]:
        """
        Get user allocations within a compute allocation.

        Args:
            repo_id: Repo (project) ID
            allocation_id: RepoComputeAllocation ID
            username: Username making the request

        Returns:
            List of UserAllocation objects
        """
        query = """
            query GetUserAllocations($repoId: MongoId!, $allocationId: MongoId!) {
                repo(_id: $repoId) {
                    computeAllocation(allocationid: $allocationId) {
                        userAllocations {
                            username
                            percent
                        }
                    }
                }
            }
        """

        try:
            result = await self.execute_query(
                query,
                variables={"repoId": repo_id, "allocationId": allocation_id},
                username=username
            )
            repo = result.get("repo")
            if not repo:
                return []
            allocation = repo.get("computeAllocation")
            if not allocation:
                return []
            return allocation.get("userAllocations", [])
        except Exception as e:
            LOG.error(f"Failed to get user allocations for allocation {allocation_id}: {e}")
            return []

    # =========================================================================
    # Facility Queries
    # =========================================================================

    async def get_facilities(self) -> List[Dict[str, Any]]:
        """
        Get all facilities.

        Returns:
            List of facility objects
        """
        query = """
            query GetFacilities {
                facilities {
                    _id
                    name
                    description
                    resources
                    serviceaccount
                    servicegroup
                    czars
                }
            }
        """

        try:
            result = await self.execute_query(query)
            return result.get("facilities", [])
        except Exception as e:
            LOG.error(f"Failed to get facilities: {e}")
            return []

    async def get_facility(self, facility_name: str) -> Optional[Dict[str, Any]]:
        """
        Get specific facility by name.

        Args:
            facility_name: Name of the facility

        Returns:
            Facility object
        """
        query = """
            query GetFacility($name: String!) {
                facilities(filter: {name: $name}) {
                    _id
                    name
                    description
                    resources
                    serviceaccount
                    servicegroup
                    czars
                }
            }
        """

        try:
            result = await self.execute_query(query, variables={"name": facility_name})
            facilities = result.get("facilities", [])
            return facilities[0] if facilities else None
        except Exception as e:
            LOG.error(f"Failed to get facility {facility_name}: {e}")
            return None

    # =========================================================================
    # Usage Queries
    # =========================================================================

    async def get_allocation_usage(
        self,
        repo_id: str,
        allocation_id: str,
        username: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get usage data for a specific allocation.

        Args:
            repo_id: Repo (project) ID
            allocation_id: Allocation ID
            username: Username making the request

        Returns:
            Usage data including resource hours or storage metrics
        """
        query = """
            query GetAllocationUsage($repoId: MongoId!, $allocationId: MongoId!) {
                repo(_id: $repoId) {
                    computeAllocation(allocationid: $allocationId) {
                        usage {
                            repoid
                            clustername
                            resourceHours
                        }
                        perUserUsage {
                            username
                            resourceHours
                        }
                    }
                }
            }
        """

        try:
            result = await self.execute_query(
                query,
                variables={"repoId": repo_id, "allocationId": allocation_id},
                username=username
            )
            repo = result.get("repo")
            if not repo:
                return None
            return repo.get("computeAllocation")
        except Exception as e:
            LOG.error(f"Failed to get usage for allocation {allocation_id}: {e}")
            return None


# Singleton instance for convenience
_default_client: Optional[CoactClient] = None


def get_coact_client() -> CoactClient:
    """
    Get or create the default CoactClient instance.
    Reads basic auth settings from S3DFSettings.

    Returns:
        Singleton CoactClient instance
    """
    global _default_client
    
    if _default_client is None:
        _default_client = CoactClient(
            api_url=settings.coact_api_url,
            service_user=settings.coact_service_user,
            service_password=settings.coact_service_password,
            use_basic_auth=settings.coact_use_basic_auth,
        )
    
    return _default_client
