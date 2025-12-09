from pydantic import BaseModel, field_serializer
import datetime
from enum import IntEnum


class ResourceSpec(BaseModel):
    node_count: int | None = None
    process_count: int | None = None
    processes_per_node: int | None = None
    cpu_cores_per_process: int | None = None
    gpu_cores_per_process: int | None = None
    exclusive_node_use: bool = True
    memory: int | None = None


class JobAttributes(BaseModel):
    duration: datetime.timedelta = datetime.timedelta(minutes=10)
    queue_name: str | None = None
    account: str | None = None
    reservation_id: str | None = None
    custom_attributes: dict[str, str] = {}


class JobSpec(BaseModel):
    executable : str | None = None
    arguments: list[str] = []
    directory: str | None = None
    name: str | None = None
    inherit_environment: bool = True
    environment: dict[str, str] = {}
    stdin_path: str | None = None
    stdout_path: str | None = None
    stderr_path: str | None = None
    resources: ResourceSpec | None = None
    attributes: JobAttributes | None = None
    pre_launch: str | None = None
    post_launch: str | None = None
    launcher: str | None = None
    class Config:
        extra = "forbid"


class CommandResult(BaseModel):
    status : str
    result : str | None = None


class JobState(IntEnum):
    """
    from: https://exaworks.org/psij-python/docs/v/0.9.11/_modules/psij/job_state.html#JobState
    
    An enumeration holding the possible job states.

    The possible states are: `NEW`, `QUEUED`, `ACTIVE`, `COMPLETED`, `FAILED`, and `CANCELED`.
    """

    NEW = 0
    """
    This is the state of a job immediately after the :class:`~psij.Job` object is created and
    before being submitted to a :class:`~psij.JobExecutor`.
    """
    QUEUED = 1
    """
    This is the state of the job after being accepted by a backend for execution, but before the
    execution of the job begins.
    """
    ACTIVE = 2
    """This state represents an actively running job."""
    COMPLETED = 3
    """
    This state represents a job that has completed *successfully* (i.e., with a zero exit code).
    In other words, a job with the executable set to `/bin/false` cannot enter this state.
    """
    FAILED = 4
    """
    Represents a job that has either completed unsuccessfully (with a non-zero exit code) or a job
    whose handling and/or execution by the backend has failed in some way.
    """
    CANCELED = 5
    """Represents a job that was canceled by a call to :func:`~psij.Job.cancel()`."""


class JobStatus(BaseModel):
    state : JobState
    time : float | None = None
    message : str | None = None
    exit_code : int | None = None
    meta_data : dict[str, object] | None = None


    @field_serializer('state')
    def serialize_state(self, state: JobState):
        return state.name


class Job(BaseModel):
    id : str
    status : JobStatus | None = None
