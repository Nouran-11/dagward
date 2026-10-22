from pathlib import Path

import yaml
from pydantic import ValidationError

from dagward.models import Workflow


class WorkflowLoadError(ValueError):
    """A workflow file could not be read, parsed, or structurally validated."""


def load_workflow(path: Path) -> Workflow:
    """Read one UTF-8 YAML document and validate its workflow structure."""
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeError as exc:
        raise WorkflowLoadError(
            f"Cannot read workflow {str(path)!r}: expected UTF-8 text"
        ) from exc
    except OSError as exc:
        raise WorkflowLoadError(
            f"Cannot read workflow {str(path)!r}: {exc.strerror or type(exc).__name__}"
        ) from exc

    data = _parse_yaml(text, path)
    try:
        return Workflow.model_validate(data)
    except ValidationError as exc:
        diagnostics = sorted(
            f"  {_field_path(error['loc'])}: {error['msg']}"
            for error in exc.errors(
                include_url=False, include_context=False, include_input=False
            )
        )
        raise WorkflowLoadError(
            f"Invalid workflow {str(path)!r}:\n" + "\n".join(diagnostics)
        ) from exc
    except RecursionError as exc:
        raise WorkflowLoadError(
            f"Invalid workflow {str(path)!r}: input is nested too deeply"
        ) from exc


def _parse_yaml(text: str, path: Path) -> object:
    try:
        return yaml.safe_load(text)
    except yaml.YAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        location = f" at line {mark.line + 1}, column {mark.column + 1}" if mark else ""
        problem = getattr(exc, "problem", None) or "invalid YAML syntax"
        raise WorkflowLoadError(
            f"Invalid YAML in {str(path)!r}{location}: {problem}"
        ) from exc
    except RecursionError as exc:
        raise WorkflowLoadError(
            f"Invalid YAML in {str(path)!r}: input is nested too deeply"
        ) from exc
    except (
        ValueError,
        TypeError,
        KeyError,
        IndexError,
        OverflowError,
        AttributeError,
    ) as exc:
        # SafeLoader's scalar constructors can raise these instead of YAMLError.
        raise WorkflowLoadError(
            f"Invalid YAML in {str(path)!r}: invalid scalar or mapping value"
        ) from exc


def _field_path(location: tuple[str | int, ...]) -> str:
    path = ""
    for component in location:
        if isinstance(component, int):
            path += f"[{component}]"
        else:
            path += f".{component}" if path else component
    return path or "workflow"
