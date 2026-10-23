import os
import subprocess
import sys
from pathlib import Path

import pytest
from rich.ansi import AnsiDecoder
from typer.testing import CliRunner

from dagward.cli import app

runner = CliRunner()


def test_help() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "Analyze DAG workflows without executing tasks." in result.output
    assert "check" in result.output
    assert "impact" in result.output


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


@pytest.mark.parametrize("command", ["check", "impact"])
@pytest.mark.parametrize(
    "content",
    [None, "tasks: [", "tasks:\n  - id: report\n    depends_on: [missing]\n"],
)
def test_error_paths_are_preserved_in_narrow_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, command: str, content: str | None
) -> None:
    monkeypatch.setenv("COLUMNS", "24")
    path = tmp_path / ("[red]workflow-" + "long-name-" * 8 + ".yaml")
    if content is not None:
        path.write_text(content, encoding="utf-8")
    arguments = [command, str(path)]
    if command == "impact":
        arguments.extend(["--fail", "report"])

    result = runner.invoke(app, arguments)

    assert result.exit_code == 1
    assert repr(str(path)) in result.stderr
    assert result.stdout == ""


def test_check_success_path_is_preserved_in_narrow_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("COLUMNS", "24")
    path = tmp_path / ("[red]workflow-" + "long-name-" * 8 + ".yaml")
    path.write_text("tasks: []\n", encoding="utf-8")

    result = runner.invoke(app, ["check", str(path)])

    assert result.exit_code == 0
    assert repr(str(path)) in result.stdout
    assert "0 tasks" in result.stdout
    assert result.stderr == ""


def test_check_identifiers_are_preserved_in_narrow_diagnostics(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("COLUMNS", "24")
    path = tmp_path / "workflow.yaml"
    missing_id = "[red]" + "missing-task-" * 8 + "[/red]:smile:"
    path.write_text(
        f"tasks:\n  - id: report\n    depends_on: ['{missing_id}']\n", encoding="utf-8"
    )

    result = runner.invoke(app, ["check", str(path)])

    assert result.exit_code == 1
    assert repr(missing_id) in result.stderr
    assert result.stdout == ""


def test_impact_help() -> None:
    result = runner.invoke(app, ["impact", "--help"])
    visible_output = "\n".join(
        line.plain for line in AnsiDecoder().decode(result.output)
    )

    assert result.exit_code == 0
    assert "PATH" in visible_output
    assert "--fail" in visible_output
    assert "downstream" in visible_output.lower()


def test_impact_help_with_github_actions_color() -> None:
    environment = os.environ | {"GITHUB_ACTIONS": "true", "TERM": "xterm-256color"}
    environment.pop("NO_COLOR", None)
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from dagward.cli import app; app()",
            "impact",
            "--help",
        ],
        capture_output=True,
        text=True,
        env=environment,
        check=False,
        timeout=10,
    )
    visible_output = "\n".join(
        line.plain for line in AnsiDecoder().decode(result.stdout)
    )

    assert result.returncode == 0
    assert "\x1b[" in result.stdout
    assert "PATH" in visible_output
    assert "--fail" in visible_output
    assert "downstream" in visible_output.lower()
    assert result.stderr == ""


@pytest.mark.parametrize(
    "arguments",
    [
        ["impact"],
        ["impact", "workflow.yaml"],
        ["impact", "--fail", "extract"],
        ["impact", "workflow.yaml", "--fail"],
        ["impact", "workflow.yaml", "--fail", "extract", "--unknown"],
    ],
)
def test_impact_usage_errors_exit_two(arguments: list[str]) -> None:
    result = runner.invoke(app, arguments)

    assert result.exit_code == 2
    assert result.stderr
    assert result.stdout == ""
    assert "Traceback" not in result.output


@pytest.mark.parametrize(
    "failed_id, expected",
    [
        ("extract", ["merge", "report", "transform"]),
        ("transform", ["merge", "report"]),
        ("report", []),
        ("unrelated", []),
    ],
)
def test_impact_reports_only_sorted_transitive_dependents(
    tmp_path: Path, failed_id: str, expected: list[str]
) -> None:
    path = tmp_path / "workflow.yaml"
    path.write_text(
        "tasks:\n"
        "  - id: report\n"
        "    depends_on: [merge]\n"
        "  - id: merge\n"
        "    depends_on: [extract, transform]\n"
        "  - id: transform\n"
        "    depends_on: [extract]\n"
        "  - id: extract\n"
        "  - id: unrelated\n",
        encoding="utf-8",
    )

    result = runner.invoke(app, ["impact", str(path), "--fail", failed_id])

    assert result.exit_code == 0
    assert repr(failed_id) in result.stdout
    assert "potentially blocked" in result.stdout.lower()
    assert "dependency-only" in result.stdout
    assert result.stderr == ""
    listed_ids = [
        line.strip() for line in result.stdout.splitlines() if line.startswith("  '")
    ]
    assert listed_ids == [repr(task_id) for task_id in expected]
    if expected:
        assert any(
            "potentially blocked" in line.lower() and str(len(expected)) in line
            for line in result.stdout.splitlines()
        )
    else:
        assert "no downstream tasks" in result.stdout.lower()


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
def test_impact_rejects_invalid_workflows_before_looking_up_failed_task(
    tmp_path: Path, content: str, expected_text: str
) -> None:
    path = tmp_path / "[red]workflow.yaml"
    path.write_text(content, encoding="utf-8")

    result = runner.invoke(app, ["impact", str(path), "--fail", "unknown-failure"])

    assert result.exit_code == 1
    assert expected_text.lower() in result.stderr.lower()
    assert path.name in result.stderr
    assert "unknown-failure" not in result.stderr
    assert result.stdout == ""
    assert "Traceback" not in result.output


def test_impact_unreadable_path_is_an_input_error(tmp_path: Path) -> None:
    path = tmp_path / "[red]missing.yaml"

    result = runner.invoke(app, ["impact", str(path), "--fail", "extract"])

    assert result.exit_code == 1
    assert "Cannot read workflow" in result.stderr
    assert path.name in result.stderr
    assert result.stdout == ""
    assert "Traceback" not in result.output


def test_impact_invalid_utf8_is_an_input_error(tmp_path: Path) -> None:
    path = tmp_path / "workflow.yaml"
    path.write_bytes(b"tasks: [\xff]")

    result = runner.invoke(app, ["impact", str(path), "--fail", "extract"])

    assert result.exit_code == 1
    assert path.name in result.stderr
    assert result.stdout == ""
    assert "Traceback" not in result.output


@pytest.mark.parametrize("content", ["tasks: []\n", "tasks:\n  - id: Extract\n"])
def test_impact_unknown_failed_task_is_an_input_error(
    tmp_path: Path, content: str
) -> None:
    path = tmp_path / "workflow.yaml"
    path.write_text(content, encoding="utf-8")
    failed_id = "[red]extract[/red]"

    result = runner.invoke(app, ["impact", str(path), "--fail", failed_id])

    assert result.exit_code == 1
    assert failed_id in result.stderr
    assert "unknown" in result.stderr.lower()
    assert result.stdout == ""
    assert "Traceback" not in result.output


def test_impact_task_identifiers_preserve_literal_text_and_whitespace(
    tmp_path: Path,
) -> None:
    path = tmp_path / "workflow.yaml"
    failed_id = " [red]Extract[/red] "
    dependent_id = " [green]Report[/green] "
    path.write_text(
        "tasks:\n"
        f"  - id: '{failed_id}'\n"
        f"  - id: '{dependent_id}'\n"
        f"    depends_on: ['{failed_id}']\n"
        "  - id: Extract\n",
        encoding="utf-8",
    )

    result = runner.invoke(app, ["impact", str(path), "--fail", failed_id])

    assert result.exit_code == 0
    assert repr(failed_id) in result.stdout
    assert repr(dependent_id) in result.stdout
    assert "  'Extract'" not in result.stdout
    assert result.stderr == ""


@pytest.mark.parametrize("has_dependents", [False, True])
def test_impact_identifiers_are_preserved_in_narrow_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, has_dependents: bool
) -> None:
    monkeypatch.setenv("COLUMNS", "24")
    path = tmp_path / "workflow.yaml"
    failed_id = " [red]" + "failed-task-" * 8 + "[/red]:smile: "
    dependent_id = " [green]" + "downstream-task-" * 8 + "[/green]:smile: "
    content = f"tasks:\n  - id: '{failed_id}'\n"
    if has_dependents:
        content += f"  - id: '{dependent_id}'\n    depends_on: ['{failed_id}']\n"
    path.write_text(content, encoding="utf-8")

    result = runner.invoke(app, ["impact", str(path), "--fail", failed_id])

    assert result.exit_code == 0
    assert f"Failed task: {failed_id!r}" in result.stdout
    if has_dependents:
        assert f"  {dependent_id!r}" in result.stdout.splitlines()
    else:
        assert "No downstream tasks are potentially blocked" in result.stdout
    assert result.stderr == ""


def test_impact_failed_task_lookup_is_case_sensitive(tmp_path: Path) -> None:
    path = tmp_path / "workflow.yaml"
    path.write_text("tasks:\n  - id: Extract\n", encoding="utf-8")

    result = runner.invoke(app, ["impact", str(path), "--fail", "extract"])

    assert result.exit_code == 1
    assert "extract" in result.stderr
    assert "unknown" in result.stderr.lower()
    assert result.stdout == ""
