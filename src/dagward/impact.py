import networkx as nx

from dagward.graph import build_graph
from dagward.models import Diagnostic, ImpactResult, Workflow
from dagward.validation import validate_workflow


def analyze_impact(workflow: Workflow, failed_task: str) -> ImpactResult:
    """Find potentially blocked downstream tasks under dependency-only semantics."""
    validation = validate_workflow(workflow)
    if not validation.valid:
        return ImpactResult(failed_task=failed_task, diagnostics=validation.diagnostics)

    if not any(task.id == failed_task for task in workflow.tasks):
        return ImpactResult(
            failed_task=failed_task,
            diagnostics=(
                Diagnostic(
                    code="unknown_task",
                    message=f"Failed task {failed_task!r} is not in the workflow.",
                    task_ids=(failed_task,),
                ),
            ),
        )

    impacted_tasks = tuple(sorted(nx.descendants(build_graph(workflow), failed_task)))
    return ImpactResult(failed_task=failed_task, impacted_tasks=impacted_tasks)
