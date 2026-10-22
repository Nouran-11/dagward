from collections import Counter

from dagward.graph import build_graph, find_cycles
from dagward.models import Diagnostic, ValidationResult, Workflow


def validate_workflow(workflow: Workflow) -> ValidationResult:
    """Validate dependency rules after loading and structural validation."""
    counts = Counter(task.id for task in workflow.tasks)
    diagnostics = {
        Diagnostic(
            code="duplicate_id",
            message=f"Task ID {task_id!r} occurs {count} times; task IDs must be unique.",
            task_ids=(task_id,),
        )
        for task_id, count in counts.items()
        if count > 1
    }

    for task in workflow.tasks:
        for prerequisite in task.depends_on:
            if prerequisite == task.id:
                diagnostics.add(
                    Diagnostic(
                        code="self_dependency",
                        message=f"Task {task.id!r} depends on itself.",
                        task_ids=(task.id,),
                    )
                )
            elif prerequisite not in counts:
                diagnostics.add(
                    Diagnostic(
                        code="missing_reference",
                        message=(
                            f"Task {task.id!r} depends on {prerequisite!r}, "
                            "but no task has that ID."
                        ),
                        task_ids=(task.id, prerequisite),
                    )
                )

    # Ambiguous or missing nodes would make cycle diagnostics misleading.
    if not any(
        diagnostic.code in {"duplicate_id", "missing_reference"}
        for diagnostic in diagnostics
    ):
        for cycle in find_cycles(build_graph(workflow)):
            path = " -> ".join(repr(task_id) for task_id in cycle)
            diagnostics.add(
                Diagnostic(
                    code="cycle",
                    message=(
                        f"Dependency cycle: {path}. "
                        "Arrows show prerequisite -> dependent."
                    ),
                    task_ids=cycle[:-1],
                )
            )

    return ValidationResult(
        diagnostics=tuple(
            sorted(diagnostics, key=lambda item: (item.code, item.task_ids))
        )
    )
