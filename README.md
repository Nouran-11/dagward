# DAGWard

DAGWard is a Python CLI for validating DAG-based workflows and analyzing which
downstream tasks may be blocked by a failed task. It analyzes dependencies without
executing workflows.

Failure impact describes potential blocking under a simplified dependency-only
model. Retries, fallback paths, and conditional execution are outside the v0.1
scope.

## Development status

The `check` command validates workflow structure, task dependencies, and directed
cycles. The `impact` command identifies transitive downstream tasks potentially
blocked by a chosen failed task. Synthetic examples are included for both
commands. The package is currently a development build (`0.1.0.dev0`).

## Try the bundled examples

From the project directory, install the development environment and analyze the
synthetic branching workflow:

```sh
uv sync --locked
uv run dagward check examples/valid.yaml
uv run dagward impact examples/valid.yaml --fail extract
```

The valid example contains five tasks. A failure of `extract` potentially blocks
`quality_check`, `report`, and `transform`, in that sorted order. The independent
`housekeeping` task is unaffected under the dependency-only model.

Each invalid example isolates one dependency problem. These commands return exit
code `1`:

| Example | Diagnostic |
| --- | --- |
| `examples/duplicate_ids.yaml` | `duplicate_id` |
| `examples/missing_reference.yaml` | `missing_reference` |
| `examples/self_dependency.yaml` | `self_dependency` |
| `examples/cycle.yaml` | `cycle` |

For example:

```sh
uv run dagward check examples/cycle.yaml
```

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

## Analyze failure impact

Using the same `workflow.yaml`, choose an existing task ID:

```sh
uv run dagward impact workflow.yaml --fail extract
```

```text
Failed task: 'extract'
Potentially blocked downstream tasks (dependency-only model): 2
  'report'
  'transform'
```

The command first validates the entire workflow as a DAG. It then lists all
transitive downstream dependents once, sorted by ID. The failed task, its
ancestors, and unrelated tasks are excluded. Task IDs must match exactly,
including case and whitespace.

A leaf or isolated task succeeds with an explicit message that no downstream
tasks are potentially blocked. An unknown failed task produces an input error.
Invalid workflows produce validation diagnostics instead of a partial impact
report.

This analysis describes potential blocking under a dependency-only model. It does
not model retries, fallback paths, or conditional execution.

Both commands use these exit codes:

| Exit code | Meaning |
| --- | --- |
| `0` | The command completed successfully. |
| `1` | The file could not be read, parsed, or validated, or the failed task is unknown. |
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

Build an installable wheel and source archive locally:

```sh
uv build
```

Artifacts are written to `dist/`. The source archive includes the examples and
tests. After installing the wheel or source archive into a Python environment,
use `dagward check PATH` and `dagward impact PATH --fail TASK_ID` directly.

## Automated checks

GitHub Actions runs the test suite, Ruff lint and formatting checks, and a package
build on pushes to `main` and on pull requests. The workflow uses Python 3.12 and
installs dependencies from `uv.lock` with `uv sync --locked`.
