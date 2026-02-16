import enum
from pydantic import BaseModel, computed_field

from ... import config


class TaskSubmitResponse(BaseModel):
    """Response model for submitting a task"""
    task_id: str

    @computed_field(description="The list of past events in this incident")
    @property
    def task_uri(self) -> str:
        return f"{config.API_URL_ROOT}{config.API_PREFIX}{config.API_URL}/tasks/{self.task_id}"


class TaskStatus(str, enum.Enum):
    pending = "pending"
    active = "active"
    completed = "completed"
    failed = "failed"
    canceled = "canceled"


class TaskCommand(BaseModel):
    router: str
    command: str
    args: dict


class Task(BaseModel):
    id: str
    status: TaskStatus = TaskStatus.pending
    result: str | None = None
    command: TaskCommand | None = None
