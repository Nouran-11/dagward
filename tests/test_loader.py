import os
from pathlib import Path

import pytest

from dagward.loader import WorkflowLoadError, load_workflow


def test_loads_utf8_workflow(tmp_path: Path) -> None:
    path = tmp_path / "workflow.yaml"
    path.write_text(
        "tasks:\n  - id: مرحلة\n  - id: report\n    depends_on: [مرحلة]\n",
        encoding="utf-8",
    )

    workflow = load_workflow(path)

    assert [task.id for task in workflow.tasks] == ["مرحلة", "report"]
    assert workflow.tasks[0].depends_on == []
    assert workflow.tasks[1].depends_on == ["مرحلة"]


def test_loads_empty_workflow(tmp_path: Path) -> None:
    path = tmp_path / "workflow.yaml"
    path.write_text("tasks: []\n", encoding="utf-8")

    assert load_workflow(path).tasks == []


def test_quoted_boolean_numeric_and_date_ids_remain_strings(tmp_path: Path) -> None:
    path = tmp_path / "workflow.yaml"
    path.write_text(
        'tasks:\n  - id: "true"\n  - id: "123"\n  - id: "2026-10-22"\n'
        '  - id: sink\n    depends_on: ["true", "123", "2026-10-22"]\n',
        encoding="utf-8",
    )

    workflow = load_workflow(path)

    assert [task.id for task in workflow.tasks] == ["true", "123", "2026-10-22", "sink"]
    assert workflow.tasks[-1].depends_on == ["true", "123", "2026-10-22"]


@pytest.mark.parametrize(
    "content",
    ["", "# comment only\n", "null\n", "42\n", "[]\n", "tasks: null\n"],
)
def test_rejects_invalid_document_structure(tmp_path: Path, content: str) -> None:
    path = tmp_path / "workflow.yaml"
    path.write_text(content, encoding="utf-8")

    with pytest.raises(WorkflowLoadError):
        load_workflow(path)


def test_schema_error_identifies_invalid_field(tmp_path: Path) -> None:
    path = tmp_path / "workflow.yaml"
    path.write_text("tasks:\n  - id: 123\n", encoding="utf-8")

    with pytest.raises(WorkflowLoadError, match=r"tasks.*0.*id"):
        load_workflow(path)


def test_schema_error_does_not_dump_input_values(tmp_path: Path) -> None:
    path = tmp_path / "workflow.yaml"
    private_value = "private-input-value"
    path.write_text(
        f"tasks:\n  - id: {{private: {private_value}}}\n    command: {private_value}\n",
        encoding="utf-8",
    )

    with pytest.raises(WorkflowLoadError) as error:
        load_workflow(path)

    message = str(error.value)
    assert "tasks[0].id" in message
    assert "tasks[0].command" in message
    assert private_value not in message


def test_schema_diagnostics_do_not_depend_on_unknown_field_order(
    tmp_path: Path,
) -> None:
    path = tmp_path / "workflow.yaml"
    messages = []
    for content in [
        "tasks: []\nzeta: 1\nalpha: 2\n",
        "alpha: 2\nzeta: 1\ntasks: []\n",
    ]:
        path.write_text(content, encoding="utf-8")
        with pytest.raises(WorkflowLoadError) as error:
            load_workflow(path)
        messages.append(str(error.value))

    assert messages[0] == messages[1]


def test_yaml_error_includes_location(tmp_path: Path) -> None:
    path = tmp_path / "workflow.yaml"
    path.write_text("tasks:\n  - id: [unfinished\n", encoding="utf-8")

    with pytest.raises(WorkflowLoadError, match=r"line|column"):
        load_workflow(path)


def test_rejects_multiple_yaml_documents(tmp_path: Path) -> None:
    path = tmp_path / "workflow.yaml"
    path.write_text("tasks: []\n---\ntasks: []\n", encoding="utf-8")

    with pytest.raises(WorkflowLoadError):
        load_workflow(path)


@pytest.mark.parametrize(
    "content",
    [
        "tasks: !!int nope\n",
        "tasks: !!bool nope\n",
        "tasks: !!float .\n",
        "tasks: !!timestamp 2026-13-01\n",
        "tasks: !!timestamp nope\n",
        "tasks: !!timestamp ''\n",
        "? [invalid, key]\n: value\n",
        "tasks:\n  - id: " + "1" * 5000 + "\n",
    ],
)
def test_malformed_yaml_values_are_reported(tmp_path: Path, content: str) -> None:
    path = tmp_path / "workflow.yaml"
    path.write_text(content, encoding="utf-8")

    with pytest.raises(WorkflowLoadError):
        load_workflow(path)


def test_unsafe_yaml_tag_is_rejected_without_execution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[str] = []

    def record_command(command: str) -> int:
        calls.append(command)
        return 0

    monkeypatch.setattr(os, "system", record_command)
    path = tmp_path / "workflow.yaml"
    path.write_text(
        '!!python/object/apply:os.system ["unsafe-command"]\n', encoding="utf-8"
    )

    with pytest.raises(WorkflowLoadError):
        load_workflow(path)

    assert calls == []


def test_missing_file_is_reported(tmp_path: Path) -> None:
    path = tmp_path / "missing.yaml"

    with pytest.raises(WorkflowLoadError, match="missing.yaml"):
        load_workflow(path)


def test_unreadable_file_is_reported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def deny_read(self: Path, *args: object, **kwargs: object) -> str:
        raise PermissionError("permission denied")

    monkeypatch.setattr(Path, "read_text", deny_read)

    with pytest.raises(WorkflowLoadError, match="[Pp]ermission"):
        load_workflow(tmp_path / "workflow.yaml")


def test_non_utf8_input_is_reported(tmp_path: Path) -> None:
    path = tmp_path / "workflow.yaml"
    path.write_bytes(b"tasks:\n  - id: \xff\n")

    with pytest.raises(WorkflowLoadError, match="UTF-8|utf-8|encoding|decode"):
        load_workflow(path)


def test_excessive_yaml_nesting_is_reported(tmp_path: Path) -> None:
    path = tmp_path / "workflow.yaml"
    path.write_text("[" * 1500 + "]" * 1500, encoding="utf-8")

    with pytest.raises(WorkflowLoadError):
        load_workflow(path)


def test_recursive_yaml_alias_is_reported(tmp_path: Path) -> None:
    path = tmp_path / "workflow.yaml"
    path.write_text("tasks: &tasks\n  - *tasks\n", encoding="utf-8")

    with pytest.raises(WorkflowLoadError):
        load_workflow(path)
