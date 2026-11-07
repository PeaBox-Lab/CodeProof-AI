import subprocess

from codeproof.adapters import imports, parse_findings, run, syntax


def test_syntax_does_not_execute_or_write_bytecode(tmp_path):
    (tmp_path / "valid.py").write_text('raise RuntimeError("must not execute")\n')
    result = syntax(tmp_path, ["."])
    assert result.status == "passed"
    assert not (tmp_path / "__pycache__").exists()
    (tmp_path / "bad.py").write_text("def broken(:\n")
    result = syntax(tmp_path, ["."])
    assert result.status == "failed"
    assert result.findings[0].path == "bad.py"
    assert result.findings[0].line == 1


def test_traversal_prunes_environments_and_duplicates(tmp_path):
    (tmp_path / ".venv").mkdir()
    (tmp_path / ".venv" / "bad.py").write_text("def broken(:")
    (tmp_path / "ok.py").write_text("x = 1")
    result = syntax(tmp_path, [".", "."])
    assert result.status == "passed"
    assert result.evidence["files_checked"] == 1
    assert syntax(tmp_path, ["absent"]).status == "skipped"


def test_import_timeout_is_a_result(monkeypatch, tmp_path):
    (tmp_path / "slow.py").write_text("")

    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(args[0], 1)

    monkeypatch.setattr(subprocess, "run", timeout)
    assert imports(tmp_path, ["."], 1).status == "error"


def test_subprocess_timeout_and_launch_failure(monkeypatch, tmp_path):
    monkeypatch.setattr("shutil.which", lambda name: "/bin/tool")
    for error in (subprocess.TimeoutExpired("ruff", 1), OSError("cannot start")):

        def fail(*args, error=error, **kwargs):
            raise error

        monkeypatch.setattr(subprocess, "run", fail)
        assert run("ruff", tmp_path, None, 1, ["."], ["tests"]).status == "error"


def test_findings_parsed_before_raw_truncation_and_stderr(monkeypatch, tmp_path):
    monkeypatch.setattr("shutil.which", lambda name: "/bin/ruff")
    payload = (
        '[{"message":"unused","filename":"app.py","location":{"row":3},"code":"F401"}]'
    )
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *a, **k: subprocess.CompletedProcess(a[0], 1, payload, "diagnostic"),
    )
    result = run("ruff", tmp_path, None, 1, ["."], ["tests"])
    assert result.findings[0].rule == "F401"
    assert result.findings[0].line == 3
    assert "diagnostic" in result.raw_output


def test_supported_json_schemas():
    assert (
        parse_findings(
            "bandit",
            '{"results":[{"issue_text":"unsafe","test_id":"B1","line_number":4}]}',
        )[0].rule
        == "B1"
    )
    assert (
        parse_findings(
            "semgrep", '{"results":[{"extra":{"message":"unsafe"},"check_id":"S1"}]}'
        )[0].rule
        == "S1"
    )
    assert (
        parse_findings(
            "pip-audit",
            '{"dependencies":[{"name":"demo","version":"1","vulns":[{"id":"CVE-TEST"}]}]}',
        )[0].rule
        == "CVE-TEST"
    )
    assert parse_findings("ruff", "invalid output") == []


def test_dependency_audit_does_not_fall_back_to_environment(tmp_path):
    result = run("pip-audit", tmp_path, None, 1, ["."], ["tests"])
    assert result.status == "unavailable"
    assert "requirements.txt" in result.summary
