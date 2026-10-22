# DAGWard

DAGWard is a Python CLI for validating DAG-based workflows and analyzing which
downstream tasks may be blocked by a failed task. It analyzes dependencies without
executing workflows.

Failure impact describes potential blocking under a simplified dependency-only
model. Retries, fallback paths, and conditional execution are outside the v0.1
scope.

## Development status

The `check` command validates workflow structure, task dependencies, and directed
cycles. Remaining increments:

1. Transitive downstream analysis via `dagward impact PATH --fail TASK_ID`.
2. Bundled synthetic examples and final packaging checks.

## Workflow format

A workflow is one UTF-8 YAML document with a top-level `tasks` list:

```yaml
tasks:
  - id: extract
  - id: transform
    depends_on: [extract]
  - id: report
    depends_on: [transform]
```

- Each task requires an `id` that is a nonblank string. IDs are case-sensitive and
  preserved exactly, including surrounding whitespace.
- `depends_on` lists prerequisite task IDs. It defaults to an empty list when
  omitted. Repeated entries and blank or non-string entries are rejected.
- Unknown fields, explicit nulls, and wrong types are rejected. Quote IDs such as
  `"yes"`, `"123"`, or `"2026-01-01"` so YAML treats them as strings.
- An empty workflow (`tasks: []`) is allowed. An empty document is invalid.
- Python object tags are rejected; workflows are data and never executed.

Task IDs must be unique, every prerequisite must refer to an existing task, and
tasks must not depend on themselves. Longer directed cycles are also invalid.

Use unique YAML mapping keys: the current loader uses PyYAML's `safe_load`, which
keeps the last value for a repeated mapping key. Duplicate mapping keys are not
diagnosed by structural validation.

## Check a workflow

Save the workflow above as `workflow.yaml`, then run:

```sh
uv run dagward check workflow.yaml
```

A valid workflow prints a success message with its task count. Invalid workflows
print actionable diagnostics to stderr. For example:

```text
[missing_reference] Task 'report' depends on 'transform', but no task has that ID.
[cycle] Dependency cycle: 'extract' -> 'transform' -> 'extract'. Arrows show prerequisite -> dependent.
```

Arrows always point from a prerequisite to a dependent task. Cycle diagnostics
show one example cycle per cyclic group; the displayed path may not include all
tasks in that group. Self-dependencies are reported separately. Cycle analysis
runs once task IDs are unique and prerequisite references exist; fix any such
errors and rerun to check for cycles. Diagnostic ordering is deterministic.

| Exit code | Meaning |
| --- | --- |
| `0` | The workflow is valid. |
| `1` | The file could not be read, parsed, or validated. |
| `2` | CLI usage error, such as a missing argument or unknown option. |

## Local development

Use Python 3.12 and [uv](https://docs.astral.sh/uv/).

```sh
uv sync --locked
uv run dagward --help
```

The development environment includes pytest and Ruff:

```sh
uv run pytest
uv run ruff check .
uv run ruff format --check .
```
