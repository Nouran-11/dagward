from typer.testing import CliRunner

from dagward.cli import app

runner = CliRunner()


def test_help() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "Analyze DAG workflows without executing tasks." in result.output


def test_missing_command_shows_help() -> None:
    result = runner.invoke(app, [])

    assert result.exit_code == 2
    assert "Usage:" in result.output


def test_unknown_command_is_usage_error() -> None:
    result = runner.invoke(app, ["unknown"])

    assert result.exit_code == 2
    assert "No such command" in result.output
