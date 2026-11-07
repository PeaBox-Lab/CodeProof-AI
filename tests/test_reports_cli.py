import json

from typer.testing import CliRunner

from codeproof.cli import app
from codeproof.config import Config
from codeproof.core import scan
from codeproof.models import CheckResult, Finding, Status
from codeproof.reporting import html, markdown, write

runner = CliRunner()


def test_report_escapes_untrusted_evidence(tmp_path):
    report = scan(tmp_path, Config(required_tools=[]))
    report.project = "<script>alert(1)</script>@@cards@@"
    report.results = [
        CheckResult(
            name="ruff",
            status=Status.failed,
            summary="a | b\nnext",
            raw_output="<img src=x onerror=alert(1)>",
            findings=[Finding(message="<script>bad</script>", path="a.py", line=2)],
        )
    ]
    page = html(report)
    assert "<script>alert(1)" not in page
    assert "&lt;script&gt;alert(1)" in page
    assert "@@cards@@" in page
    assert "<img src=x" not in page
    assert "a \\| b<br>next" in markdown(report)
    assert len(write(report, tmp_path / "reports", "all")) == 3
    assert (
        json.loads((tmp_path / "reports/codeproof-report.json").read_text())[
            "schema_version"
        ]
        == "1.0"
    )


def test_cli_invalid_policy_and_directory_have_no_traceback(tmp_path):
    (tmp_path / ".codeproof.yml").write_text("jobs: 0")
    result = runner.invoke(app, ["scan", str(tmp_path)])
    assert result.exit_code == 2 and "Invalid policy" in result.output
    assert runner.invoke(app, ["scan", str(tmp_path / "missing")]).exit_code == 2
    assert runner.invoke(app, ["scan", str(tmp_path), "--jobs", "9"]).exit_code == 2


def test_cli_scan_and_required_gate_with_check_selection(tmp_path):
    (tmp_path / "app.py").write_text("x = 1")
    (tmp_path / ".codeproof.yml").write_text('required_tools: []\nsource_paths: ["."]')
    result = runner.invoke(
        app, ["scan", str(tmp_path), "--checks", "syntax", "--jobs", "2"]
    )
    assert result.exit_code == 0, result.output
    report = json.loads(
        (tmp_path / ".codeproof/reports/codeproof-report.json").read_text()
    )
    assert report["score"] == 100
    (tmp_path / ".codeproof.yml").unlink()
    result = runner.invoke(
        app, ["scan", str(tmp_path), "--checks", "syntax", "--fail-under", "0"]
    )
    assert result.exit_code == 1
    result = runner.invoke(app, ["scan", str(tmp_path), "--checks", "typo"])
    assert result.exit_code == 2


def test_init_force_can_replace_invalid_policy(tmp_path):
    (tmp_path / ".codeproof.yml").write_text("jobs: bad")
    assert runner.invoke(app, ["init", str(tmp_path)]).exit_code == 2
    assert runner.invoke(app, ["init", str(tmp_path), "--force"]).exit_code == 0
    assert runner.invoke(app, ["tools"]).exit_code == 0
    assert "syntax" in runner.invoke(app, ["doctor"]).output


def test_legacy_path_option(tmp_path):
    assert runner.invoke(app, ["init", "--path", str(tmp_path)]).exit_code == 0
    assert runner.invoke(app, ["inventory", "--path", str(tmp_path)]).exit_code == 0
    assert (
        runner.invoke(
            app, ["scan", "--path", str(tmp_path), "--checks", "syntax"]
        ).exit_code
        == 1
    )
