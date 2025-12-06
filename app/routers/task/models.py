from pydantic import BaseModel
import enum


class TaskStatus(str, enum.Enum):
        pending = "pending"
        active = "active"
        completed = "completed"
        failed = "failed"
        canceled = "canceled"


class Task(BaseModel):
    id: str
    status: TaskStatus=TaskStatus.pending
    result: str|None=None


class TaskCommand(BaseModel):
      router: str
      command: str
      args: dict
      