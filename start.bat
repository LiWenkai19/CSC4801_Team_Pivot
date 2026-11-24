@echo off
setlocal
set "ROOT=%~dp0"
rem Prefer the repository's own virtual environment, then Conda, then PATH.
set "PYTHON_EXE="
if exist "%ROOT%.venv\Scripts\python.exe" set "PYTHON_EXE=%ROOT%.venv\Scripts\python.exe"
if not defined PYTHON_EXE if defined CONDA_PREFIX if exist "%CONDA_PREFIX%\python.exe" set "PYTHON_EXE=%CONDA_PREFIX%\python.exe"
if not defined PYTHON_EXE if exist "%USERPROFILE%\miniconda3\envs\SYManage\python.exe" set "PYTHON_EXE=%USERPROFILE%\miniconda3\envs\SYManage\python.exe"
if not defined PYTHON_EXE set "PYTHON_EXE=python"

if not exist "%ROOT%backend\app\main.py" (
    echo Backend not found next to start.bat.
    exit /b 1
)
if not exist "%ROOT%frontend\package.json" (
    echo Frontend not found next to start.bat.
    exit /b 1
)
"%PYTHON_EXE%" --version >nul 2>&1
if errorlevel 1 (
    echo Python is unavailable: %PYTHON_EXE%
    echo Create .venv in the repository root or activate the SYManage environment, then retry.
    exit /b 1
)
rem Fail fast instead of letting dev_start.py crash on a missing import.
"%PYTHON_EXE%" -c "import fastapi, sqlmodel, uvicorn" >nul 2>&1
if errorlevel 1 (
    echo Backend dependencies are missing for: %PYTHON_EXE%
    echo Install them with: "%PYTHON_EXE%" -m pip install -r "%ROOT%requirements.txt"
    exit /b 1
)
where npm.cmd >nul 2>&1
if errorlevel 1 (
    echo npm is unavailable. Install Node.js and retry.
    exit /b 1
)
if not exist "%ROOT%frontend\node_modules\.bin\vite.cmd" (
    echo Frontend dependencies are missing. Run npm install in frontend first.
    exit /b 1
)

pushd "%ROOT%backend"
if errorlevel 1 exit /b 1
rem Enable Uvicorn reload for the local backend.
set "UVICORN_RELOAD=true"
"%PYTHON_EXE%" scripts\dev_start.py
set "RESULT=%ERRORLEVEL%"
popd
if not "%RESULT%"=="0" pause
exit /b %RESULT%
