# DAGWard

DAGWard is a Python CLI for validating DAG-based workflows and analyzing which
downstream tasks may be blocked by a failed task. It analyzes dependencies without
executing workflows.

Failure impact describes potential blocking under a simplified dependency-only
model. Retries, fallback paths, and conditional execution are outside the v0.1
scope.

## Development status

The package foundation and CLI help are available. Workflow validation and impact
analysis are planned for subsequent increments:

1. Safe YAML loading and structural validation.
2. Dependency validation and cycle diagnostics via `dagward check PATH`.
3. Transitive downstream analysis via `dagward impact PATH --fail TASK_ID`.
4. Synthetic examples, usage documentation, and end-to-end tests.

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
