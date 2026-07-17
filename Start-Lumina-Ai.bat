@echo off
TITLE Lumina Ai Launcher
echo ===================================================
echo Starting Lumina Ai...
echo ===================================================
echo.

:: Change to the directory where this script is located
cd /d "%~dp0"

:: Start the backend API in a new hidden window (or minimized)
echo [1/2] Starting Lumina Ai Server...
start "Lumina Ai Server" /MIN cmd /c ".\.venv\Scripts\python.exe -m uvicorn backend.main:app --port 8000"

:: Wait a moment for the server to initialize
timeout /t 3 /nobreak >nul

:: Open the browser
echo [2/2] Opening Lumina Ai in your default web browser...
start http://localhost:8000

echo.
echo ===================================================
echo Lumina Ai is now running! 
echo.
echo To stop the application, please close the 
echo minimized command prompt window that was opened.
echo ===================================================
pause
