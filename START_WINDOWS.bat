@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
py -3.13 -c "import sys" >nul 2>&1
if not errorlevel 1 (
    py -3.13 scripts\launch_local.py
    goto finished
)
py -3.12 -c "import sys" >nul 2>&1
if not errorlevel 1 (
    py -3.12 scripts\launch_local.py
    goto finished
)
python -c "import sys; raise SystemExit(0 if (3,12) <= sys.version_info[:2] <= (3,14) else 1)" >nul 2>&1
if not errorlevel 1 (
    python scripts\launch_local.py
    goto finished
)
echo Python is missing. Install Python 3.13 from python.org.
echo During installation, enable "Add python.exe to PATH".
echo Then double-click START_WINDOWS.bat again.
pause
exit /b 1
:finished
if errorlevel 1 echo The store could not start. Please read the error above.
pause
