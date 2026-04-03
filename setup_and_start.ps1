# Self-elevate if not already admin
if (-NOT ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]"Administrator")) {
    Start-Process powershell "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`"" -Verb RunAs
    exit
}

Write-Host "=== PnL Application Setup ===" -ForegroundColor Cyan

# 1. Add hosts entry
$hostsFile = "C:\Windows\System32\drivers\etc\hosts"
$entry = "127.0.0.1       pnlAX"
$existing = Get-Content $hostsFile | Where-Object { $_ -match "pnlAX" }
if (-not $existing) {
    Add-Content $hostsFile "`n$entry"
    Write-Host "[OK] Added pnlAX to hosts file" -ForegroundColor Green
} else {
    Write-Host "[OK] pnlAX already in hosts file" -ForegroundColor Yellow
}

# 2. Port forwarding 80 -> 5000
netsh interface portproxy delete v4tov4 listenport=80 listenaddress=127.0.0.1 | Out-Null
netsh interface portproxy add v4tov4 listenport=80 listenaddress=127.0.0.1 connectport=5000 connectaddress=127.0.0.1
Write-Host "[OK] Port 80 -> 5000 forwarding active" -ForegroundColor Green

# 3. Allow port 80 through firewall
netsh advfirewall firewall delete rule name="PnL App Port 80" | Out-Null
netsh advfirewall firewall add rule name="PnL App Port 80" dir=in action=allow protocol=TCP localport=80 | Out-Null
Write-Host "[OK] Firewall rule added for port 80" -ForegroundColor Green

# 4. Register auto-start task
$python = "C:\Users\15743\AppData\Local\Programs\Python\Python312\python.exe"
$script = "D:\PnL Application\app.py"
$action = New-ScheduledTaskAction -Execute $python -Argument "`"$script`""
$trigger = New-ScheduledTaskTrigger -AtLogOn
$settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit 0
Unregister-ScheduledTask -TaskName "PnL Application" -Confirm:$false -ErrorAction SilentlyContinue
Register-ScheduledTask -TaskName "PnL Application" -Action $action -Trigger $trigger -Settings $settings -RunLevel Highest -Force | Out-Null
Write-Host "[OK] Auto-start on login registered" -ForegroundColor Green

# 5. Start Flask now (if not already running)
$running = Get-NetTCPConnection -LocalPort 5000 -ErrorAction SilentlyContinue
if (-not $running) {
    Start-Process -FilePath $python -ArgumentList "`"$script`"" -WindowStyle Hidden
    Start-Sleep -Seconds 2
    Write-Host "[OK] Flask app started" -ForegroundColor Green
} else {
    Write-Host "[OK] Flask app already running" -ForegroundColor Yellow
}

# 6. Flush DNS cache
ipconfig /flushdns | Out-Null
Write-Host "[OK] DNS cache flushed" -ForegroundColor Green

Write-Host ""
Write-Host "All done! Open your browser and go to:" -ForegroundColor Cyan
Write-Host "  http://pnlAX" -ForegroundColor White -BackgroundColor DarkGreen
Write-Host ""
Start-Process "http://pnlAX"
Read-Host "Press Enter to close"
