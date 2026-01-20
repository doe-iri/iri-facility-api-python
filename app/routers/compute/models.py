from enum import IntEnum
from pydantic import field_serializer, ConfigDict, StrictBool, Field
from ..dependencies import IRIBaseModel


class ResourceSpec(IRIBaseModel):
    node_count: int = Field(default=None, ge=1, description="Number of nodes")
    process_count: int = Field(default=None, ge=1, description="Number of processes")
    processes_per_node: int = Field(default=None, ge=1, description="Number of processes per node")
    cpu_cores_per_process: int = Field(default=None, ge=1, description="Number of CPU cores per process")
    gpu_cores_per_process: int = Field(default=None, ge=1, description="Number of GPU cores per process")
    exclusive_node_use: StrictBool = True
    memory: int = Field(default=None, ge=1, description="Amount of memory in megabytes")


class JobAttributes(IRIBaseModel):
    duration: int = Field(default=None, ge=1, description="Duration in seconds", examples=[30, 60, 120])
    queue_name: str = Field(default=None, min_length=1, description="Name of the queue/partition to use")
    account: str = Field(default=None, min_length=1, description="Account/Project name to charge")
    reservation_id: str = Field(default=None, min_length=1, description="Reservation ID to use")
    custom_attributes: dict[str, str] = {}


class JobSpec(IRIBaseModel):
    model_config = ConfigDict(extra="forbid")
    executable : str = Field(min_length=1, description="The executable to run")
    arguments: list[str] = []
    directory: str = Field(default=None, min_length=1, description="The working directory for the job")
    name: str = Field(default=None, min_length=1, description="The name of the job")
    inherit_environment: StrictBool = Field(default=True, description="Whether to inherit the environment")
    environment: dict[str, str] = {}
    stdin_path: str = Field(default=None, min_length=1, description="Path to the standard input file")
    stdout_path: str = Field(default=None, min_length=1, description="Path to the standard output file")
    stderr_path: str = Field(default=None, min_length=1, description="Path to the standard error file")
    resources: ResourceSpec | None = None
    attributes: JobAttributes | None = None
    pre_launch: str = Field(default=None, min_length=1, description="Command to run before launching the job")
    post_launch: str = Field(default=None, min_length=1, description="Command to run after launching the job")
    launcher: str = Field(default=None, min_length=1, description="Launcher to use for the job")


class CommandResult(IRIBaseModel):
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


class JobStatus(IRIBaseModel):
    state : JobState
    time : float | None = None
    message : str | None = None
    exit_code : int | None = None
    meta_data : dict[str, object] | None = None

    @field_serializer('state')
    def serialize_state(self, state: JobState):
        return state.name


class Job(IRIBaseModel):
    id : str
    status : JobStatus | None = None
    job_spec : JobSpec | None = None
