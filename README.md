# CodeProof AI

Local-first Python CLI and reusable GitHub Action for verifying Python repositories. It runs deterministic checks, normalizes evidence, calculates a transparent confidence score, and exports JSON, Markdown, and HTML reports. It does not claim that code is correct.

## Features
- Ruff, mypy, pytest, Bandit, Semgrep and import-smoke adapters
- Weighted policy and required-tool gates
- AST test-gap inventory and reviewable smoke-test generation
- CI-friendly exit codes
- GitHub composite Action
- Local-first scanning
- Modern local GUI dashboard (`codeproof gui`) for scans, findings, policy, and history

## Install
```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
pip install -e ".[checkers]"
codeproof scan .
```

<!-- coderabbit-ai-generated:v1 -->

<!-- coderabbit-ai-generated-section:v1:3b67dbb46462cc622268fbccfec224b9fadec6e62adcd31c971ddfbdf0fff3c1 -->

## Commands

```bash
codeproof tools                         # supported checks and execution behavior
codeproof doctor                        # availability and install guidance
codeproof init                          # write a default policy
codeproof inventory .                   # public symbols, not coverage
codeproof generate-tests . --output tests/generated
codeproof scan . --format all --fail-under 70 --jobs 3
codeproof scan . --config path/to/policy.yml --checks ruff,pytest,syntax
```

Reports are stored under `.codeproof/reports/`. Open `codeproof-report.html` for offline search, status filters, and expandable evidence. JSON and Markdown remain available. Paths are positional; the earlier `--path` option is also supported. Exit codes: **0** policy passed, **1** policy failed, **2** invalid usage or configuration.

### Policy and additional tools

Partial policies overlay the six default checks; explicitly disable any you do not want. A selected or configured check cannot bypass a required tool gate. Remove a tool from `required_tools` only when intentionally changing the policy. For a quick execution-free syntax-only scan, use:

```yaml
# .codeproof.yml
required_tools: []
source_paths: [src]
checks:
  syntax: {enabled: true, weight: 10}
```

```bash
codeproof scan . --checks syntax
```

To add dependency auditing, install `pip install 'codeproof-ai[audit]'`, provide a root `requirements.txt`, and add `pip-audit: {enabled: true, weight: 15}` under `checks`. This opt-in tool queries vulnerability services and may invoke package tooling while resolving dependencies. Unsupported manifests are reported unavailable; the developer environment is never audited as a fallback.

`jobs: 1` (default) runs serially; `--jobs 2` through `--jobs 8` allow concurrency. Tests and imports can share resources, so choose concurrency to suit the repository. Invalid thresholds, negative/nonfinite weights, unknown tools, and unknown policy keys are rejected.

Generated tests check symbol exposure and execute imports; review them before running. Existing files are preserved unless `--force` is passed. See the [audit and prioritized roadmap](docs/roadmap.md) for delivered changes, compatibility notes, and follow-up work.

<!-- /coderabbit-ai-generated:v1 -->

<!-- coderabbit-ai-generated:v1 -->

<!-- coderabbit-ai-generated-section:v1:92fa63fb64ba1e1531e19feb0d45a9570a922b4234965c93f86f078af595fe02 -->

## Developer workspace

```bash
codeproof serve .
# Open http://127.0.0.1:8765/
```

Run scans from a responsive browser workspace with four presets, durable history, searchable findings, report comparison, tool readiness and policy inspection. Export JSON, Markdown, HTML or SARIF. Required policy gates remain active. Browser scans require opt-in for code execution and network checks. History keeps the latest 50 runs locally.

```bash
codeproof scan . --format sarif
```

Read the [workspace guide and use cases](docs/developer-workspace.md) for setup, workflows, storage and deployment boundaries. This is a local single-user workspace.
codeproof scan . --format all --fail-under 70
codeproof gui . --host 127.0.0.1 --port 8787
```
Reports are stored under `.codeproof/reports/`. The GUI runs locally and uses the same core engine/policy as the CLI. See `ROADMAP.md` for planned enhancements.

## Confidence model

<!-- /coderabbit-ai-generated:v1 -->
The score is the weighted percentage of included checks that pass. Missing required tools fail policy. Missing optional tools are marked unavailable and excluded from the denominator. A passing report is evidence that configured checks passed, not proof of correctness.

## Security
pytest and import checks execute repository code. Scan untrusted repositories only in an isolated container or ephemeral runner. Semgrep `auto` can retrieve rules; use a local rules directory for offline operation.

## Development
```bash
pip install -e ".[dev]"
pytest
```

## License
MIT
