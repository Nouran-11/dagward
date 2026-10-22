from pathlib import Path

import pytest
from typer.testing import CliRunner

from dagward.cli import app

runner = CliRunner()


def test_help() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "Analyze DAG workflows without executing tasks." in result.output
    assert "check" in result.output


def test_missing_command_shows_help() -> None:
    result = runner.invoke(app, [])

    assert result.exit_code == 2
    assert "Usage:" in result.output


def test_unknown_command_is_usage_error() -> None:
    result = runner.invoke(app, ["unknown"])

    assert result.exit_code == 2
    assert "No such command" in result.output


def test_check_help() -> None:
    result = runner.invoke(app, ["check", "--help"])

    assert result.exit_code == 0
    assert "PATH" in result.output
    assert "workflow" in result.output.lower()


@pytest.mark.parametrize(
    "arguments",
    [["check"], ["check", "workflow.yaml", "--unknown"]],
)
def test_check_usage_errors_exit_two(arguments: list[str]) -> None:
    result = runner.invoke(app, arguments)

    assert result.exit_code == 2
    assert "Usage:" in result.output


@pytest.mark.parametrize(
    "tasks, count", [("tasks: []\n", 0), ("tasks:\n  - id: single\n", 1)]
)
def test_check_valid_workflow_succeeds(tmp_path: Path, tasks: str, count: int) -> None:
    path = tmp_path / "workflow.yaml"
    path.write_text(tasks, encoding="utf-8")

    result = runner.invoke(app, ["check", str(path)])

    assert result.exit_code == 0
    assert "Valid workflow" in result.stdout
    assert str(count) in result.stdout
    assert "task" in result.stdout
    assert result.stderr == ""


@pytest.mark.parametrize(
    "content, expected_text",
    [
        ("tasks: [", "Invalid YAML"),
        ("tasks:\n  - id: 123\n", "tasks[0].id"),
        ("!!python/object:builtins.object {}", "Invalid YAML"),
        ("tasks:\n  - id: same\n  - id: same\n", "same"),
        ("tasks:\n  - id: report\n    depends_on: [missing]\n", "missing"),
        ("tasks:\n  - id: loop\n    depends_on: [loop]\n", "loop"),
        (
            "tasks:\n  - id: a\n    depends_on: [b]\n  - id: b\n    depends_on: [a]\n",
            "cycle",
        ),
    ],
)
def test_check_input_failures_are_readable_errors(
    tmp_path: Path, content: str, expected_text: str
) -> None:
    path = tmp_path / "[red]workflow.yaml"
    path.write_text(content, encoding="utf-8")

    result = runner.invoke(app, ["check", str(path)])

    assert result.exit_code == 1
    assert expected_text.lower() in result.stderr.lower()
    assert path.name in result.stderr
    assert result.stdout == ""
    assert "Traceback" not in result.output


def test_check_unreadable_path_is_an_input_error(tmp_path: Path) -> None:
    path = tmp_path / "[red]missing.yaml"

    result = runner.invoke(app, ["check", str(path)])

    assert result.exit_code == 1
    assert "Cannot read workflow" in result.stderr
    assert path.name in result.stderr
    assert result.stdout == ""
    assert "Traceback" not in result.output


def test_check_task_identifiers_are_rendered_literally(tmp_path: Path) -> None:
    path = tmp_path / "workflow.yaml"
    missing_id = "[red]missing[/red]"
    path.write_text(
        f"tasks:\n  - id: report\n    depends_on: ['{missing_id}']\n",
        encoding="utf-8",
    )

    result = runner.invoke(app, ["check", str(path)])

    assert result.exit_code == 1
    assert missing_id in result.stderr
