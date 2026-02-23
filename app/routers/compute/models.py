"""Models for compute router, including job specifications, job status, and related data structures."""
from enum import Enum
from typing import Annotated

from pydantic import ConfigDict, Field, StrictBool

from ...types.base import IRIBaseModel


class ResourceSpec(IRIBaseModel):
    """
    Specification of computational resources required for a job.
    """

    node_count: Annotated[int, Field(ge=1, description="Number of compute nodes to allocate", example=2)] = None
    process_count: Annotated[int, Field(ge=1, description="Total number of processes to launch", example=64)] = None
    processes_per_node: Annotated[int, Field(ge=1, description="Number of processes to launch per node", example=32)] = None
    cpu_cores_per_process: Annotated[int, Field(ge=1, description="Number of CPU cores to allocate per process", example=2)] = None
    gpu_cores_per_process: Annotated[int, Field(ge=1, description="Number of GPU cores to allocate per process", example=1)] = None
    exclusive_node_use: Annotated[StrictBool, Field(description="Whether to request exclusive use of allocated nodes", example=True)] = True
    memory: Annotated[int, Field(ge=1, description="Amount of memory to allocate in bytes", example=17179869184)] = None


class JobAttributes(IRIBaseModel):
    """
    Additional attributes and scheduling parameters for a job.
    """

    duration: Annotated[int, Field(description="Duration in seconds", ge=1, examples=[30, 60, 120])] = None
    queue_name: Annotated[str, Field(min_length=1, description="Name of the queue or partition to submit the job to", example="debug")] = None
    account: Annotated[str, Field(min_length=1, description="Account or project to charge for resource usage", example="proj123")] = None
    reservation_id: Annotated[str, Field(min_length=1, description="ID of a reservation to use for the job", example="resv-42")] = None
    custom_attributes: Annotated[dict[str, str], Field(description="Custom scheduler-specific attributes as key-value pairs", example={"constraint": "gpu"})] = {}


class VolumeMount(IRIBaseModel):
    """
    Represents a volume mount for a container.
    """

    source: Annotated[str, Field(min_length=1, description="The source path on the host system to mount", example="/data/project")]
    target: Annotated[str, Field(min_length=1, description="The target path inside the container where the volume will be mounted", example="/mnt/data")]
    read_only: Annotated[StrictBool, Field(description="Whether the mount should be read-only", example=True)] = True


class Container(IRIBaseModel):
    """
    Represents a container specification for job execution.

    Implementation notes: The value of gpu_cores_per_process in ResourceSpec should be used to determine
    if the container should be run with GPU support. Likewise, the value of launcher in JobSpec should be used
    to determine if the container should be run with MPI support. The container should by default. be run with
    host networking.
    """

    image: Annotated[str, Field(min_length=1, description="The container image to use (e.g., 'docker.io/library/ubuntu:latest')", example="docker.io/library/ubuntu:latest")]
    volume_mounts: Annotated[list[VolumeMount], Field(description="List of volume mounts for the container")] = []


class JobSpec(IRIBaseModel):
    """
    Specification for a job.
    """

    model_config = ConfigDict(extra="forbid")
    executable: Annotated[str, Field(min_length=1,
                                     description="Path to the executable to run. If container is specified, this will be used as the entrypoint to the container.",
                                     example="/usr/bin/python")] = None
    container: Annotated[Container, Field(description="Container specification for containerized execution")] = None
    arguments: Annotated[list[str], Field(description="Command-line arguments to pass to the executable or container", example=["-n", "100"])] = []
    directory: Annotated[str, Field(min_length=1, description="Working directory for the job", example="/home/user/work")] = None
    name: Annotated[str, Field(min_length=1, description="Name of the job", example="my-job")] = None
    inherit_environment: Annotated[StrictBool, Field(description="Whether to inherit the environment variables from the submission environment", example=True)] = True
    environment: Annotated[dict[str, str], Field(description="Environment variables to set for the job. If container is specified, these will be set inside the container.",
                                                 example={"OMP_NUM_THREADS": "4"})] = {}
    stdin_path: Annotated[str, Field(min_length=1, description="Path to file to use as standard input", example="/home/user/input.txt")] = None
    stdout_path: Annotated[str, Field(min_length=1, description="Path to file to write standard output", example="/home/user/output.txt")] = None
    stderr_path: Annotated[str, Field(min_length=1, description="Path to file to write standard error", example="/home/user/error.txt")] = None
    resources: Annotated[ResourceSpec, Field(description="Resource requirements for the job")] = None
    attributes: Annotated[JobAttributes, Field(description="Additional job attributes such as duration, queue, and account")] = None
    pre_launch: Annotated[str, Field(min_length=1, description="Script or commands to run before launching the job", example="module load cuda")] = None
    post_launch: Annotated[str, Field(min_length=1, description="Script or commands to run after the job completes", example="echo done")] = None
    launcher: Annotated[str, Field(min_length=1, description="Job launcher to use (e.g., 'mpirun', 'srun')", example="srun")] = None


class JobState(str, Enum):
    """
    from: https://exaworks.org/psij-python/docs/v/0.9.11/_modules/psij/job_state.html#JobState

    An enumeration holding the possible job states.

    The possible states are: `NEW`, `QUEUED`, `ACTIVE`, `COMPLETED`, `FAILED`, and `CANCELED`.
    """

    NEW = "new"
    """
    This is the state of a job immediately after the :class:`~psij.Job` object is created and
    before being submitted to a :class:`~psij.JobExecutor`.
    """
    QUEUED = "queued"
    """
    This is the state of the job after being accepted by a backend for execution, but before the
    execution of the job begins.
    """
    ACTIVE = "active"
    """This state represents an actively running job."""
    COMPLETED = "completed"
    """
    This state represents a job that has completed *successfully* (i.e., with a zero exit code).
    In other words, a job with the executable set to `/bin/false` cannot enter this state.
    """
    FAILED = "failed"
    """
    Represents a job that has either completed unsuccessfully (with a non-zero exit code) or a job
    whose handling and/or execution by the backend has failed in some way.
    """
    CANCELED = "canceled"
    """Represents a job that was canceled by a call to :func:`~psij.Job.cancel()`."""


class JobStatus(IRIBaseModel):
    """Represents the status of a job."""
    state: JobState = Field(..., description="Current state of the job", example="queued")
    time: float = Field(default=None, description="Timestamp associated with the status (seconds since epoch)", example=1708531200.0)
    message: str = Field(default=None, description="Human-readable status message", example="Job is waiting in queue")
    exit_code: int = Field(default=None, description="Process exit code if the job has finished", example=0)
    meta_data: dict[str, object] = Field(default=None, description="Backend-specific metadata associated with the job status")


class Job(IRIBaseModel):
    """Represents a job in the system."""
    id: str = Field(..., description="Unique identifier of the job", example="job-12345")
    status: JobStatus = Field(default=None, description="Current status of the job")
    job_spec: JobSpec = Field(default=None, description="Specification used to create the job")
