import enum
from pydantic import BaseModel, computed_field, field_validator
from typing import Any

from humps import decamelize

from ... import config


class TaskSubmitResponse(BaseModel):
    """Response model for submitting a task"""
    task_id: str

    @computed_field(description="The list of past events in this incident")
    @property
    def task_uri(self) -> str:
        return f"{config.API_URL_ROOT}{config.API_PREFIX}{config.API_URL}/task/{self.task_id}"


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

    @field_validator("args", mode="before")
    @classmethod
    def normalize_args(cls, v):
        if v is None or not isinstance(v, dict):
            return v

        v = v.copy()
        rm = v.get("request_model")

        if hasattr(rm, "model_dump"):
            v["request_model"] = rm.model_dump(by_alias=False)
        elif isinstance(rm, dict):
            v["request_model"] = decamelize(rm)


        return v


class Task(BaseModel):
    id: str
    status: TaskStatus = TaskStatus.pending
    result: Any | None = None
    command: TaskCommand | None = None
