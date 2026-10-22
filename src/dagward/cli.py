from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from dagward.impact import analyze_impact
from dagward.loader import WorkflowLoadError, load_workflow
from dagward.models import Diagnostic, Workflow
from dagward.validation import validate_workflow

app = typer.Typer(no_args_is_help=True, add_completion=False)
console = Console(markup=False, highlight=False, emoji=False)
error_console = Console(stderr=True, markup=False, highlight=False, emoji=False)


@app.callback()
def main() -> None:
    """Analyze DAG workflows without executing tasks."""


@app.command()
def check(
    path: Annotated[
        Path, typer.Argument(metavar="PATH", help="Path to a workflow YAML file.")
    ],
) -> None:
    """Validate workflow structure, task dependencies, and directed cycles."""
    workflow = _load_workflow_or_exit(path)
    result = validate_workflow(workflow)
    if not result.valid:
        error_console.print(f"Invalid workflow {str(path)!r}:", style="red")
        _print_diagnostics(result.diagnostics)
        raise typer.Exit(code=1)

    count = len(workflow.tasks)
    task_label = "task" if count == 1 else "tasks"
    console.print(f"Valid workflow {str(path)!r}: {count} {task_label}.", style="green")


@app.command()
def impact(
    path: Annotated[
        Path, typer.Argument(metavar="PATH", help="Path to a workflow YAML file.")
    ],
    failed_task: Annotated[
        str,
        typer.Option("--fail", metavar="TASK_ID", help="ID of the failed task."),
    ],
) -> None:
    """Find downstream tasks potentially blocked under the dependency-only model."""
    workflow = _load_workflow_or_exit(path)
    result = analyze_impact(workflow, failed_task)
    if not result.valid:
        error_console.print(
            f"Cannot analyze impact for workflow {str(path)!r}:", style="red"
        )
        _print_diagnostics(result.diagnostics)
        raise typer.Exit(code=1)

    console.print(f"Failed task: {result.failed_task!r}")
    if not result.impacted_tasks:
        console.print(
            "No downstream tasks are potentially blocked under the dependency-only model."
        )
        return

    console.print(
        "Potentially blocked downstream tasks (dependency-only model): "
        f"{len(result.impacted_tasks)}"
    )
    for task_id in result.impacted_tasks:
        console.print(f"  {task_id!r}")


def _load_workflow_or_exit(path: Path) -> Workflow:
    try:
        return load_workflow(path)
    except WorkflowLoadError as exc:
        error_console.print(f"Error: {exc}", style="red")
        raise typer.Exit(code=1) from None


def _print_diagnostics(diagnostics: tuple[Diagnostic, ...]) -> None:
    for diagnostic in diagnostics:
        error_console.print(f"  [{diagnostic.code}] {diagnostic.message}")
    if any(
        diagnostic.code in {"duplicate_id", "missing_reference"}
        for diagnostic in diagnostics
    ):
        error_console.print(
            "Cycle analysis is deferred until task IDs and references are valid."
        )
