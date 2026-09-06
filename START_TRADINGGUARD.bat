@echo off
setlocal
cd /d "%~dp0"
title TradingGuard Launcher

echo ========================================
echo        TradingGuard v0.9 Launcher
echo ========================================
echo.

if not exist ".venv\Scripts\python.exe" (
  echo [ERROR] Python virtual environment tidak ditemukan.
  echo Expected: %CD%\.venv\Scripts\python.exe
  pause
  exit /b 1
)

if not exist "frontend\package.json" (
  echo [ERROR] Folder frontend tidak ditemukan.
  pause
  exit /b 1
)

echo [1/3] Menjalankan backend FastAPI di http://127.0.0.1:8000 ...
start "TradingGuard Backend" cmd /k "cd /d "%CD%" && .venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000"

echo [2/3] Menjalankan frontend Vite di http://127.0.0.1:5173 ...
start "TradingGuard Frontend" cmd /k "cd /d "%CD%\frontend" && npm.cmd run dev -- --host 127.0.0.1 --port 5173"

echo [3/3] Menunggu service siap lalu membuka browser ...
timeout /t 4 /nobreak >nul
start "" "http://127.0.0.1:5173"

echo.
echo TradingGuard sedang berjalan.
echo Backend : http://127.0.0.1:8000
echo Frontend: http://127.0.0.1:5173
echo.
echo Untuk mematikan TradingGuard, double-click STOP_TRADINGGUARD.bat.
timeout /t 2 /nobreak >nul
endlocal
exit /b 0
