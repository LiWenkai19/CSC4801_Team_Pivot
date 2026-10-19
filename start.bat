@echo off
setlocal
set "ROOT=%~dp0"
set "PYTHON_EXE=python"
if defined CONDA_PREFIX if exist "%CONDA_PREFIX%\python.exe" set "PYTHON_EXE=%CONDA_PREFIX%\python.exe"
if not defined CONDA_PREFIX if exist "%USERPROFILE%\miniconda3\envs\SYManage\python.exe" set "PYTHON_EXE=%USERPROFILE%\miniconda3\envs\SYManage\python.exe"

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
    echo Python is unavailable. Activate the SYManage environment and retry.
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
"%PYTHON_EXE%" scripts\dev_start.py
set "RESULT=%ERRORLEVEL%"
popd
if not "%RESULT%"=="0" pause
exit /b %RESULT%
