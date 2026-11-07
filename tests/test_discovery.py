import ast

from codeproof.discovery import generate


def test_generates_all_symbols_once_and_preserves_manual_edits(tmp_path):
    src = tmp_path / "src" / "pkg"
    src.mkdir(parents=True)
    (src / "api.py").write_text(
        "def first(): pass\nasync def second(): pass\nclass Third: pass\n"
    )
    (src / "__init__.py").write_text("def exported(): pass\n")
    out = tmp_path / "generated"
    made = generate(tmp_path, ["src"], out)
    assert len(made) == 2
    text = next(p.read_text() for p in made if "first" in p.read_text())
    tree = ast.parse(text)
    assert len([n for n in tree.body if isinstance(n, ast.FunctionDef)]) == 3
    package = next(p for p in made if "exported" in p.read_text())
    assert "import_module('pkg')" in package.read_text()
    package.write_text("# manual")
    assert generate(tmp_path, ["src"], out) == []
    assert package.read_text() == "# manual"
    assert len(generate(tmp_path, ["src"], out, force=True)) == 2
    assert "exported" in package.read_text()
