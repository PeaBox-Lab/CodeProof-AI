# CodeProof AI

Local-first Python CLI and reusable GitHub Action for verifying Python repositories. It runs deterministic checks, normalizes evidence, calculates a transparent confidence score, and exports JSON, Markdown, and HTML reports. It does not claim that code is correct.

## Features
- Ruff, mypy, pytest, Bandit, Semgrep and import-smoke adapters
- Weighted policy and required-tool gates
- AST test-gap inventory and reviewable smoke-test generation
- CI-friendly exit codes
- GitHub composite Action
- Local-first scanning

## Install
```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
pip install -e ".[checkers]"
codeproof scan .
```

## Commands
```bash
codeproof doctor
codeproof init
codeproof inventory .
codeproof generate-tests . --output tests/generated
codeproof scan . --format all --fail-under 70
```
Reports are stored under `.codeproof/reports/`.

## Confidence model
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
