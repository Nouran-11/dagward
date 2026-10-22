import pytest
from pydantic import ValidationError

from dagward.models import Task, Workflow


def test_workflow_preserves_task_and_dependency_order() -> None:
    workflow = Workflow.model_validate(
        {
            "tasks": [
                {"id": "extract"},
                {"id": "report", "depends_on": ["transform", "extract"]},
                {"id": "transform", "depends_on": ["extract"]},
            ]
        }
    )

    assert [task.id for task in workflow.tasks] == ["extract", "report", "transform"]
    assert workflow.tasks[1].depends_on == ["transform", "extract"]


def test_identifiers_are_preserved_verbatim() -> None:
    task = Task(id=" Task A ", depends_on=[" Prerequisite "])

    assert task.id == " Task A "
    assert task.depends_on == [" Prerequisite "]


def test_dependency_defaults_are_independent() -> None:
    first = Task(id="first")
    second = Task(id="second")

    first.depends_on.append("source")

    assert second.depends_on == []


@pytest.mark.parametrize("task_id", ["", " \t\n", 123, True, None, ["task"]])
def test_rejects_invalid_task_ids(task_id: object) -> None:
    with pytest.raises(ValidationError):
        Task.model_validate({"id": task_id})


@pytest.mark.parametrize(
    "dependencies",
    [None, "source", ("source",), [False], [123], [""], [" \t"], ["a", "a"]],
)
def test_rejects_invalid_dependencies(dependencies: object) -> None:
    with pytest.raises(ValidationError):
        Task.model_validate({"id": "task", "depends_on": dependencies})


@pytest.mark.parametrize(
    "payload",
    [
        None,
        [],
        {},
        {"tasks": None},
        {"tasks": {}},
        {"tasks": ()},
        {"tasks": [None]},
        {"tasks": [{}]},
        {"tasks": [], "name": "unexpected"},
        {"tasks": [{"id": "task", "command": "unexpected"}]},
    ],
)
def test_rejects_invalid_workflow_structure(payload: object) -> None:
    with pytest.raises(ValidationError):
        Workflow.model_validate(payload)


def test_empty_workflow_is_valid() -> None:
    assert Workflow(tasks=[]).tasks == []


def test_duplicate_task_ids_remain_available_for_semantic_validation() -> None:
    workflow = Workflow.model_validate({"tasks": [{"id": "same"}, {"id": "same"}]})

    assert [task.id for task in workflow.tasks] == ["same", "same"]
