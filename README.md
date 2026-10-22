# DAGWard

DAGWard is a Python CLI for validating DAG-based workflows and analyzing which
downstream tasks may be blocked by a failed task. It analyzes dependencies without
executing workflows.

Failure impact describes potential blocking under a simplified dependency-only
model. Retries, fallback paths, and conditional execution are outside the v0.1
scope.

## Development status

The package foundation, CLI help, safe YAML loading, and structural validation are
available. The loader and models are internal Python APIs; the CLI currently
provides help only. Remaining increments:

1. Dependency validation and cycle diagnostics via `dagward check PATH`.
2. Transitive downstream analysis via `dagward impact PATH --fail TASK_ID`.
3. Synthetic examples, CLI usage documentation, and end-to-end tests.

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

Structural validation preserves the task list. Duplicate task IDs, missing
references, self-dependencies, and cycles will be checked in the dependency
validation increment.

Use unique YAML mapping keys: the current loader uses PyYAML's `safe_load`, which
keeps the last value for a repeated mapping key. Duplicate mapping keys are not
diagnosed by structural validation.

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
