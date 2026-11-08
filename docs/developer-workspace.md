<!-- coderabbit-ai-generated:v1 -->

# CodeProof Developer Workspace

## Start here

```bash
pip install -e ".[checkers]"
codeproof serve .
```

Open **http://127.0.0.1:8765/**. The same repository-scoped engine powers the browser, CLI and GitHub Action. The workspace uses Python's standard library HTTP server and SQLite; there is no frontend build step or new service dependency. All CSS, scripts and fonts are local. Dates follow the browser locale and stored timestamps use UTC.

Use `codeproof doctor` to check availability. Add `pip install 'codeproof-ai[audit]'` for dependency auditing and a root requirements.txt. The CLI and existing static reports remain supported. `--format all` still generates the original JSON, Markdown and HTML files; `--format sarif` explicitly generates codeproof-report.sarif.

## Developer workflows and product use cases

| Audience / problem | Workflow | Evidence delivered |
|---|---|---|
| Python developers catching errors before commit | Fast feedback preset: syntax, Ruff and mypy plus required gates | Tool statuses, structured findings, file locations and raw output |
| Reviewers evaluating a pull request | Code quality preset: syntax, lint, types, pytest and Bandit plus required gates | Weighted score, required-check result, downloadable report and SARIF |
| Maintainers tracking regressions | Scan history and baseline/current comparison | Score difference and new/resolved normalized findings, with a warning if check sets/weights/thresholds differ |
| Security champions triaging Python code | Security preset: syntax, Bandit, Semgrep and pip-audit plus required gates | Security-pattern and dependency findings; unavailable tools remain visible |
| Release engineers applying shared standards | Repository policy preset and Quality policy page | The existing policy, explicit threshold, required gates and repeatable scan evidence |
| New contributors learning a repository's quality workflow | Tool readiness, installation guidance, use-case guides and downloadable YAML | Clear setup steps and one scan dialog instead of remembering CLI options |
| Teams moving evidence between CI tools | Export JSON, Markdown, HTML or SARIF 2.1.0 | Portable snapshots; SARIF exports normalized findings only, not raw-only diagnostics |

The product is a Python verification workspace. It does not write application code, prove correctness, measure test coverage, offer an AI chat model, or certify compliance. Generated tests in the CLI check symbol exposure and should be reviewed before running.

## Interface and behavior

- Repository overview: actual score, check counts, findings and policy outcome; no simulated statistics.
- Quality trend: latest 12 completed runs with scores and timestamps. Different presets can measure different check sets; compare their configurations before treating a trend as improvement.
- Findings explorer: search message/rule/file, filter by tool/severity, and page through 25 rows at a time. Check evidence includes commands, structured findings, diagnostics and execution time.
- Scan dialog: four presets, threshold 0–100, workers 1–8, and explicit code-execution/network opt-ins. Existing required checks are included and disabled required checks still fail policy. Mypy plugins and package resolution can execute code, so their profiles require execution consent.
- Run history: statuses include running, complete, error and interrupted; a failing policy is a completed scan with a failed policy outcome. Reports survive application restarts.
- Comparison: tool, rule, path, line and message identify a normalized finding. Location shifts may count as new/resolved. Up to 100 changes per group are rendered. Raw-only errors are outside finding comparison. Complete environment/rule snapshots are not yet recorded, so identical check sets do not establish identical execution conditions.
- Toolchain, policy downloads and command helpers support onboarding and terminal/CI use. Browser changes apply only to that scan and never overwrite .codeproof.yml.
- Responsive navigation, native dialogs, keyboard focus styles, live status messaging, locale-sensitive timestamps and no external asset requests keep the app useful across devices and networks.

## Local scale and storage

History is stored in `.codeproof/workspace/history.sqlite3`, ignored by Git. The oldest run is deleted when admitting a run beyond the 50-run retention limit. Keep exported reports elsewhere if longer retention is needed. History reads summary columns rather than loading every report payload. Browser caching is capped at 50 reports. Check execution uses the existing bounded pool of up to eight workers.

One active scan is admitted per server process; further submissions receive HTTP 409. There is no unbounded execution queue. Run one workspace server per repository. A restart marks unfinished records interrupted; it does not resume or cancel orphan subprocess trees. Existing per-tool timeouts still apply. Subprocess output is still buffered in memory before truncation; large-repository and load benchmarks remain follow-up work. No throughput improvement or distributed execution is claimed.

## Access and deployment

The default bind address is loopback. The API pins the repository at startup; requests cannot supply arbitrary target paths or shell commands. Mutations require a per-session token, matching Origin when present, and a permitted Host. Downloads are attachments and untrusted report text is escaped. Requests are limited to 64 KB and connections have a 15-second timeout. Assets use a restrictive content-security policy.

For a trusted development reverse proxy, specify its exact hostname using `--allowed-host` and use `--host 0.0.0.0` only when that proxy is appropriately restricted. The workspace token prevents cross-site scan submission; it is not user authentication. This release is a local single-user app. Public team deployment requires user authentication, authorization, isolated execution workers, shared storage/queues, quotas, observability and a separate deployment review.

## Product expansion priorities

1. Validate adoption with the four developer workflows, improve onboarding from real feedback, and add richer normalization for pytest and mypy.
2. Add report provenance for source revision, tool versions and effective policy; improve comparison equivalence checks and configure retention.
3. Add measured process/output limits and process-tree cancellation before raising concurrency or introducing incremental caching.
4. Add localization using an explicit translation catalog and validate keyboard/screen-reader workflows; English and browser-locale date formatting are delivered now.
5. Build a hosted team edition only after defining tenant isolation, identity, billing, data residency and operating budgets. Corporate visual design alone does not establish enterprise security or compliance.
