<!-- coderabbit-ai-generated:v1 -->

# CodeProof AI — repository audit and delivery roadmap

## Product direction

CodeProof is a local Python CLI and reusable GitHub Action. Its strongest use cases are developer preflight checks, CI policy gates, and portable evidence for code review. Keep the local CLI as the execution engine and make its reports useful to maintainers before introducing a hosted product. A score summarizes configured checks; it cannot establish correctness or replace behavioral tests.

Audit baseline: `7043a711daefaed5a2f973d51ec856a5ef00d703`. The initial package had six adapters, a weighted score, an AST symbol inventory, exposure-test generation, three report formats, and two tests. There was no application server, database, hosted account system, or test-coverage analysis. The inventory should not be described as identifying untested behavior.

## Audit findings and delivered repairs

| Priority | Finding and evidence | Delivered improvement |
|---|---|---|
| P0 | `core.py` checked required gates only for executed results; disabling or omitting one bypassed its gate | Emit required skipped results and fail policy; no weighted evidence cannot pass, including at threshold zero |
| P0 | `config.py` accepted invalid weights/timeouts and replaced all default checks when a partial file existed | Validate policy ranges, unknown settings/tools and version; merge partial overrides with defaults |
| P0 | `action.yml` interpolated inputs directly into shell scripts | Pass inputs through quoted environment variables; upload report artifacts including the hidden report directory |
| P0 | Semgrep ran without `--error`, permitting successful exit despite findings | Findings now produce a failed check; this may lower previously misleading scores |
| P1 | Documented positional CLI paths were interpreted as options | Support documented positional paths and retain the existing `--path` option for compatibility |
| P1 | `adapters.py` returned almost exclusively raw output and import timeouts escaped the adapter | Normalize Ruff/Bandit/Semgrep/pip-audit findings; retain raw diagnostics; contain launch and timeout errors; enforce total import time budget |
| P1 | All adapters ran serially | Configurable worker pool (1–8), stable result order; serial remains default |
| P1 | HTML had only an unstyled summary table | Offline responsive report, policy explanation, search, status filters, expandable findings and raw evidence; keyboard focus styles and live count |
| P1 | No dependency vulnerability or execution-free syntax tools | Opt-in `pip-audit` for root requirements.txt; built-in `syntax` without execution or bytecode writes; discoverable tools and install guidance |
| P1 | Test generation wrote only the first symbol per module without force, duplicated on force, and mishandled package imports | Group symbols by module, replace once on force, preserve existing files, handle package exports and avoid module filename collisions |
| P1 | File discovery descended into environments and caches | Shared deterministic traversal prunes common generated trees, skips symlinks and deduplicates overlapping roots |
| P1 | Only grade and total weights had tests | Regression coverage for policy gates, config, parallel execution, adapter errors, structured evidence, generation, escaping and CLI workflows |

## Compatibility and intentional changes

- Existing six default checks and their weights (100 total) remain. Both new tools are opt-in; all report filenames and JSON schema 1.0 fields remain. Existing `--path` callers remain supported.
- A partial YAML policy now overlays defaults. Previously, specifying only `fail_under` could run no checks. To run a smaller set, disable the other checks explicitly or use `--checks`; remove a tool from `required_tools` only when that policy change is intended.
- Disabled or absent required checks fail policy, matching the README's required-tool guarantee. Empty evidence fails even if the threshold is zero. Invalid or misspelled policies now fail with CLI exit code 2.
- Semgrep findings now fail the check. Optional unavailable checks remain excluded from the score; required unavailable checks block policy.
- Generated filenames now use length-prefixed module components to avoid collisions. Existing generated files are preserved; review and remove obsolete files before regenerating into the same directory.
- Concurrent execution is opt-in because tests and imports execute repository code and may share resources. Each tool has a time budget; concurrency is not a sandbox or a process/memory quota.

## Prioritized roadmap

| Phase | Work | Exit criteria | Effort |
|---|---|---|---|
| 1 — Delivered | Policy integrity, actionable reports, opt-in tools, bounded workers, generation repairs and regression tests | Local CLI and Action retain compatibility; policy bypass regressions pass; report controls work on desktop and mobile | This change |
| 2 — CI adoption | SARIF export and GitHub annotations; machine-readable doctor; configurable local Semgrep rules; lockfile support for pip-audit; supported Python-version matrix | SARIF validates against its schema; annotations point to source lines; offline configuration completes without rule downloads; locked dependency fixtures yield stable findings | M |
| 3 — Faster large repositories | Benchmarked discovery, streamed/limited subprocess output, process-tree cancellation, bounded findings, incremental cache | Representative small/medium/large fixtures publish timings; no orphan processes after timeout; cache keys include source, config, dependency locks, tool/Python versions; changed inputs invalidate results | L |
| 4 — Stronger evidence | Real pytest counts and coverage ingestion; mypy normalization; severity-aware policy; changed-code baselines; versioned report schema | Inventory remains distinct from coverage; original evidence retained; high-severity gates cannot be offset by unrelated passes; schema migration and consumer contract tests pass | L |
| 5 — Team workflows | Report history and comparison; reviewable policy templates; distributable static viewer; accessible navigation/contrast audit | Compare two saved reports without rerunning code; policy changes show a clear diff; keyboard and screen-reader checks pass; report artifacts require no external assets | M |

M and L are relative planning estimates, not delivery dates. Phase 2 should precede persistent history or a hosted service. Hosted authentication, queues, object storage and multi-tenant execution need separate product demand and a security design; this repository does not currently contain those facilities.

## Engineering tools and delivery discipline

- Use Ruff format/lint, mypy with PyYAML stubs, pytest regression tests, and Bandit for changes to process execution and reporting. Keep dependency auditing as an explicit extra rather than a mandatory network dependency for every local scan.
- Add packaging smoke tests so the HTML template is verified inside built wheels. Pin a reproducible CI dependency set in the next phase and document an update cadence.
- Measure p50/p95 scan time, peak memory, adapter error rates, policy pass rates with missing tools, and report size on synthetic fixtures before implementing caching or claiming speedups. Worker parallelism is delivered; no benchmarked speedup is claimed.
- Preserve the schema and exit-code contract (0 pass, 1 policy fail, 2 usage/config error). Add integration coverage for supported checker versions and hostile JSON/text fixtures.

## Remaining limits

Dependency auditing currently supports only a root requirements.txt and requires the optional pip-audit executable and network access. Resolution can invoke package build tooling; use isolated runners for untrusted requirements. Semgrep auto may retrieve rules. Tool processes still capture output in memory before retaining the final 50 KB; nested child processes are not comprehensively cancelled. The import adapter skips standalone package `__init__.py` files, as before. Syntax checks do not establish runtime importability, and generated tests only check symbol exposure. Reports are snapshots; filters never alter the policy score. Live GitHub Action execution requires pushing and running the workflow. Broader minimum-Python and accessibility coverage remain roadmap work.
