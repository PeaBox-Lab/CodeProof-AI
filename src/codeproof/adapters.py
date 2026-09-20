import json,os,shutil,subprocess,sys,time
from pathlib import Path
from .models import CheckResult,Finding,Status
def run(name:str,root:Path,cfg:str|None,timeout:int,sources:list[str],tests:list[str])->CheckResult:
    src=[x for x in sources if (root/x).exists()] or ["."]
    commands={"ruff":["ruff","check",*src,"--output-format","json"],"mypy":["mypy",*src,"--no-error-summary"],"pytest":["pytest",*([x for x in tests if (root/x).exists()] or ["."]),"-q"],"bandit":["bandit","-r",*src,"-f","json","-q"],"semgrep":["semgrep","scan","--config",cfg or "auto","--json",*src]}
    if name=="imports": return imports(root,src,timeout)
    cmd=commands.get(name)
    if not cmd:return CheckResult(name=name,status=Status.skipped,summary="unknown adapter")
    if not shutil.which(cmd[0]):return CheckResult(name=name,status=Status.unavailable,command=cmd,summary=f"{cmd[0]} is not installed")
    started=time.perf_counter()
    try:
        cp=subprocess.run(cmd,cwd=root,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=timeout,env={**os.environ,"NO_COLOR":"1"})
        return CheckResult(name=name,status=Status.passed if cp.returncode==0 else Status.failed,command=cmd,duration_seconds=round(time.perf_counter()-started,3),exit_code=cp.returncode,summary="passed" if cp.returncode==0 else "reported findings",raw_output=(cp.stdout or "")[-50000:])
    except subprocess.TimeoutExpired as e:return CheckResult(name=name,status=Status.error,command=cmd,summary=f"timed out after {timeout}s")
def imports(root:Path,sources:list[str],timeout:int)->CheckResult:
    started=time.perf_counter(); findings=[]; count=0
    for src in sources:
        base=root/src
        for p in base.rglob("*.py") if base.exists() else []:
            if p.name=="__init__.py":continue
            module=".".join(p.relative_to(base).with_suffix("").parts); count+=1
            cp=subprocess.run([sys.executable,"-c",f"import sys;sys.path.insert(0,{str(base)!r});__import__({module!r})"],cwd=root,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=timeout)
            if cp.returncode:findings.append(Finding(level="error",message=(cp.stdout or "failed")[-800:],path=str(p.relative_to(root)),rule="import"))
    return CheckResult(name="imports",status=Status.passed if not findings else Status.failed,duration_seconds=round(time.perf_counter()-started,3),summary=f"{count} modules checked; {len(findings)} failed",findings=findings,evidence={"modules_checked":count})
