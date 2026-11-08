import ast
from collections import defaultdict
from pathlib import Path

from .files import python_files


def symbols(root: Path, sources: list[str]):
    out = []
    for path, _ in python_files(root, sources):
        try:
            tree = ast.parse(path.read_bytes())
        except (SyntaxError, UnicodeError):
            continue
        for node in tree.body:
            if isinstance(
                node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
            ) and not node.name.startswith("_"):
                out.append((node.name, path.relative_to(root), node.lineno))
    return out


def generate(root: Path, sources: list[str], output: Path, force=False):
    output.mkdir(parents=True, exist_ok=True)
    groups = defaultdict(list)
    bases = {path.relative_to(root): base for path, base in python_files(root, sources)}
    for name, path, _ in symbols(root, sources):
        parts = list((root / path).relative_to(bases[path]).with_suffix("").parts)
        if parts[-1] == "__init__":
            parts.pop()
        module = ".".join(parts)
        if module:
            groups[module].append(name)
    made = []
    for module, names in groups.items():
        # Length-prefix components to avoid collisions such as a_b.c and a.b_c.
        slug = "_".join(f"{len(part)}_{part}" for part in module.split("."))
        dest = output / f"test_{slug}_generated.py"
        if dest.exists() and not force:
            continue
        text = f"import importlib\n\nmodule = importlib.import_module({module!r})\n"
        for name in names:
            text += f"\n\ndef test_{name}_is_exposed():\n    assert hasattr(module, {name!r})\n"
        dest.write_text(text, encoding="utf-8")
        made.append(dest)
    return made
