import shutil
from enum import Enum
from pathlib import Path
from typing import Annotated

import typer
import yaml
from rich.console import Console
from rich.table import Table

from .config import DEFAULT, TOOL_INFO, CheckConfig, load
from .core import scan as execute
from .discovery import generate, symbols
from .reporting import write

app = typer.Typer(
    no_args_is_help=True,
    help="Evidence-backed Python repository checks. Start with doctor or init.",
)
console = Console()


class Format(str, Enum):
    all = "all"
    json = "json"
    markdown = "markdown"
    html = "html"


def policy(root: Path, config: Path | None = None):
    if not root.is_dir():
        raise typer.BadParameter(f"Repository directory does not exist: {root}")
    try:
        return load(root, config)
    except (ValueError, TypeError, OSError, yaml.YAMLError) as exc:
        raise typer.BadParameter(f"Invalid policy: {exc}") from exc


@app.command()
def tools():
    """List supported tools, execution behavior, and installation extras."""
    table = Table("Tool", "Purpose", "Behavior", "Install extra")
    for name, (purpose, description, extra) in TOOL_INFO.items():
        table.add_row(name, purpose, description, extra or "built in")
    console.print(table)


@app.command()
def doctor():
    """Check tool availability and show how to install missing tools."""
    table = Table("Tool", "Status", "Next step")
    for name, (_, _, extra) in TOOL_INFO.items():
        available = extra is None or bool(shutil.which(name))
        table.add_row(
            name,
            "available" if available else "missing",
            "Ready" if available else f"pip install 'codeproof-ai[{extra}]'",
        )
    console.print(table)
    console.print(
        "Dependency auditing needs requirements.txt. Semgrep auto and pip-audit use the network."
    )


@app.command()
def init(
    path: Annotated[Path, typer.Argument()] = Path("."),
    force: bool = False,
    path_option: Annotated[Path | None, typer.Option("--path", hidden=True)] = None,
):
    """Create a commented policy without overwriting an existing one."""
    root = (path_option or path).resolve()
    if not root.is_dir():
        raise typer.BadParameter(f"Repository directory does not exist: {root}")
    dest = root / ".codeproof.yml"
    if dest.exists() and not force:
        raise typer.BadParameter("policy exists; use --force")
    dest.write_text(
        "# Weights are relative. Required checks must pass even with weight 0.\n"
        "# Add syntax or pip-audit under checks to opt in; jobs: 1 is serial.\n"
        + yaml.safe_dump(DEFAULT.model_dump(mode="json"), sort_keys=False),
        encoding="utf-8",
    )
    console.print(f"Created {dest}")


@app.command()
def inventory(
    path: Annotated[Path, typer.Argument()] = Path("."),
    path_option: Annotated[Path | None, typer.Option("--path", hidden=True)] = None,
):
    """List public top-level symbols; this is an inventory, not coverage analysis."""
    root = (path_option or path).resolve()
    cfg = policy(root)
    table = Table("Symbol", "File", "Line")
    data = symbols(root, cfg.source_paths)
    for name, file, line in data:
        table.add_row(name, str(file), str(line))
    console.print(table)
    console.print(f"{len(data)} public symbols")


@app.command("generate-tests")
def generate_tests(
    path: Annotated[Path, typer.Argument()] = Path("."),
    path_option: Annotated[Path | None, typer.Option("--path", hidden=True)] = None,
    output: Path = Path("tests/generated"),
    force: bool = False,
):
    """Generate reviewable exposure checks. These are not behavioral tests."""
    root = (path_option or path).resolve()
    cfg = policy(root)
    made = generate(root, cfg.source_paths, root / output, force)
    console.print(
        f"Created {len(made)} files; review before running (imports execute code)."
    )


@app.command()
def scan(
    path: Annotated[Path, typer.Argument()] = Path("."),
    path_option: Annotated[Path | None, typer.Option("--path", hidden=True)] = None,
    format: Format = Format.all,
    fail_under: float | None = typer.Option(None, min=0, max=100),
    output: Path = Path(".codeproof/reports"),
    config: Path | None = None,
    jobs: int | None = typer.Option(None, min=1, max=8),
    checks: str | None = typer.Option(
        None, help="Comma-separated tools to run. Required tools remain policy gates."
    ),
):
    """Run checks and write reports. Exit 0: policy passes; 1: fails; 2: invalid input."""
    root = (path_option or path).resolve()
    cfg = policy(root, config)
    if checks is not None:
        selected = {name.strip() for name in checks.split(",") if name.strip()}
        if not selected or selected - TOOL_INFO.keys():
            raise typer.BadParameter(
                "--checks must name supported tools; see codeproof tools"
            )
        for name in sorted(selected):
            cfg.checks.setdefault(name, CheckConfig(weight=10))
        for name, check in cfg.checks.items():
            check.enabled = name in selected
    with console.status("Running repository checks…"):
        report = execute(root, cfg, fail_under, jobs)
    table = Table("Check", "Status", "Required", "Time", "Summary")
    for result in report.results:
        table.add_row(
            result.name,
            result.status.value,
            "yes" if result.required else "no",
            f"{result.duration_seconds:.2f}s",
            result.summary,
        )
    console.print(table)
    console.print(
        f"Score {report.score}/100 ({report.grade}); policy {'PASS' if report.policy_passed else 'FAIL'} (threshold {report.fail_under:g})"
    )
    for dest in write(report, root / output, format.value):
        console.print(f"Report: {dest}")
    raise typer.Exit(0 if report.policy_passed else 1)


if __name__ == "__main__":
    app()
