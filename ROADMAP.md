# CodeProof-AI — 10-Release Roadmap

Current version: **0.1.0** (CLI + GitHub Action + local developer workspace, 9 checks, SARIF/JSON/MD/HTML reports, provenance, coverage ingestion, bounded findings, configurable retention).

## Guiding principles
- **Evidence over claims**: reports show what ran, what passed/failed, and what was excluded.
- **Local-first & transparent**: predictable execution, explicit limitations, user-controlled network use.
- **Composable**: CLI, GUI, and CI share one core engine and policy.
- **Safe by default**: clear warnings when scanning executes untrusted code.

## Releases

### v0.2.0 — CI adoption & annotations
- GitHub Code Scanning annotations from SARIF; PR comment summaries.
- Configurable local Semgrep rules directory (offline, no rule downloads).
- Lockfile support for pip-audit (poetry.lock, Pipfile.lock, uv.lock).
- Machine-readable `doctor --json` (delivered) + install hints.
- Exit criteria: SARIF validates against schema; annotations point to source lines; offline config completes without network.

### v0.3.0 — Stronger evidence (part 1)
- Severity-aware policy: fail on high/critical findings even when a tool exits 0.
- Versioned report schema (1.0 → 1.1) with migration + consumer contract tests.
- Real pytest counts & coverage ingestion (delivered).
- mypy normalization (delivered).
- Exit criteria: high-severity gates cannot be offset by unrelated passes; schema migration tests pass.

### v0.4.0 — Faster large repositories
- Benchmarked discovery (p50/p95 timings on small/medium/large fixtures).
- Streamed/limited subprocess output (no unbounded buffering).
- Process-tree cancellation on timeout (no orphan processes).
- Incremental cache keyed on source, config, locks, tool/Python versions.
- Exit criteria: no orphan processes after timeout; changed inputs invalidate cache; timings published.

### v0.5.0 — Changed-code baselines
- Git-diff-scoped findings (only changed lines/files).
- Baseline vs. current comparison with new/resolved grouping (UI delivered; equivalence checks improved).
- Configure retention (delivered) + export of long-term history.
- Exit criteria: compare two saved reports without rerunning; policy changes show a clear diff.

### v0.6.0 — Team workflows (part 1)
- Reviewable policy templates (strict/balanced/fast/security) with clear diffs.
- Distributable static viewer (single HTML with embedded data, no server).
- Report history comparison equivalence checks.
- Exit criteria: keyboard & screen-reader checks pass; artifacts require no external assets.

### v0.7.0 — Accessibility & localization
- Full keyboard/screen-reader audit and fixes.
- Explicit translation catalog (i18n) with English + browser-locale date formatting (delivered baseline).
- High-contrast theme and reduced-motion support.
- Exit criteria: WCAG 2.2 AA for core flows; localization catalog validated.

### v0.8.0 — Extensibility & multi-language groundwork
- Stable plugin/adapter API for custom checks (coverage, vulture, complexity, license).
- Abstract runner/report model to support JS/TS while keeping Python best-in-class.
- Configurable worker pool defaults with measured speedups.
- Exit criteria: documented extension API; at least one third-party-style adapter example.

### v0.9.0 — Stability & compatibility
- Supported Python-version matrix (3.10–3.13) in CI.
- Packaging smoke tests (HTML template verified in built wheels).
- Pinned reproducible CI dependency set with update cadence.
- Backward-compatible config migrations and versioned report schema guarantees.
- Exit criteria: integration coverage for supported checker versions; hostile JSON/text fixtures.

### v1.0.0 — General availability
- Stability guarantees: versioned report schema, backward-compatible config, documented extension API.
- Policy packs & provenance (signed/shareable profiles).
- Workspace/monorepo support: per-package policies, aggregated scoring, targeted scans.
- Exit criteria: public API documented; migration guide; no breaking changes without major bump.

### v1.1.0 — AI-assisted, evidence-grounded insights (optional)
- Summarize findings and suggest fixes with citations to check output.
- Opt-in only; never claims correctness; preserves local-first core.
- Exit criteria: every suggestion cites evidence; user can disable entirely.

## Status legend
- (delivered) items already shipped in 0.1.0.
- M/L effort estimates remain relative planning, not dates.
- Hosted team edition (auth, queues, multi-tenant) requires separate product demand and security design; not scheduled.