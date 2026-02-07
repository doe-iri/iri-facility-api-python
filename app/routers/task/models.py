import enum
from pydantic import BaseModel


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
