from pathlib import Path
import shutil,typer,yaml
from rich.console import Console
from rich.table import Table
from .config import load,DEFAULT
from .core import scan as execute
from .discovery import symbols,generate
from .reporting import write
app=typer.Typer(no_args_is_help=True);console=Console()
@app.command()
def doctor():
    t=Table("Tool","Status")
    for n in ["ruff","mypy","pytest","bandit","semgrep"]:t.add_row(n,"available" if shutil.which(n) else "missing")
    console.print(t)
@app.command()
def init(path:Path=Path("."),force:bool=False):
    p=path.resolve()/".codeproof.yml"
    if p.exists() and not force:raise typer.BadParameter("policy exists; use --force")
    p.write_text(yaml.safe_dump(DEFAULT.model_dump(mode="json"),sort_keys=False));console.print(f"Created {p}")
@app.command()
def inventory(path:Path=Path(".")):
    root=path.resolve();cfg=load(root);t=Table("Symbol","File","Line")
    data=symbols(root,cfg.source_paths)
    for n,p,l in data:t.add_row(n,str(p),str(l))
    console.print(t);console.print(f"{len(data)} public symbols")
@app.command("generate-tests")
def generate_tests(path:Path=Path("."),output:Path=Path("tests/generated"),force:bool=False):
    root=path.resolve();cfg=load(root);made=generate(root,cfg.source_paths,root/output,force);console.print(f"Created {len(made)} files")
@app.command()
def scan(path:Path=Path("."),format:str="all",fail_under:float|None=None,output:Path=Path(".codeproof/reports")):
    if format not in {"all","json","markdown","html"}:raise typer.BadParameter("invalid format")
    root=path.resolve();report=execute(root,load(root),fail_under);t=Table("Check","Status","Weight","Summary")
    for r in report.results:t.add_row(r.name,r.status.value,str(r.weight),r.summary)
    console.print(t);console.print(f"Score {report.score}/100 ({report.grade}); policy {'PASS' if report.policy_passed else 'FAIL'}")
    for p in write(report,root/output,format):console.print(f"Report: {p}")
    raise typer.Exit(0 if report.policy_passed else 1)

@app.command()
def gui(path:Path=Path("."),host:str="127.0.0.1",port:int=8787,no_open:bool=False):
    """Launch the local CodeProof GUI dashboard."""
    from .web import serve
    serve(host=host,port=port,target=path.resolve(),open_browser=not no_open)

if __name__=="__main__":app()

