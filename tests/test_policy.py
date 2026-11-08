from pathlib import Path
from threading import Barrier

import pytest
from pydantic import ValidationError

from codeproof.config import DEFAULT, CheckConfig, Config, load
from codeproof.core import scan
from codeproof.models import CheckResult, Status


def test_partial_policy_keeps_checks_and_weights(tmp_path):
    (tmp_path / ".codeproof.yml").write_text("checks:\n  ruff:\n    weight: 22\n")
    config = load(tmp_path)
    assert config.checks["ruff"].weight == 22
    assert config.checks["pytest"].weight == 30
    assert config.checks["semgrep"].config == "auto"
    config.checks["pytest"].enabled = False
    assert DEFAULT.checks["pytest"].enabled


@pytest.mark.parametrize(
    "text",
    [
        "[]",
        "checks: []",
        "checks:\n  ruff: false",
        "jobs: 0",
        "fail_under: 101",
        "fail_under: .nan",
        "required_tools: [typo]",
        "checks:\n  ruff:\n    weight: -1",
        "version: 2",
        "typo: true",
    ],
)
def test_invalid_policy(tmp_path, text):
    (tmp_path / ".codeproof.yml").write_text(text)
    with pytest.raises((ValueError, TypeError, ValidationError)):
        load(tmp_path)


def test_explicit_missing_policy(tmp_path):
    with pytest.raises(ValueError, match="not found"):
        load(tmp_path, Path("missing.yml"))


def result(name, root, cfg, timeout, sources, tests):
    return CheckResult(name=name, status=Status.passed)


def test_disabled_and_absent_required_tools_fail(monkeypatch, tmp_path):
    monkeypatch.setattr("codeproof.core.run", result)
    cfg = Config(
        checks={"syntax": CheckConfig(weight=100), "ruff": CheckConfig(enabled=False)}
    )
    report = scan(tmp_path, cfg)
    assert report.score == 100
    assert not report.policy_passed
    assert {r.name for r in report.results if r.required} == {"ruff", "pytest"}


def test_empty_evidence_never_passes_at_zero(tmp_path):
    assert not scan(tmp_path, Config(required_tools=[], fail_under=0)).policy_passed


def test_optional_unavailable_excluded_but_required_blocks(monkeypatch, tmp_path):
    def run(name, *args):
        return CheckResult(
            name=name, status=Status.passed if name == "syntax" else Status.unavailable
        )

    monkeypatch.setattr("codeproof.core.run", run)
    cfg = Config(
        required_tools=[], checks={"syntax": CheckConfig(), "ruff": CheckConfig()}
    )
    report = scan(tmp_path, cfg)
    assert report.score == 100 and report.policy_passed
    cfg.required_tools = ["ruff"]
    report = scan(tmp_path, cfg)
    assert report.score == 50 and not report.policy_passed


def test_parallel_checks_preserve_order(monkeypatch, tmp_path):
    barrier = Barrier(2, timeout=5)

    def run(name, *args):
        barrier.wait()
        return CheckResult(name=name, status=Status.passed)

    monkeypatch.setattr("codeproof.core.run", run)
    cfg = Config(
        required_tools=[], checks={"syntax": CheckConfig(), "ruff": CheckConfig()}
    )
    report = scan(tmp_path, cfg, jobs=2)
    assert [r.name for r in report.results] == ["syntax", "ruff"]
    assert report.policy_passed
