from datetime import datetime,timezone
from pathlib import Path
from . import __version__
from .adapters import run
from .models import ScanReport,Status
def grade(x:float)->str:return "A" if x>=90 else "B" if x>=80 else "C" if x>=70 else "D" if x>=60 else "F"
def scan(root,cfg,fail_under=None):
    results=[]
    for name,c in cfg.checks.items():
        if not c.enabled:continue
        r=run(name,root,c.config,cfg.timeout_seconds,cfg.source_paths,cfg.test_paths);r.weight=c.weight;r.required=name in cfg.required_tools;results.append(r)
    included=[r for r in results if r.status not in (Status.unavailable,Status.skipped) or r.required]
    denominator=sum(r.weight for r in included);score=100*sum(r.weight for r in included if r.status==Status.passed)/denominator if denominator else 0
    threshold=cfg.fail_under if fail_under is None else fail_under
    required_ok=all(not r.required or r.status==Status.passed for r in results)
    unavailable=[r.name for r in results if r.status==Status.unavailable and not r.required]
    limitations=["Passing configured checks is not proof of correctness.","pytest and import checks may execute repository code."]
    if unavailable:limitations.append("Optional checks excluded from score: "+", ".join(unavailable))
    return ScanReport(project=root.name,target=str(root),generated_at=datetime.now(timezone.utc).isoformat(),codeproof_version=__version__,score=round(score,2),grade=grade(score),policy_passed=score>=threshold and required_ok,fail_under=threshold,results=results,limitations=limitations)
