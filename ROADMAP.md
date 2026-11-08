# CodeProof-AI Roadmap

## Vision
Make CodeProof-AI the most trusted, local-first evidence platform for Python repository health—transparent scoring, actionable diagnostics, and seamless workflows from CLI to CI to interactive GUI.

## Current State (v0.1.0)
- Deterministic checks: Ruff, mypy, pytest, Bandit, Semgrep, import-smoke
- Weighted policy engine with required-tool gates and configurable thresholds
- AST-based symbol inventory and reviewable smoke-test generation
- Reports: JSON, Markdown, HTML
- Typer CLI + reusable GitHub Action
- Local-first execution model

## Near-term (v0.2.x) — Usability & Visibility
- **Modern GUI dashboard (in progress)**: local web interface to run scans, view results, inspect findings, browse report history, and edit policy.
- **Scan history & trends**: persist run metadata/summaries; show score trends over time per project.
- **Richer finding details**: normalize adapter outputs (file/line/rule/severity) into structured findings across all tools.
- **Config UX**: validate `.codeproof.yml`, expose presets (strict/balanced/fast), and document all options.
- **Improved HTML reports**: interactive filtering, sortable tables, and deep links to evidence/raw output.
- **Doctor enhancements**: version checks, install hints, and environment diagnostics.

## Mid-term (v0.3.x–v0.4.x) — Depth & Integrations
- **Async/background scans in GUI** with live progress and cancellation.
- **Baseline & diff mode**: compare current scan against a baseline to highlight regressions/new findings (PR-focused).
- **Plugin/adapter system**: stable interface for custom checks (coverage, pip-audit, vulture, complexity, license checks).
- **Coverage integration**: parse `coverage.xml`/pytest-cov output as a first-class evidence source.
- **Multi-language groundwork**: abstract runner/report model to support additional ecosystems (starting with JS/TS) while keeping Python best-in-class.
- **SARIF export** and better GitHub Code Scanning/PR annotation workflows.
- **Caching & incremental checks**: speed up repeated local scans.

## Long-term (v1.0+) — Team & Trust
- **Policy packs & provenance**: signed/shareable policy profiles; clear evidence provenance in reports.
- **Workspace/monorepo support**: per-package policies, aggregated scoring, and targeted scans.
- **Optional hosted/CI insights**: opt-in aggregation for teams (never default; preserve local-first core).
- **AI-assisted, evidence-grounded explanations**: summarize findings and suggest fixes *with citations to check output* (no correctness claims).
- **Stability guarantees**: versioned report schema, backward-compatible config migrations, and documented extension API.

## Guiding Principles
- **Evidence over claims**: reports show what ran, what passed/failed, and what was excluded.
- **Local-first & transparent**: predictable execution, explicit limitations, user-controlled network use.
- **Composable**: CLI, GUI, and CI share the same core engine and config.
- **Safe by default**: clear warnings when scanning executes untrusted code; encourage isolated environments.
