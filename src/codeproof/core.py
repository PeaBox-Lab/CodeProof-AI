from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from . import __version__
from .adapters import run
from .models import CheckResult, ScanReport, Status


def grade(x: float) -> str:
    return (
        "A"
        if x >= 90
        else "B"
        if x >= 80
        else "C"
        if x >= 70
        else "D"
        if x >= 60
        else "F"
    )


def scan(root, cfg, fail_under=None, jobs=None):
    threshold = cfg.fail_under if fail_under is None else fail_under
    workers = cfg.jobs if jobs is None else jobs
    if not 0 <= threshold <= 100:
        raise ValueError("fail_under must be between 0 and 100")
    if not 1 <= workers <= 8:
        raise ValueError("jobs must be between 1 and 8")
    selected = [(name, check) for name, check in cfg.checks.items() if check.enabled]

    def execute(item):
        name, check = item
        result = run(
            name,
            root,
            check.config,
            cfg.timeout_seconds,
            cfg.source_paths,
            cfg.test_paths,
        )
        result.weight = check.weight
        result.required = name in cfg.required_tools
        return result

    # map preserves policy order even when workers finish out of order.
    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(execute, selected))
    for name in dict.fromkeys(cfg.required_tools):
        if not any(result.name == name for result in results):
            results.append(
                CheckResult(
                    name=name,
                    status=Status.skipped,
                    required=True,
                    summary="Required check is disabled or absent from the policy",
                )
            )
    included = [
        r
        for r in results
        if r.status not in (Status.unavailable, Status.skipped) or r.required
    ]
    denominator = sum(r.weight for r in included)
    score = (
        100 * sum(r.weight for r in included if r.status == Status.passed) / denominator
        if denominator
        else 0
    )
    required_ok = all(not r.required or r.status == Status.passed for r in results)
    unavailable = [
        r.name for r in results if r.status == Status.unavailable and not r.required
    ]
    limitations = [
        "Passing configured checks is not proof of correctness.",
        "pytest and import checks may execute repository code.",
    ]
    if unavailable:
        limitations.append(
            "Optional checks excluded from score: " + ", ".join(unavailable)
        )
    if denominator == 0:
        limitations.append(
            "No weighted checks contributed evidence; policy cannot pass."
        )
    return ScanReport(
        project=root.name,
        target=str(root),
        generated_at=datetime.now(timezone.utc).isoformat(),
        codeproof_version=__version__,
        score=round(score, 2),
        grade=grade(score),
        policy_passed=score >= threshold and required_ok and denominator > 0,
        fail_under=threshold,
        results=results,
        limitations=limitations,
    )
