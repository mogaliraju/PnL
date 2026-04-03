@echo off
echo Starting PnL Application...
cd /d "%~dp0"
start "" "http://localhost:5000"
python app.py
pause
