"""Tool boundaries: normalize findings and contain process failures."""

import json
import os
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

from .files import python_files
from .models import CheckResult, Finding, Status


def parse_findings(name: str, output: str) -> list[Finding]:
    """Retain raw evidence if a tool emits text or an unfamiliar JSON schema."""
    import re

    if name == "mypy":
        findings = []
        for match in re.finditer(
            r"^(.+?):(\d+)(?::\d+)?:\s*(error|warning|note):\s*(.*?)(?:\s+\[([^\]]+)\])?$",
            output,
            re.MULTILINE,
        ):
            path, line, severity, message, code = match.groups()
            findings.append(
                Finding(
                    level={"error": "error", "warning": "warning", "note": "info"}[
                        severity
                    ],
                    message=message,
                    path=path,
                    line=int(line),
                    rule=code,
                )
            )
        return findings
    if name == "pytest":
        findings = []
        for line in output.splitlines():
            match = re.match(r"^FAILED\s+(.+?)(?:\s+-\s+(.*))?$", line.strip())
            if match:
                node, reason = match.groups()
                findings.append(
                    Finding(
                        level="error",
                        message=reason or "test failed",
                        path=node.split("::")[0],
                        rule="pytest",
                    )
                )
        return findings
    try:
        data = json.loads(output)
        if name == "ruff":
            return [
                Finding(
                    level="warning",
                    message=item["message"],
                    path=item.get("filename"),
                    line=item.get("location", {}).get("row"),
                    rule=item.get("code"),
                )
                for item in data
            ]
        if name == "bandit":
            return [
                Finding(
                    level=item.get("issue_severity", "warning").lower(),
                    message=item["issue_text"],
                    path=item.get("filename"),
                    line=item.get("line_number"),
                    rule=item.get("test_id"),
                )
                for item in data.get("results", [])
            ]
        if name == "semgrep":
            return [
                Finding(
                    level=item["extra"].get("severity", "warning").lower(),
                    message=item["extra"]["message"],
                    path=item.get("path"),
                    line=item.get("start", {}).get("line"),
                    rule=item.get("check_id"),
                )
                for item in data.get("results", [])
            ]
        if name == "pip-audit":
            return [
                Finding(
                    level="warning",
                    message=f"{dep['name']} {dep['version']}: {vuln.get('description', vuln['id'])}",
                    rule=vuln["id"],
                    path="requirements.txt",
                )
                for dep in data.get("dependencies", [])
                for vuln in dep.get("vulns", [])
            ]
    except (ValueError, KeyError, TypeError, AttributeError):
        pass
    return []


def run(
    name: str,
    root: Path,
    cfg: str | None,
    timeout: int,
    sources: list[str],
    tests: list[str],
) -> CheckResult:
    if name == "syntax":
        return syntax(root, sources)
    if name == "imports":
        return imports(root, sources, timeout)
    if name == "coverage":
        return coverage(root, sources, cfg)
    src = [x for x in sources if (root / x).exists()] or ["."]
    commands = {
        "ruff": ["ruff", "check", *src, "--output-format", "json"],
        "mypy": ["mypy", *src, "--no-error-summary"],
        "pytest": [
            "pytest",
            *([x for x in tests if (root / x).exists()] or ["."]),
            "-q",
        ],
        "bandit": ["bandit", "-r", *src, "-f", "json", "-q"],
        "semgrep": [
            "semgrep",
            "scan",
            "--config",
            cfg or "auto",
            "--json",
            "--error",
            *src,
        ],
        "pip-audit": [
            "pip-audit",
            "-r",
            "requirements.txt",
            "--format",
            "json",
            "--progress-spinner",
            "off",
        ],
    }
    cmd = commands.get(name)
    if not cmd:
        return CheckResult(name=name, status=Status.skipped, summary="unknown adapter")
    if name == "pip-audit" and not (root / "requirements.txt").is_file():
        return CheckResult(
            name=name,
            status=Status.unavailable,
            summary="Requires requirements.txt at the project root; no environment audit performed",
        )
    if not shutil.which(cmd[0]):
        return CheckResult(
            name=name,
            status=Status.unavailable,
            command=cmd,
            summary=f"{cmd[0]} is not installed; install codeproof-ai[{'audit' if name == 'pip-audit' else 'checkers'}]",
        )
    started = time.perf_counter()
    try:
        cp = subprocess.run(
            cmd,
            check=False,
            cwd=root,
            text=True,
            errors="replace",
            capture_output=True,
            timeout=timeout,
            env={**os.environ, "NO_COLOR": "1"},
        )
        findings = parse_findings(name, cp.stdout or "")
        evidence = {}
        if name == "pytest":
            import re as _re

            summary_match = _re.search(
                r"(\d+)\s+passed(?:.*?(\d+)\s+failed)?|(\d+)\s+failed",
                cp.stdout or "",
            )
            # simpler explicit counts
            passed_m = _re.search(r"(\d+)\s+passed", cp.stdout or "")
            failed_m = _re.search(r"(\d+)\s+failed", cp.stdout or "")
            evidence = {
                "tests_passed": int(passed_m.group(1)) if passed_m else 0,
                "tests_failed": int(failed_m.group(1)) if failed_m else len(findings),
            }
        if name == "mypy":
            evidence = {"findings": len(findings)}
        return CheckResult(
            name=name,
            status=Status.passed if cp.returncode == 0 else Status.failed,
            command=cmd,
            duration_seconds=round(time.perf_counter() - started, 3),
            exit_code=cp.returncode,
            summary=f"{len(findings)} findings"
            if findings
            else (
                "passed"
                if cp.returncode == 0
                else "Check failed; expand output for details"
            ),
            findings=findings,
            evidence=evidence,
            raw_output=((cp.stdout or "") + ("\n" + cp.stderr if cp.stderr else ""))[
                -50000:
            ],
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        return CheckResult(
            name=name,
            status=Status.error,
            command=cmd,
            duration_seconds=round(time.perf_counter() - started, 3),
            summary=f"timed out after {timeout}s"
            if isinstance(exc, subprocess.TimeoutExpired)
            else str(exc),
        )


def syntax(root: Path, sources: list[str]) -> CheckResult:
    started = time.perf_counter()
    findings: list[Finding] = []
    count = 0
    for path, _ in python_files(root, sources):
        count += 1
        try:
            compile(path.read_bytes(), str(path), "exec")
        except (SyntaxError, UnicodeError, OSError) as exc:
            findings.append(
                Finding(
                    level="error",
                    message=str(exc),
                    path=str(path.relative_to(root)),
                    line=getattr(exc, "lineno", None),
                    rule="syntax",
                )
            )
    return CheckResult(
        name="syntax",
        status=Status.failed
        if findings
        else (Status.passed if count else Status.skipped),
        duration_seconds=round(time.perf_counter() - started, 3),
        summary=f"{count} files compiled; {len(findings)} errors",
        findings=findings,
        evidence={"files_checked": count},
    )


def imports(root: Path, sources: list[str], timeout: int) -> CheckResult:
    started = time.perf_counter()
    findings: list[Finding] = []
    count = 0
    for path, base in python_files(root, sources):
        if path.name == "__init__.py":
            continue
        remaining = timeout - (time.perf_counter() - started)
        if remaining <= 0:
            return CheckResult(
                name="imports",
                status=Status.error,
                summary=f"timed out after {timeout}s",
                findings=findings,
            )
        module = ".".join(path.relative_to(base).with_suffix("").parts)
        count += 1
        try:
            cp = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    f"import sys;sys.path.insert(0,{str(base)!r});__import__({module!r})",
                ],
                check=False,
                cwd=root,
                text=True,
                errors="replace",
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=remaining,
            )
        except (subprocess.TimeoutExpired, OSError) as exc:
            return CheckResult(
                name="imports",
                status=Status.error,
                duration_seconds=round(time.perf_counter() - started, 3),
                findings=findings,
                summary=f"timed out after {timeout}s"
                if isinstance(exc, subprocess.TimeoutExpired)
                else str(exc),
            )
        if cp.returncode:
            findings.append(
                Finding(
                    level="error",
                    message=(cp.stdout or "failed")[-800:],
                    path=str(path.relative_to(root)),
                    rule="import",
                )
            )
    return CheckResult(
        name="imports",
        status=Status.failed
        if findings
        else (Status.passed if count else Status.skipped),
        duration_seconds=round(time.perf_counter() - started, 3),
        summary=f"{count} modules checked; {len(findings)} failed",
        findings=findings,
        evidence={"modules_checked": count},
    )


def coverage(root: Path, sources: list[str], cfg: str | None) -> CheckResult:
    started = time.perf_counter()
    candidates = [root / "coverage.xml"]
    for src in sources:
        candidates.append(root / src / "coverage.xml")
    path = next((p for p in candidates if p.is_file()), None)
    if path is None:
        return CheckResult(
            name="coverage",
            status=Status.unavailable,
            duration_seconds=round(time.perf_counter() - started, 3),
            summary="Requires coverage.xml at the project root",
        )
    try:
        tree = ET.parse(path)
    except (ET.ParseError, OSError) as exc:
        return CheckResult(
            name="coverage",
            status=Status.error,
            duration_seconds=round(time.perf_counter() - started, 3),
            summary=f"Could not parse coverage.xml: {exc}",
        )
    root_el = tree.getroot()
    try:
        line_rate = float(root_el.get("line-rate", "0"))
        branch_rate = float(root_el.get("branch-rate", "0"))
    except ValueError:
        line_rate = 0.0
        branch_rate = 0.0
    lines_valid = int(root_el.get("lines-valid", "0") or 0)
    lines_covered = int(root_el.get("lines-covered", "0") or 0)
    threshold = 70.0
    if cfg:
        try:
            threshold = float(cfg)
        except ValueError:
            pass
    findings = []
    for cls in root_el.iter("class"):
        filename = cls.get("filename")
        try:
            cls_line_rate = float(cls.get("line-rate", "1"))
        except ValueError:
            cls_line_rate = 1.0
        if cls_line_rate * 100 < threshold and filename:
            findings.append(
                Finding(
                    level="warning",
                    message=f"Line coverage {cls_line_rate * 100:.1f}% is below {threshold:g}%",
                    path=filename,
                    rule="coverage",
                )
            )
    findings = findings[:20]
    passed = line_rate * 100 >= threshold
    return CheckResult(
        name="coverage",
        status=Status.passed if passed else Status.failed,
        duration_seconds=round(time.perf_counter() - started, 3),
        summary=f"Line coverage {line_rate * 100:.1f}%, branch coverage {branch_rate * 100:.1f}%",
        findings=findings,
        evidence={
            "line_rate": line_rate,
            "branch_rate": branch_rate,
            "lines_covered": lines_covered,
            "lines_valid": lines_valid,
            "threshold": threshold,
            "files_below_threshold": len(findings),
        },
    )
