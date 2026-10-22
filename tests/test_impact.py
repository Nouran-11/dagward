import pytest

from dagward.impact import analyze_impact
from dagward.models import Task, Workflow
from dagward.validation import validate_workflow


def test_chain_impact_excludes_ancestors_and_failed_task() -> None:
    workflow = Workflow(
        tasks=[
            Task(id="extract"),
            Task(id="transform", depends_on=["extract"]),
            Task(id="report", depends_on=["transform"]),
            Task(id="publish", depends_on=["report"]),
        ]
    )

    result = analyze_impact(workflow, "transform")

    assert result.valid
    assert result.failed_task == "transform"
    assert result.impacted_tasks == ("publish", "report")
    assert result.diagnostics == ()


def test_branching_and_diamond_impact_is_sorted_and_unique() -> None:
    workflow = Workflow(
        tasks=[
            Task(id="source"),
            Task(id="right", depends_on=["source"]),
            Task(id="left", depends_on=["source"]),
            Task(id="join", depends_on=["right", "left"]),
            Task(id="unrelated"),
            Task(id="unrelated-child", depends_on=["unrelated"]),
        ]
    )

    result = analyze_impact(workflow, "source")

    assert result.valid
    assert result.impacted_tasks == ("join", "left", "right")


@pytest.mark.parametrize("failed_task", ["leaf", "isolated"])
def test_tasks_without_dependents_have_empty_successful_impact(
    failed_task: str,
) -> None:
    workflow = Workflow(
        tasks=[
            Task(id="source"),
            Task(id="leaf", depends_on=["source"]),
            Task(id="isolated"),
        ]
    )

    result = analyze_impact(workflow, failed_task)

    assert result.valid
    assert result.failed_task == failed_task
    assert result.impacted_tasks == ()
    assert result.diagnostics == ()


@pytest.mark.parametrize(
    "tasks",
    [
        [Task(id="source"), Task(id="source")],
        [Task(id="source", depends_on=["missing"])],
        [Task(id="source", depends_on=["source"])],
        [
            Task(id="source", depends_on=["other"]),
            Task(id="other", depends_on=["source"]),
        ],
    ],
)
@pytest.mark.parametrize("failed_task", ["source", "unknown"])
def test_invalid_workflows_return_validation_diagnostics_before_impact(
    tasks: list[Task], failed_task: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    workflow = Workflow(tasks=tasks)
    expected = validate_workflow(workflow)

    def unexpected_graph_build(_: Workflow) -> None:
        pytest.fail("Impact analysis must not build a graph for an invalid workflow")

    monkeypatch.setattr("dagward.impact.build_graph", unexpected_graph_build)

    result = analyze_impact(workflow, failed_task)

    assert not result.valid
    assert result.failed_task == failed_task
    assert result.impacted_tasks == ()
    assert result.diagnostics == expected.diagnostics


@pytest.mark.parametrize("tasks", [[], [Task(id="source")]])
def test_unknown_failed_task_is_reported_including_empty_workflow(
    tasks: list[Task],
) -> None:
    result = analyze_impact(Workflow(tasks=tasks), "missing")

    assert not result.valid
    assert result.failed_task == "missing"
    assert result.impacted_tasks == ()
    assert len(result.diagnostics) == 1
    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "unknown_task"
    assert diagnostic.task_ids == ("missing",)
    assert "missing" in diagnostic.message


def test_task_identifiers_are_preserved_and_compared_verbatim() -> None:
    workflow = Workflow(
        tasks=[
            Task(id="Task"),
            Task(id=" Task "),
            Task(id="task", depends_on=["Task"]),
            Task(id=" child ", depends_on=[" Task "]),
        ]
    )

    assert analyze_impact(workflow, "Task").impacted_tasks == ("task",)
    assert analyze_impact(workflow, " Task ").impacted_tasks == (" child ",)
    assert not analyze_impact(workflow, "TASK").valid


def test_impact_is_independent_of_task_and_prerequisite_order() -> None:
    workflow = Workflow(
        tasks=[
            Task(id="source"),
            Task(id="b", depends_on=["source"]),
            Task(id="a", depends_on=["source"]),
            Task(id="join", depends_on=["b", "a"]),
        ]
    )
    permuted = Workflow(
        tasks=[
            Task(id=task.id, depends_on=list(reversed(task.depends_on)))
            for task in reversed(workflow.tasks)
        ]
    )

    assert analyze_impact(workflow, "source") == analyze_impact(permuted, "source")


def test_impact_handles_long_chains_without_recursion() -> None:
    ids = [f"task-{index:04}" for index in range(1500)]
    workflow = Workflow(
        tasks=[Task(id=ids[0])]
        + [
            Task(id=task_id, depends_on=[prerequisite])
            for prerequisite, task_id in zip(ids[:-1], ids[1:], strict=True)
        ]
    )

    result = analyze_impact(workflow, ids[0])

    assert result.valid
    assert result.impacted_tasks == tuple(ids[1:])
