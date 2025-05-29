from pydantic import BaseModel
import enum


class AllocationUnit(enum.Enum):
    node_hours = "Node Hours"
    bytes = "Bytes"
    inodes = "Inodes"


class Capability(BaseModel):
    """
        An aspect of a resource that can have an allocation.
        For example, Perlmutter nodes with GPUs
        For some resources at a facility, this will be 1 to 1 with the resource.
        It is a way to further subdivide a resource into allocatable sub-resources.
        The word "capability" is also known to users as something they need for a job to run. (eg. gpu)
    """
    id: str
    name: str
    units: list[AllocationUnit]


class User(BaseModel):
    """A user of the facility"""
    id: str
    name: str
    # we could expose more fields here (eg. email) but it might be against policy
    

class Project(BaseModel):
    """A project and its users at a facility"""
    id: str
    name: str
    description: str
    user_ids: list[str]


class AllocationEntry(BaseModel):
    """Base class for allocations."""
    id: str
    allocation: float  # how much this allocation can spend
    usage: float # how much this allocation has spent
    units: AllocationUnit


class ProjectAllocation(BaseModel):
    """
        A project's allocation for a capability. (aka. repo)
        This allocation is a piece of the total allocation for the capability. (eg. 5% of the total node hours of Perlmutter GPU nodes)
        A project would at least have a storage and job repos, maybe more than 1 of each.
    """
    # how much this allocation can spend
    id: str
    project_id: str
    capability_id: str
    entries: list[AllocationEntry]


class UserAllocation(BaseModel):
    """
        A user's allcation in a project. 
        This allocation is a piece of the project's allocation.
    """
    id: str
    project_allocation_id: str
    user_id: str
    entries: list[AllocationEntry]