from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from dagward.loader import WorkflowLoadError, load_workflow
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
    try:
        workflow = load_workflow(path)
    except WorkflowLoadError as exc:
        error_console.print(f"Error: {exc}", style="red")
        raise typer.Exit(code=1) from None

    result = validate_workflow(workflow)
    if not result.valid:
        error_console.print(f"Invalid workflow {str(path)!r}:", style="red")
        for diagnostic in result.diagnostics:
            error_console.print(f"  [{diagnostic.code}] {diagnostic.message}")
        if any(
            diagnostic.code in {"duplicate_id", "missing_reference"}
            for diagnostic in result.diagnostics
        ):
            error_console.print(
                "Cycle analysis is deferred until task IDs and references are valid."
            )
        raise typer.Exit(code=1)

    count = len(workflow.tasks)
    task_label = "task" if count == 1 else "tasks"
    console.print(f"Valid workflow {str(path)!r}: {count} {task_label}.", style="green")
