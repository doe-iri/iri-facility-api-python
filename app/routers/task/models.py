""" Task models for the IRI Facility API """
import enum

from pydantic import BaseModel, Field, computed_field

from ...request_context import get_url_prefix
from ...types.hal import IRI_CURIE, PROFILE_TASK, SERVICE_DESC_MEDIA_TYPE, build_hal_link


class TaskSubmitResponse(BaseModel):
    """Response model for submitting a task"""
    task_id: str = Field(..., description="Identifier of the submitted task", example="task-123")

    @computed_field(description="URI of the Task used to monitor the submitted operation")
    @property
    def task_uri(self) -> str:
        """Return the URI for this task."""
        return f"{get_url_prefix()}/task/{self.task_id}"

    @computed_field(description="HAL link to the Task used to monitor the submitted operation")
    @property
    def _links(self) -> dict:
        return {
            "monitor": build_hal_link(self.task_uri, profile=PROFILE_TASK),
        }


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

    @computed_field(description="HAL hypermedia links for this Task")
    @property
    def _links(self) -> dict:
        self_href = f"{get_url_prefix()}/task/{self.id}"
        return {
            "self": build_hal_link(self_href, profile=PROFILE_TASK),
            "curies": [IRI_CURIE],
            "service-desc": build_hal_link(
                f"{get_url_prefix()}/openapi.json",
                media_type=SERVICE_DESC_MEDIA_TYPE,
            ),
        }
