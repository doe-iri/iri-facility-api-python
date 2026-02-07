"""Models for the IRI Facility API."""

from pydantic import Field

from .base import NamedObject
from .scalars import AllocationUnit, StrictDateTime


class Capability(NamedObject):
    """
    An aspect of a resource that can have an allocation.
    For example, Perlmutter nodes with GPUs
    For some resources at a facility, this will be 1 to 1 with the resource.
    It is a way to further subdivide a resource into allocatable sub-resources.
    The word "capability" is also known to users as something they need for a job to run. (eg. gpu)
    """

    def _self_path(self) -> str:
        return f"/account/capabilities/{self.id}"

    last_modified: StrictDateTime | None = Field(default=None, description="ISO 8601 timestamp when this object was last modified.")

    units: list[AllocationUnit]
