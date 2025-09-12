from pydantic import BaseModel
import datetime

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


class JobRequest(BaseModel):
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


class Job(BaseModel):
    job_id : str


class CommandResult(BaseModel):
    status : str
    result : str | None = None