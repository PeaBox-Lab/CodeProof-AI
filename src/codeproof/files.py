"""Shared deterministic traversal; never descend into caches or environments."""

import os
from pathlib import Path

EXCLUDED = {
    ".git",
    ".venv",
    "venv",
    "env",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".codeproof",
    "node_modules",
    "build",
    "dist",
}


def python_files(root: Path, sources: list[str]):
    seen = set()
    for source in sources:
        base = root / source
        if base.is_file():
            candidates = [base] if base.suffix == ".py" else []
        else:
            candidates = []
            for directory, folders, names in os.walk(base, followlinks=False):
                folders[:] = sorted(
                    name
                    for name in folders
                    if name not in EXCLUDED
                    and not (Path(directory) / name).is_symlink()
                )
                candidates.extend(
                    Path(directory) / name
                    for name in sorted(names)
                    if name.endswith(".py")
                )
        for path in candidates:
            if path.is_symlink():
                continue
            resolved = path.resolve()
            if not resolved.is_relative_to(root.resolve()) or resolved in seen:
                continue
            seen.add(resolved)
            yield path, base if base.is_dir() else base.parent
