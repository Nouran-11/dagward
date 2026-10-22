from pathlib import Path

import pytest
from typer.testing import CliRunner

from dagward.cli import app
from dagward.impact import analyze_impact
from dagward.loader import load_workflow
from dagward.validation import validate_workflow

EXAMPLES_DIR = Path(__file__).resolve().parents[1] / "examples"


def test_valid_example_has_branching_join_and_isolated_task() -> None:
    workflow = load_workflow(EXAMPLES_DIR / "valid.yaml")

    assert validate_workflow(workflow).valid
    assert {task.id: task.depends_on for task in workflow.tasks} == {
        "extract": [],
        "transform": ["extract"],
        "quality_check": ["extract"],
        "report": ["transform", "quality_check"],
        "housekeeping": [],
    }


@pytest.mark.parametrize(
    "failed_task, expected",
    [
        ("extract", ("quality_check", "report", "transform")),
        ("report", ()),
        ("housekeeping", ()),
    ],
)
def test_valid_example_failure_impact(
    failed_task: str, expected: tuple[str, ...]
) -> None:
    workflow = load_workflow(EXAMPLES_DIR / "valid.yaml")

    result = analyze_impact(workflow, failed_task)

    assert result.valid
    assert result.impacted_tasks == expected


@pytest.mark.parametrize(
    "filename, expected_code",
    [
        ("duplicate_ids.yaml", "duplicate_id"),
        ("missing_reference.yaml", "missing_reference"),
        ("self_dependency.yaml", "self_dependency"),
        ("cycle.yaml", "cycle"),
    ],
)
def test_invalid_example_demonstrates_one_dependency_error(
    filename: str, expected_code: str
) -> None:
    workflow = load_workflow(EXAMPLES_DIR / filename)

    result = validate_workflow(workflow)

    assert not result.valid
    assert tuple(diagnostic.code for diagnostic in result.diagnostics) == (
        expected_code,
    )


def test_check_accepts_bundled_valid_example() -> None:
    result = CliRunner().invoke(app, ["check", str(EXAMPLES_DIR / "valid.yaml")])

    assert result.exit_code == 0
    assert "Valid workflow" in result.stdout
    assert "5 tasks" in " ".join(result.stdout.split())
    assert result.stderr == ""


def test_impact_reports_bundled_example_dependents() -> None:
    result = CliRunner().invoke(
        app, ["impact", str(EXAMPLES_DIR / "valid.yaml"), "--fail", "extract"]
    )

    assert result.exit_code == 0
    assert "potentially blocked" in result.stdout.lower()
    assert "dependency-only" in result.stdout
    assert [
        line.strip() for line in result.stdout.splitlines() if line.startswith("  '")
    ] == ["'quality_check'", "'report'", "'transform'"]
    assert result.stderr == ""
