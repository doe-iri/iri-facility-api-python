from pydantic import BaseModel, field_serializer, Field
import datetime
from enum import IntEnum


class ResourceSpec(BaseModel):
    """
    Specification of computational resources required for a job.
    """
    node_count: int | None = Field(default=None, description="Number of compute nodes to allocate")
    process_count: int | None = Field(default=None, description="Total number of processes to launch")
    processes_per_node: int | None = Field(default=None, description="Number of processes to launch per node")
    cpu_cores_per_process: int | None = Field(default=None, description="Number of CPU cores to allocate per process")
    gpu_cores_per_process: int | None = Field(default=None, description="Number of GPU cores to allocate per process")
    exclusive_node_use: bool = Field(default=True, description="Whether to request exclusive use of allocated nodes")
    memory: int | None = Field(default=None, description="Amount of memory to allocate in bytes")


class JobAttributes(BaseModel):
    """
    Additional attributes and scheduling parameters for a job.
    """
    duration: datetime.timedelta = Field(default=datetime.timedelta(minutes=10), description="Maximum wall time duration for the job")
    queue_name: str | None = Field(default=None, description="Name of the queue or partition to submit the job to")
    account: str | None = Field(default=None, description="Account or project to charge for resource usage")
    reservation_id: str | None = Field(default=None, description="ID of a reservation to use for the job")
    custom_attributes: dict[str, str] = Field(default={}, description="Custom scheduler-specific attributes as key-value pairs")


class VolumeMount(BaseModel):
    """
    Represents a volume mount for a container.
    """
    source: str = Field(description="The source path on the host system to mount")
    target: str = Field(description="The target path inside the container where the volume will be mounted")
    read_only: bool = Field(default=True, description="Whether the mount should be read-only")

class Container(BaseModel):
    """
    Represents a container specification for job execution.

    Implementation notes: The value of gpu_cores_per_process in ResourceSpec should be used to determine
    if the container should be run with GPU support. Likewise, the value of launcher in JobSpec should be used
    to determine if the container should be run with MPI support. The container should by default. be run with
    host networking.
    """
    image: str = Field(description="The container image to use (e.g., 'docker.io/library/ubuntu:latest')")
    volume_mounts: list[VolumeMount] = Field(default=[], description="List of volume mounts for the container")


class JobSpec(BaseModel):
    """
    Specification for job.
    """
    executable: str | None = Field(default=None, description="Path to the executable to run. If container is specified, this will be used as the entrypoint to the container.")
    container: Container | None = Field(default=None, description="Container specification for containerized execution")
    arguments: list[str] = Field(default=[], description="Command-line arguments to pass to the executable or container")
    directory: str | None = Field(default=None, description="Working directory for the job")
    name: str | None = Field(default=None, description="Name of the job")
    inherit_environment: bool = Field(default=True, description="Whether to inherit the environment variables from the submission environment")
    environment: dict[str, str] = Field(default={}, description="Environment variables to set for the job. If container is specified, these will be set inside the container.")
    stdin_path: str | None = Field(default=None, description="Path to file to use as standard input")
    stdout_path: str | None = Field(default=None, description="Path to file to write standard output")
    stderr_path: str | None = Field(default=None, description="Path to file to write standard error")
    resources: ResourceSpec | None = Field(default=None, description="Resource requirements for the job")
    attributes: JobAttributes | None = Field(default=None, description="Additional job attributes such as duration, queue, and account")
    pre_launch: str | None = Field(default=None, description="Script or commands to run before launching the job")
    post_launch: str | None = Field(default=None, description="Script or commands to run after the job completes")
    launcher: str | None = Field(default=None, description="Job launcher to use (e.g., 'mpirun', 'srun')")


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
