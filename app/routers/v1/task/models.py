""" Task models for the IRI Facility API """
import enum
from pydantic import BaseModel, Field, computed_field

from .... import config


class TaskSubmitResponse(BaseModel):
    """Response model for submitting a task"""
    task_id: str = Field(..., description="Identifier of the submitted task", example="task-123")

    @computed_field(description="The list of past events in this incident")
    @property
    def task_uri(self) -> str:
        """Return the URI for this task."""
        return f"{config.API_URL_ROOT}{config.API_PREFIX}{config.API_URL}/task/{self.task_id}"


class TaskStatus(str, enum.Enum):
    """Represents the status of a task."""
    pending = "pending"
    active = "active"
    completed = "completed"
    failed = "failed"
    canceled = "canceled"


class TaskCommand(BaseModel):
    """Represents a command to be executed as part of a task."""
    router: str = Field(..., description="Router name the task comes from", example="filesystem")
    command: str = Field(..., description="Command to execute", example="chmod")
    args: dict = Field(..., description="Command arguments as key-value pairs", example={"path": "/home/user/file", "mode": "755"})


class Task(BaseModel):
    """Represents a task in the system."""
    id: str = Field(..., description="Unique identifier of the task", example="task-123")
    status: TaskStatus = Field(default=TaskStatus.pending, description="Current status of the task", example="pending")
    result: dict | None = Field(default=None, description="Result of the task execution, if available")
    command: TaskCommand|None = Field(default=None, description="Command associated with this task")
