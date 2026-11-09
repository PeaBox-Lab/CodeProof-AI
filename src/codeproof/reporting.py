from html import escape
from pathlib import Path
from typing import Any

from .models import ScanReport, Status


def cell(value):
    return (
        str(value)
        .replace("\\", "\\\\")
        .replace("|", "\\|")
        .replace("\n", "<br>")
        .replace("\r", "")
    )


def markdown(report: ScanReport):
    rows = [
        "| Check | Status | Required | Weight | Duration | Summary |",
        "|---|---|---|---:|---:|---|",
    ]
    for result in report.results:
        rows.append(
            f"| {cell(result.name)} | {result.status.value} | {'yes' if result.required else 'no'} | "
            f"{result.weight:g} | {result.duration_seconds:.2f}s | {cell(result.summary)} |"
        )
    text = (
        f"# CodeProof: {cell(report.project)}\n\n**Score:** {report.score}/100 ({report.grade})  \n"
        f"**Policy:** {'PASS' if report.policy_passed else 'FAIL'} · threshold {report.fail_under:g}\n\n"
        + "\n".join(rows)
    )
    for result in report.results:
        if result.findings:
            text += f"\n\n## {cell(result.name)} findings\n"
            for finding in result.findings:
                location = f"{finding.path or ''}{':' + str(finding.line) if finding.line else ''}"
                text += f"\n- {cell(finding.rule or finding.level)} · {cell(location)}: {cell(finding.message)}"
    provenance = ""
    if report.source_revision or report.tool_versions:
        provenance = "\n\n## Provenance\n"
        if report.source_revision:
            provenance += f"- Source revision: `{report.source_revision}`\n"
        for name, version in report.tool_versions.items():
            provenance += f"- {name}: {cell(version)}\n"
    return (
        text
        + provenance
        + "\n\n## Limitations\n"
        + "\n".join("- " + cell(item) for item in report.limitations)
        + "\n"
    )


def html(report: ScanReport):
    cards = []
    for result in report.results:
        findings = "".join(
            f'<li><div class="finding-meta"><span>{escape(item.rule or item.level)}</span>'
            f"<code>{escape(item.path or 'No file location')}{':' + str(item.line) if item.line else ''}</code></div>"
            f"<p>{escape(item.message)}</p></li>"
            for item in result.findings
        )
        detail = (
            f'<h4>Findings ({len(result.findings)})</h4><ul class="findings">{findings}</ul>'
            if findings
            else ""
        )
        if result.command:
            detail += (
                "<h4>Command arguments</h4><pre>"
                + escape(str(result.command))
                + "</pre>"
            )
        if result.raw_output:
            detail += "<h4>Tool output</h4><pre>" + escape(result.raw_output) + "</pre>"
        if result.evidence:
            detail += "<h4>Evidence</h4><pre>" + escape(str(result.evidence)) + "</pre>"
        cards.append(
            f'<article class="check" data-status="{result.status.value}">'
            f'<details><summary><span class="status-dot {result.status.value}"></span>'
            f'<span class="check-title">{escape(result.name)}<small>{escape(result.summary)}</small></span>'
            f'<span class="required">{"Required" if result.required else "Optional"}</span>'
            f'<span class="duration">{result.duration_seconds:.2f}s</span>'
            f'<span class="badge {result.status.value}">{result.status.value}</span><span class="chevron">⌄</span></summary>'
            f'<div class="check-body"><p class="muted">Policy weight: {result.weight:g}</p>{detail or "<p>No additional evidence.</p>"}</div>'
            "</details></article>"
        )
    template = (
        Path(__file__).with_name("report_template.html").read_text(encoding="utf-8")
    )
    passed = sum(result.status == Status.passed for result in report.results)
    attention = sum(
        result.status in (Status.failed, Status.error)
        or (result.required and result.status != Status.passed)
        for result in report.results
    )
    replacements = {
        "project": escape(report.project),
        "target": escape(report.target),
        "generated": escape(report.generated_at),
        "score": f"{report.score:g}",
        "grade": escape(report.grade),
        "policy": "Passed" if report.policy_passed else "Failed",
        "policy_class": "passed" if report.policy_passed else "failed",
        "threshold": f"{report.fail_under:g}",
        "passed": str(passed),
        "total": str(len(report.results)),
        "attention": str(attention),
        "findings": str(sum(len(result.findings) for result in report.results)),
        "cards": "".join(cards),
        "limitations": "".join(
            f"<li>{escape(item)}</li>" for item in report.limitations
        ),
        "version": escape(report.codeproof_version),
    }
    # One replacement pass prevents report text from being interpreted as template tokens.
    import re

    return re.sub(r"@@(\w+)@@", lambda match: replacements[match[1]], template)


def write(report: ScanReport, out: Path, fmt: str):
    if fmt not in {"all", "json", "markdown", "html", "sarif"}:
        raise ValueError(f"Unsupported report format: {fmt}")
    out.mkdir(parents=True, exist_ok=True)
    made = []
    renderers = {
        "json": ("json", lambda: report.model_dump_json(indent=2)),
        "markdown": ("md", lambda: markdown(report)),
        "html": ("html", lambda: html(report)),
    }
    for name, (suffix, render) in renderers.items():
        if fmt in ("all", name):
            path = out / f"codeproof-report.{suffix}"
            path.write_text(render(), encoding="utf-8")
            made.append(path)
    if fmt == "sarif":
        import json

        path = out / "codeproof-report.sarif"
        path.write_text(json.dumps(sarif(report), indent=2), encoding="utf-8")
        made.append(path)
    raw = out.parent / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    for result in report.results:
        if result.raw_output:
            (raw / f"{result.name}.txt").write_text(result.raw_output, encoding="utf-8")
    return made


def sarif(report: ScanReport):
    """Export normalized findings for SARIF 2.1.0 consumers."""
    rules: dict[str, Any] = {}
    results = []
    root = Path(report.target).resolve()
    for check in report.results:
        for finding in check.findings:
            rule = f"{check.name}/{finding.rule or 'finding'}"
            rules.setdefault(
                rule,
                {"id": rule, "shortDescription": {"text": finding.rule or check.name}},
            )
            level = (
                "error"
                if finding.level.lower() in {"error", "high", "critical"}
                else "note"
                if finding.level.lower() in {"info", "low"}
                else "warning"
            )
            item: dict[str, Any] = {
                "ruleId": rule,
                "level": level,
                "message": {"text": finding.message},
            }
            if finding.path:
                original = Path(finding.path)
                path: Path | None = None
                if original.is_absolute():
                    try:
                        path = original.resolve().relative_to(root)
                    except ValueError:
                        path = None
                else:
                    if ".." not in original.parts:
                        candidate = (root / original).resolve()
                        try:
                            path = candidate.relative_to(root)
                        except ValueError:
                            path = None
                if path is not None and ".." not in path.parts:
                    from urllib.parse import quote

                    location: dict[str, Any] = {
                        "artifactLocation": {
                            "uri": quote(path.as_posix()),
                            "uriBaseId": "%SRCROOT%",
                        }
                    }
                    if finding.line and finding.line > 0:
                        location["region"] = {"startLine": finding.line}
                    item["locations"] = [{"physicalLocation": location}]
            results.append(item)
    return {
        "version": "2.1.0",
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "CodeProof AI",
                        "version": report.codeproof_version,
                        "rules": list(rules.values()),
                    }
                },
                "results": results,
            }
        ],
    }
