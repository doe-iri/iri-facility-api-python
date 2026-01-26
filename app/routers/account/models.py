from pydantic import computed_field, Field
from ... import config
from ..common import IRIBaseModel, AllocationUnit


class User(IRIBaseModel):
    """A user of the facility"""
    id: str
    name: str
    api_key: str
    client_ip: str|None
    # we could expose more fields here (eg. email) but it might be against policy


class Project(IRIBaseModel):
    """A project and its users at a facility"""
    id: str
    name: str
    description: str
    user_ids: list[str]


class AllocationEntry(IRIBaseModel):
    """Base class for allocations."""
    allocation: float  # how much this allocation can spend
    usage: float # how much this allocation has spent
    unit: AllocationUnit


class ProjectAllocation(IRIBaseModel):
    """
        A project's allocation for a capability. (aka. repo)
        This allocation is a piece of the total allocation for the capability. (eg. 5% of the total node hours of Perlmutter GPU nodes)
        A project would at least have a storage and job repos, maybe more than 1 of each.
    """
    # how much this allocation can spend
    id: str
    project_id: str = Field(exclude=True)
    capability_id: str = Field(exclude=True)
    entries: list[AllocationEntry]


    @computed_field(description="The list of past events in this incident")
    @property
    def project_uri(self) -> str:
        return f"{config.API_URL_ROOT}{config.API_PREFIX}{config.API_URL}/account/projects/{self.project_id}"


    @computed_field(description="The list of past events in this incident")
    @property
    def capability_uri(self) -> str:
        return f"{config.API_URL_ROOT}{config.API_PREFIX}{config.API_URL}/account/capabilities/{self.capability_id}"


class UserAllocation(IRIBaseModel):
    """
        A user's allcation in a project.
        This allocation is a piece of the project's allocation.
    """
    id: str
    project_id: str = Field(exclude=True)
    project_allocation_id: str = Field(exclude=True)
    user_id: str
    entries: list[AllocationEntry]


    @computed_field(description="The list of past events in this incident")
    @property
    def project_allocation_uri(self) -> str:
        return f"{config.API_URL_ROOT}{config.API_PREFIX}{config.API_URL}/account/projects/{self.project_id}/project_allocations/{self.project_allocation_id}"
