@echo off
echo Registering PnL Application as a startup service...
schtasks /Create /TN "PnL Application" /TR "\"C:\Users\15743\AppData\Local\Programs\Python\Python312\python.exe\" \"D:\PnL Application\app.py\"" /SC ONLOGON /RL HIGHEST /F
if %ERRORLEVEL% == 0 (
    echo.
    echo Success! PnL Application will start automatically on login.
    echo Open your browser and go to: http://localhost:5000
) else (
    echo.
    echo Failed. Try running this file as Administrator.
)
pause
