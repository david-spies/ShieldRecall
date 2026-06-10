@echo off
:: ============================================================
:: launch.bat — Shield Recall launcher for Windows
::
:: Attempts to re-launch itself with Administrator privileges
:: via PowerShell's Start-Process -Verb RunAs so the kill
:: switch can write to HKLM.
::
:: Usage:
::   Double-click launch.bat   — prompts for UAC elevation
::   launch.bat --no-admin     — runs without elevation (kill switch disabled)
:: ============================================================

setlocal

set SCRIPT_DIR=%~dp0
set VENV_PYTHON=%SCRIPT_DIR%.venv\Scripts\python.exe
set FALLBACK_PYTHON=python

:: Check if --no-admin flag was passed
if "%1"=="--no-admin" goto :run

:: Check if already elevated
net session >nul 2>&1
if %errorLevel% == 0 goto :run

echo Requesting administrator privileges for registry control...
echo (You can decline — the dashboard will work, but the kill switch will be disabled.)
echo.

powershell -Command "Start-Process -FilePath '%~f0' -ArgumentList '--no-admin' -Verb RunAs -Wait"
exit /b

:run
echo ============================================================
echo   Shield Recall — Enterprise Privacy Engine
echo ============================================================

:: Activate virtual environment if it exists
if exist "%VENV_PYTHON%" (
    echo Using virtual environment: %VENV_PYTHON%
    set PYTHON=%VENV_PYTHON%
) else (
    echo Virtual environment not found at .venv — using system Python.
    set PYTHON=%FALLBACK_PYTHON%
)

:: Copy .env.example to .env if .env is missing
if not exist "%SCRIPT_DIR%.env" (
    echo .env not found — creating from .env.example...
    copy "%SCRIPT_DIR%.env.example" "%SCRIPT_DIR%.env" >nul
    echo Please review .env and set a strong SHIELD_RECALL_KEY before use.
    echo.
)

:: Launch
echo Starting server on http://127.0.0.1:8000
echo Press Ctrl+C to stop.
echo.

cd /d "%SCRIPT_DIR%"
%PYTHON% main.py

pause
endlocal
