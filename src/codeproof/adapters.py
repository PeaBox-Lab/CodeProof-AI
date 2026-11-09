import json,os,re,shutil,subprocess,sys,time
from pathlib import Path
from .models import CheckResult,Finding,Status
def _rel(root:Path,p:str|None)->str|None:
    if not p:return None
    try:
        pp=Path(p)
        if pp.is_absolute(): return str(pp.relative_to(root))
    except Exception: pass
    return p
def _level_from_code(code:str|None)->str:
    if code and str(code)[:1].upper()=="W":return "warning"
    return "error"
def parse_findings(name:str,root:Path,cp:subprocess.CompletedProcess)->list[Finding]:
    out=[]
    text=cp.stdout or ""
    if name=="ruff":
        try:
            for item in (json.loads(text) or []):
                loc=item.get("location") or {}
                out.append(Finding(level=_level_from_code(item.get("code")),message=item.get("message",""),path=_rel(root,item.get("filename")),line=loc.get("row"),rule=item.get("code")))
        except Exception: pass
    elif name=="bandit":
        try:
            for item in (json.loads(text).get("results") or []):
                sev=str(item.get("issue_severity","MEDIUM")).upper()
                level="error" if sev in ("HIGH","MEDIUM") else "warning"
                out.append(Finding(level=level,message=item.get("issue_text",""),path=_rel(root,item.get("filename")),line=item.get("line_number"),rule=item.get("test_id")))
        except Exception: pass
    elif name=="semgrep":
        try:
            for item in (json.loads(text).get("results") or []):
                extra=item.get("extra") or {}
                sev=str(extra.get("severity","WARNING")).upper()
                level="error" if sev in ("ERROR","HIGH") else "warning" if sev in ("WARNING","MEDIUM") else "info"
                start=item.get("start") or {}
                out.append(Finding(level=level,message=extra.get("message",""),path=_rel(root,item.get("path")),line=start.get("line"),rule=item.get("check_id")))
        except Exception: pass
    elif name=="mypy":
        for m in re.finditer(r"^(.+?):(\d+)(?::\d+)?:\s*(error|warning|note):\s*(.*?)(?:\s+\[([^\]]+)\])?$", text, re.M):
            path,line,sev,msg,code=m.groups()
            level={"error":"error","warning":"warning","note":"info"}[sev]
            out.append(Finding(level=level,message=msg,path=_rel(root,path),line=int(line),rule=code))
    elif name=="pytest":
        for line in text.splitlines():
            m=re.match(r"^FAILED\s+(.+?)(?:\s+-\s+(.*))?$", line.strip())
            if m:
                node=m.group(1); msg=m.group(2) or "test failed"
                path=node.split("::")[0]
                out.append(Finding(level="error",message=msg,path=_rel(root,path),rule="pytest"))
    return out
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
        findings=parse_findings(name,root,cp)
        summary="passed" if cp.returncode==0 else (f"{len(findings)} findings" if findings else "reported findings")
        return CheckResult(name=name,status=Status.passed if cp.returncode==0 else Status.failed,command=cmd,duration_seconds=round(time.perf_counter()-started,3),exit_code=cp.returncode,summary=summary,findings=findings,raw_output=(cp.stdout or "")[-50000:])
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