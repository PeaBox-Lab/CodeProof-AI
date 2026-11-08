#!/bin/sh
set -eu

# Run from the checkout even when launched from another directory.
cd "$(dirname "$0")"
repo_dir=$(pwd -P)
venv_python="$repo_dir/.venv/bin/python"

if [ ! -x "$venv_python" ]; then
    if command -v python3 >/dev/null 2>&1 && python3 -c 'import sys; sys.exit(sys.version_info < (3, 10))' >/dev/null 2>&1; then
        bootstrap=python3
    elif command -v python >/dev/null 2>&1 && python -c 'import sys; sys.exit(sys.version_info < (3, 10))' >/dev/null 2>&1; then
        bootstrap=python
    else
        echo 'Python 3.10 or newer was not found. Install Python and try again.' >&2
        exit 1
    fi
    echo 'Creating the virtual environment...'
    "$bootstrap" -m venv .venv
fi

# Ensure the environment points to this checkout, not another installation.
if ! "$venv_python" -c "import pathlib, codeproof.cli; assert pathlib.Path(codeproof.cli.__file__).resolve() == (pathlib.Path.cwd() / 'src' / 'codeproof' / 'cli.py').resolve()" >/dev/null 2>&1; then
    echo 'Installing CodeProof and its application dependencies...'
    "$venv_python" -m pip install -e .
fi

# Make checkers installed in the virtual environment visible to the GUI.
PATH="$repo_dir/.venv/bin:$PATH"
export PATH
echo 'Starting CodeProof at http://127.0.0.1:8787/'
echo 'To install scan checkers, see the Install section in README.md.'
echo 'Keep this terminal open while using the app. Press Ctrl+C to stop.'
exec "$venv_python" -m codeproof.cli gui --path "$repo_dir"