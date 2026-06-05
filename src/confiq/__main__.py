"""Command-line interface for confiq."""

import typer


app: typer.Typer = typer.Typer()


@app.command(name="confiq")
def main() -> None:
    """Confiq."""


if __name__ == "__main__":
    app()  # pragma: no cover
