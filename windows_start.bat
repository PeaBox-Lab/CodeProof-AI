:create_venv
echo Creating the virtual environment...
%BOOTSTRAP% -m venv .venv
if errorlevel 1 goto error

:check_install
rem Ensure the environment points to this checkout, not another installation.
".venv\Scripts\python.exe" -c "import pathlib, codeproof.cli; assert pathlib.Path(codeproof.cli.__file__).resolve() == (pathlib.Path.cwd() / 'src' / 'codeproof' / 'cli.py').resolve()" >nul 2>&1
if not errorlevel 1 goto start_app

echo Installing CodeProof and its application dependencies...
".venv\Scripts\python.exe" -m pip install -e .
if errorlevel 1 goto error

:start_app
rem Make checkers installed in the virtual environment visible to the GUI.
set "PATH=%CD%\.venv\Scripts;%PATH%"
echo Starting CodeProof at http://127.0.0.1:8787/
echo To install scan checkers, see the Install section in README.md.
echo Keep this window open while using the app. Press Ctrl+C to stop.
".venv\Scripts\python.exe" -m codeproof.cli gui --path "%CD%"
if errorlevel 1 goto error
popd
exit /b 0

:directory_error
echo Could not open the CodeProof directory.
echo Press any key to close this window.
pause >nul
exit /b 1

:error
echo CodeProof could not start. Check the messages above and try again.
echo Press any key to close this window.
pause >nul
popd
exit /b 1