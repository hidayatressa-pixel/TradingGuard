@echo off
setlocal
title Stop TradingGuard

echo ========================================
echo          Stop TradingGuard
echo ========================================
echo.
echo Menghentikan service pada port 8000 dan 5173 ...

for %%P in (8000 5173) do (
  for /f "tokens=5" %%A in ('netstat -ano ^| findstr /R /C:":%%P .*LISTENING"') do (
    echo Menghentikan PID %%A pada port %%P ...
    taskkill /PID %%A /T /F >nul 2>&1
  )
)

echo.
echo TradingGuard dihentikan.
timeout /t 2 /nobreak >nul
endlocal
exit /b 0
