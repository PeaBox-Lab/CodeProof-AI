import ast
from pathlib import Path
def symbols(root:Path,sources:list[str]):
    out=[]
    for src in sources:
        base=root/src
        for p in base.rglob("*.py") if base.exists() else []:
            try:tree=ast.parse(p.read_text())
            except SyntaxError:continue
            for n in tree.body:
                if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)) and not n.name.startswith("_"):out.append((n.name,p.relative_to(root),n.lineno))
    return out
def generate(root:Path,sources:list[str],output:Path,force=False):
    output.mkdir(parents=True,exist_ok=True);made=[]
    for name,p,line in symbols(root,sources):
        src=next((s for s in sources if str(p).startswith(s+"/")),sources[0]);mod=".".join(Path(p).relative_to(src).with_suffix("").parts);dest=output/f"test_{mod.replace('.','_')}_generated.py"
        text=(dest.read_text() if dest.exists() else f'import importlib\nmodule=importlib.import_module("{mod}")\n')+f'\ndef test_{name}_is_exposed():\n    assert hasattr(module,"{name}")\n'
        if force or not dest.exists():dest.write_text(text);made.append(dest)
    return made
