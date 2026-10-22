import typer

app = typer.Typer(no_args_is_help=True, add_completion=False)


@app.callback()
def main() -> None:
    """Analyze DAG workflows without executing tasks."""
