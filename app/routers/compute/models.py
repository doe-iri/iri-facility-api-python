"""Models for compute router, including job specifications, job status, and related data structures."""
import time
from enum import Enum
from typing import Annotated
from uuid import uuid4

from pydantic import ConfigDict, Field, StrictBool

from ...types.base import IRIBaseModel


class ResourceSpec(IRIBaseModel):
    """
    Specification of computational resources required for a job.
    """

    node_count: int|None = Field(default=None, ge=1, description="Number of compute nodes to allocate", example=2)
    process_count: int|None = Field(default=None, ge=1, description="Total number of processes to launch", example=64)
    processes_per_node: int|None = Field(default=None, ge=1, description="Number of processes to launch per node", example=32)
    cpu_cores_per_process: int|None = Field(default=None, ge=1, description="Number of CPU cores to allocate per process", example=2)
    gpu_cores_per_process: int|None = Field(default=None, ge=1, description="Number of GPU cores to allocate per process", example=1)
    exclusive_node_use: StrictBool = Field(default=True, description="Whether to request exclusive use of allocated nodes", example=True)
    memory: int|None = Field(default=None, ge=1, description="Amount of memory to allocate in bytes", example=17179869184)


class JobAttributes(IRIBaseModel):
    """
    Additional attributes and scheduling parameters for a job.
    """

    duration: int|None = Field(default=None, description="Duration in seconds", ge=1, examples=[30, 60, 120])
    queue_name: str|None = Field(default=None, min_length=1, description="Name of the queue or partition to submit the job to", example="debug")
    account: str|None = Field(default=None, min_length=1, description="Account or project to charge for resource usage", example="proj123")
    reservation_id: str|None = Field(default=None, min_length=1, description="ID of a reservation to use for the job", example="resv-42")
    custom_attributes: dict[str, str] = Field(default_factory=dict, description="Custom scheduler-specific attributes as key-value pairs", example={"constraint": "gpu"})


class VolumeMount(IRIBaseModel):
    """
    Represents a volume mount for a container.
    """

    source: str = Field(min_length=1, description="The source path on the host system to mount", example="/data/project")
    target: str = Field(min_length=1, description="The target path inside the container where the volume will be mounted", example="/mnt/data")
    read_only: StrictBool = Field(default=True, description="Whether the mount should be read-only", example=True)


class Container(IRIBaseModel):
    """
    Represents a container specification for job execution.

    Implementation notes: The value of gpu_cores_per_process in ResourceSpec should be used to determine
    if the container should be run with GPU support. Likewise, the value of launcher in JobSpec should be used
    to determine if the container should be run with MPI support. The container should by default. be run with
    host networking.
    """

    image: str = Field(min_length=1, description="The container image to use (e.g., 'docker.io/library/ubuntu:latest')", example="docker.io/library/ubuntu:latest")
    volume_mounts: list[VolumeMount] = Field(default_factory=list, description="List of volume mounts for the container")


class JobSpec(IRIBaseModel):
    """
    Specification for a job.
    """

    model_config = ConfigDict(extra="forbid")
    executable: str|None = Field(default=None,
                                 min_length=1,
                                 description="Path to the executable to run. If container is specified, this will be used as the entrypoint to the container.",
                                 example="/usr/bin/python")
    container: Container|None = Field(default=None, description="Container specification for containerized execution")
    arguments: list[str] = Field(default_factory=list, description="Command-line arguments to pass to the executable or container", example=["-n", "100"])
    directory: str|None = Field(default=None, min_length=1, description="Working directory for the job", example="/home/user/work")
    name: str|None = Field(default=None, min_length=1, description="Name of the job", example="my-job")
    inherit_environment: StrictBool = Field(default=True, description="Whether to inherit the environment variables from the submission environment", example=True)
    environment: dict[str, str] = Field(default_factory=dict,
                                        description="Environment variables to set for the job. If container is specified, these will be set inside the container.",
                                        example={"OMP_NUM_THREADS": "4"})
    stdin_path: str|None = Field(default=None, min_length=1, description="Path to file to use as standard input", example="/home/user/input.txt")
    stdout_path: str|None = Field(default=None, min_length=1, description="Path to file to write standard output", example="/home/user/output.txt")
    stderr_path: str|None = Field(default=None, min_length=1, description="Path to file to write standard error", example="/home/user/error.txt")
    resources: ResourceSpec|None = Field(default=None, description="Resource requirements for the job")
    attributes: JobAttributes|None = Field(default=None, description="Additional job attributes such as duration, queue, and account")
    pre_launch: str|None = Field(default=None, min_length=1, description="Script or commands to run before launching the job", example="module load cuda")
    post_launch: str|None = Field(default=None, min_length=1, description="Script or commands to run after the job completes", example="echo done")
    launcher: str|None = Field(default=None, min_length=1, description="Job launcher to use (e.g., 'mpirun', 'srun')", example="srun")


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
    HELD = "held"
    """
    This is the state of a job that is queued but ineligible to run.
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
    time: float|None = Field(default=None, description="Timestamp associated with the status (seconds since epoch)", example=1708531200.0)
    message: str|None = Field(default=None, description="Human-readable status message", example="Job is waiting in queue")
    exit_code: int|None = Field(default=None, description="Process exit code if the job has finished", example=0)
    meta_data: dict[str, object]|None = Field(default=None, description="Backend-specific metadata associated with the job status")


class Job(IRIBaseModel):
    """Represents a job in the system."""
    id: str = Field(..., description="Unique identifier of the job", example="job-12345")
    status: JobStatus|None = Field(default=None, description="Current status of the job")
    job_spec: JobSpec|None = Field(default=None, description="Specification used to create the job")


# ---------------------------------------------------------------------------
# Workflow execution models
# ---------------------------------------------------------------------------

class TaskKind(str, Enum):
    """Kind of task execution inside a scheduler allocation."""
    local = "local"
    per_node = "per_node"
    coordinated = "coordinated"


class TaskRun(str, Enum):
    """Whether the task blocks or runs in the background."""
    foreground = "foreground"
    background = "background"


class TaskLifecycleState(str, Enum):
    """Directory-based lifecycle states for workflow tasks."""
    New = "New"
    Pending = "Pending"
    Running = "Running"
    Finished = "Finished"
    Failed = "Failed"


class WorkflowTaskSpec(IRIBaseModel):
    """Specification for a single task dispatched into a workflow."""
    task_id: str = Field(default_factory=lambda: str(uuid4()), description="Unique task identifier")
    command: str = Field(..., min_length=1, description="Shell command to execute")
    kind: TaskKind = Field(default=TaskKind.local, description="Execution semantics")
    run: TaskRun = Field(default=TaskRun.foreground, description="Foreground (blocking) or background")
    wait_for: list[str] = Field(default_factory=list, description="Task IDs that must finish before this task becomes pending")
    created: float = Field(default_factory=time.time, description="Creation timestamp (seconds since epoch)")


class WorkflowSpec(IRIBaseModel):
    """Request body for creating a new workflow."""
    name: str|None = Field(default=None, description="Optional workflow name")
    work_dir: str|None = Field(default=None, description="Shared filesystem directory for workflow state; facility default if omitted")
    worker_count: int = Field(default=1, ge=1, description="Number of worker processes to launch")
    resources: ResourceSpec|None = Field(default=None, description="Compute resources for the scheduler allocation")
    attributes: JobAttributes|None = Field(default=None, description="Scheduling attributes (queue, account, duration)")


class Workflow(IRIBaseModel):
    """Response returned when a workflow is created."""
    workflow_id: str = Field(..., description="Unique workflow identifier")
    work_dir: str = Field(..., description="Filesystem root where workflow state is stored")
    job_id: str|None = Field(default=None, description="Scheduler job ID hosting the runtime")


class WorkerInfo(IRIBaseModel):
    """Heartbeat snapshot for a leader or worker process."""
    id: str = Field(..., description="Process identifier (e.g. leader-1234)")
    host: str = Field(..., description="Hostname where the process is running")
    ts: float = Field(..., description="Last heartbeat timestamp (seconds since epoch)")


class WorkflowStatus(IRIBaseModel):
    """Aggregated status of a running workflow."""
    tasks: dict[str, int] = Field(..., description="Count of tasks in each lifecycle state", example={"New": 1, "Pending": 2, "Running": 3, "Finished": 10, "Failed": 0})
    workers: list[WorkerInfo] = Field(default_factory=list, description="Active worker heartbeats")
    leader: WorkerInfo|None = Field(default=None, description="Leader heartbeat, if alive")
