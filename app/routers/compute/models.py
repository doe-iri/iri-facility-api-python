from typing import Annotated
from enum import IntEnum
from pydantic import field_serializer, ConfigDict, StrictBool, Field
from ..common import IRIBaseModel


class ResourceSpec(IRIBaseModel):
    """
    Specification of computational resources required for a job.
    """
    node_count: Annotated[int | None, Field(ge=1, description="Number of compute nodes to allocate")] = None
    process_count: Annotated[int | None, Field(ge=1, description="Total number of processes to launch")] = None
    processes_per_node: Annotated[int | None, Field(ge=1, description="Number of processes to launch per node")] = None
    cpu_cores_per_process: Annotated[int | None, Field(ge=1, description="Number of CPU cores to allocate per process")] = None
    gpu_cores_per_process: Annotated[int | None, Field(ge=1, description="Number of GPU cores to allocate per process")] = None
    exclusive_node_use: Annotated[StrictBool, Field(description="Whether to request exclusive use of allocated nodes")] = True
    memory: Annotated[int | None, Field(ge=1,description="Amount of memory to allocate in bytes")] = None


class JobAttributes(IRIBaseModel):
    """
    Additional attributes and scheduling parameters for a job.
    """
    duration: Annotated[int | None, Field(description="Duration in seconds", ge=1, examples=[30, 60, 120])] = None
    queue_name: Annotated[str | None, Field(min_length=1, description="Name of the queue or partition to submit the job to")] = None
    account: Annotated[str | None, Field(min_length=1, description="Account or project to charge for resource usage")] = None
    reservation_id: Annotated[str | None, Field(min_length=1, description="ID of a reservation to use for the job")] = None
    custom_attributes: Annotated[dict[str, str], Field(description="Custom scheduler-specific attributes as key-value pairs")] = {}


class VolumeMount(IRIBaseModel):
    """
    Represents a volume mount for a container.
    """
    source: Annotated[str, Field(min_length=1, description="The source path on the host system to mount")]
    target: Annotated[str, Field(min_length=1, description="The target path inside the container where the volume will be mounted")]
    read_only: Annotated[StrictBool, Field(description="Whether the mount should be read-only")] = True

class Container(IRIBaseModel):
    """
    Represents a container specification for job execution.

    Implementation notes: The value of gpu_cores_per_process in ResourceSpec should be used to determine
    if the container should be run with GPU support. Likewise, the value of launcher in JobSpec should be used
    to determine if the container should be run with MPI support. The container should by default. be run with
    host networking.
    """
    image: Annotated[str, Field(min_length=1, description="The container image to use (e.g., 'docker.io/library/ubuntu:latest')")]
    volume_mounts: Annotated[list[VolumeMount], Field(description="List of volume mounts for the container")] = []


class JobSpec(IRIBaseModel):
    """
    Specification for job.
    """
    model_config = ConfigDict(extra="forbid")
    executable: Annotated[str | None, Field(min_length=1, description="Path to the executable to run. If container is specified, this will be used as the entrypoint to the container.")] = None
    container: Annotated[Container | None, Field(description="Container specification for containerized execution")] = None
    arguments: Annotated[list[str], Field(description="Command-line arguments to pass to the executable or container")] = []
    directory: Annotated[str | None, Field(min_length=1, description="Working directory for the job")] = None
    name: Annotated[str | None, Field(min_length=1, description="Name of the job")] = None
    inherit_environment: Annotated[StrictBool, Field(description="Whether to inherit the environment variables from the submission environment")] = True
    environment: Annotated[dict[str, str], Field(description="Environment variables to set for the job. If container is specified, these will be set inside the container.")] = {}
    stdin_path: Annotated[str | None, Field(min_length=1, description="Path to file to use as standard input")] = None
    stdout_path: Annotated[str | None, Field(min_length=1, description="Path to file to write standard output")] = None
    stderr_path: Annotated[str | None, Field(min_length=1, description="Path to file to write standard error")] = None
    resources: Annotated[ResourceSpec | None, Field(description="Resource requirements for the job")] = None
    attributes: Annotated[JobAttributes | None, Field(description="Additional job attributes such as duration, queue, and account")] = None
    pre_launch: Annotated[str | None, Field(min_length=1, description="Script or commands to run before launching the job")] = None
    post_launch: Annotated[str | None, Field(min_length=1, description="Script or commands to run after the job completes")] = None
    launcher: Annotated[str | None, Field(min_length=1, description="Job launcher to use (e.g., 'mpirun', 'srun')")] = None


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
