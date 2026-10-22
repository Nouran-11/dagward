from dataclasses import dataclass
from typing import Annotated

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StrictStr,
    field_validator,
)


def _nonblank_id(value: str) -> str:
    if not value.strip():
        raise ValueError("Task IDs must not be blank")
    return value


TaskId = Annotated[StrictStr, AfterValidator(_nonblank_id)]


class Task(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    id: TaskId
    depends_on: list[TaskId] = Field(default_factory=list)

    @field_validator("depends_on")
    @classmethod
    def unique_prerequisites(cls, dependencies: list[str]) -> list[str]:
        if len(dependencies) != len(set(dependencies)):
            raise ValueError("depends_on must not contain repeated task IDs")
        return dependencies


class Workflow(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    tasks: list[Task]


@dataclass(frozen=True)
class Diagnostic:
    code: str
    message: str
    task_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class ValidationResult:
    diagnostics: tuple[Diagnostic, ...] = ()

    @property
    def valid(self) -> bool:
        return not self.diagnostics
