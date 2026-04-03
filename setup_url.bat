@echo off
echo Setting up http://pnlAX ...

:: Add hosts entry
findstr /C:"pnlAX" C:\Windows\System32\drivers\etc\hosts >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo 127.0.0.1       pnlAX >> C:\Windows\System32\drivers\etc\hosts
    echo [OK] Added pnlAX to hosts file
) else (
    echo [OK] pnlAX already in hosts file
)

:: Forward port 80 -> 5000 so no port number needed in URL
netsh interface portproxy add v4tov4 listenport=80 listenaddress=127.0.0.1 connectport=5000 connectaddress=127.0.0.1
echo [OK] Port 80 -> 5000 forwarding set

echo.
echo Done! Open your browser and go to:
echo   http://pnlAX
echo.
pause
