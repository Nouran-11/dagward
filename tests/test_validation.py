import pytest

from dagward.models import Diagnostic, ValidationResult, Workflow
from dagward.validation import validate_workflow


def validate_tasks(tasks: list[dict[str, object]]) -> ValidationResult:
    return validate_workflow(Workflow.model_validate({"tasks": tasks}))


@pytest.mark.parametrize(
    "tasks",
    [
        [],
        [{"id": "isolated"}],
        [
            {"id": "extract"},
            {"id": "transform", "depends_on": ["extract"]},
            {"id": "report", "depends_on": ["transform"]},
            {"id": "unrelated"},
        ],
        [
            {"id": "source"},
            {"id": "left", "depends_on": ["source"]},
            {"id": "right", "depends_on": ["source"]},
            {"id": "join", "depends_on": ["right", "left"]},
        ],
    ],
)
def test_valid_workflows_have_no_diagnostics(tasks: list[dict[str, object]]) -> None:
    result = validate_tasks(tasks)

    assert result.valid
    assert result.diagnostics == ()


def test_result_validity_reflects_diagnostics() -> None:
    result = ValidationResult(
        diagnostics=(Diagnostic(code="duplicate_id", message="Duplicate task ID"),)
    )

    assert not result.valid


def test_duplicate_ids_report_each_id_once_and_include_occurrence_count() -> None:
    result = validate_tasks([{"id": "same"}, {"id": "same"}, {"id": "same"}])

    assert not result.valid
    assert len(result.diagnostics) == 1
    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "duplicate_id"
    assert diagnostic.task_ids == ("same",)
    assert "same" in diagnostic.message
    assert "3" in diagnostic.message


def test_missing_references_identify_dependent_and_prerequisite() -> None:
    result = validate_tasks(
        [{"id": "report", "depends_on": ["missing", "also-missing"]}]
    )

    assert not result.valid
    assert len(result.diagnostics) == 2
    assert {item.code for item in result.diagnostics} == {"missing_reference"}
    for missing in ("missing", "also-missing"):
        assert any(
            "report" in item.task_ids
            and missing in item.task_ids
            and "report" in item.message
            and missing in item.message
            for item in result.diagnostics
        )


def test_self_dependency_and_missing_reference_are_both_reported() -> None:
    result = validate_tasks([{"id": "task", "depends_on": ["task", "missing"]}])

    assert {item.code for item in result.diagnostics} == {
        "self_dependency",
        "missing_reference",
    }
    self_dependency = next(
        item for item in result.diagnostics if item.code == "self_dependency"
    )
    assert self_dependency.task_ids == ("task",)
    assert "task" in self_dependency.message


@pytest.mark.parametrize(
    "tasks, cycle_ids",
    [
        (
            [{"id": "a", "depends_on": ["b"]}, {"id": "b", "depends_on": ["a"]}],
            {"a", "b"},
        ),
        (
            [
                {"id": "a", "depends_on": ["c"]},
                {"id": "b", "depends_on": ["a"]},
                {"id": "c", "depends_on": ["b"]},
                {"id": "downstream", "depends_on": ["c"]},
            ],
            {"a", "b", "c"},
        ),
    ],
)
def test_cycles_identify_participating_tasks(
    tasks: list[dict[str, object]], cycle_ids: set[str]
) -> None:
    result = validate_tasks(tasks)

    assert not result.valid
    assert len(result.diagnostics) == 1
    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "cycle"
    assert set(diagnostic.task_ids) == cycle_ids
    assert all(task_id in diagnostic.message for task_id in cycle_ids)


def test_reports_one_representative_cycle_per_cyclic_component() -> None:
    result = validate_tasks(
        [
            {"id": "a", "depends_on": ["b", "c"]},
            {"id": "b", "depends_on": ["a"]},
            {"id": "c", "depends_on": ["a"]},
            {"id": "x", "depends_on": ["y"]},
            {"id": "y", "depends_on": ["x"]},
        ]
    )

    assert len(result.diagnostics) == 2
    assert all(item.code == "cycle" for item in result.diagnostics)
    first_component, second_component = result.diagnostics
    assert set(first_component.task_ids) <= {"a", "b", "c"}
    assert len(set(first_component.task_ids)) >= 2
    assert set(second_component.task_ids) == {"x", "y"}


def test_self_dependency_does_not_hide_longer_cycles() -> None:
    result = validate_tasks(
        [
            {"id": "a", "depends_on": ["a", "b"]},
            {"id": "b", "depends_on": ["a"]},
        ]
    )

    assert {item.code for item in result.diagnostics} == {"self_dependency", "cycle"}
    cycle = next(item for item in result.diagnostics if item.code == "cycle")
    assert set(cycle.task_ids) == {"a", "b"}


@pytest.mark.parametrize(
    "invalid_task, expected_code",
    [
        ({"id": "a"}, "duplicate_id"),
        ({"id": "other", "depends_on": ["missing"]}, "missing_reference"),
    ],
)
def test_graph_analysis_waits_for_unambiguous_ids_and_references(
    invalid_task: dict[str, object], expected_code: str
) -> None:
    result = validate_tasks(
        [
            {"id": "a", "depends_on": ["b"]},
            {"id": "b", "depends_on": ["a"]},
            invalid_task,
        ]
    )

    assert {item.code for item in result.diagnostics} == {expected_code}


def test_invalid_reference_diagnostics_are_stable_and_unique() -> None:
    tasks = [
        {"id": "z", "depends_on": ["missing-b", "z", "missing-a"]},
        {"id": "duplicate", "depends_on": ["missing-a"]},
        {"id": "duplicate", "depends_on": ["missing-a"]},
    ]
    permuted = [
        {**task, "depends_on": list(reversed(task["depends_on"]))}
        for task in reversed(tasks)
    ]

    first = validate_tasks(tasks)
    second = validate_tasks(permuted)

    assert first == second
    assert len(first.diagnostics) == 5


def test_cycle_representatives_are_stable_across_input_order() -> None:
    tasks = [
        {"id": "a", "depends_on": ["c", "b"]},
        {"id": "b", "depends_on": ["a"]},
        {"id": "c", "depends_on": ["a"]},
    ]
    permuted = [
        {**task, "depends_on": list(reversed(task["depends_on"]))}
        for task in reversed(tasks)
    ]

    assert validate_tasks(tasks) == validate_tasks(permuted)


def test_task_identifiers_are_compared_verbatim() -> None:
    result = validate_tasks(
        [
            {"id": "Task"},
            {"id": " Task "},
            {"id": "task", "depends_on": ["Task", " Task "]},
        ]
    )

    assert result.valid
