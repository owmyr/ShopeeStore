# Registers Windows Task Scheduler entries for ShopeeStore.
# Run from an elevated-or-normal PowerShell:  powershell -File scripts\install_tasks.ps1
# Remove with: powershell -File scripts\uninstall_tasks.ps1
$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root ".venv\Scripts\python.exe"
$main = Join-Path $root "__main__.py"

if (-not (Test-Path $python)) { throw "venv python not found at $python - run setup first" }

$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -WakeToRun `
    -ExecutionTimeLimit (New-TimeSpan -Hours 2)

$weeklyAction = New-ScheduledTaskAction -Execute $python -Argument "`"$main`" run" -WorkingDirectory $root
$weeklyTrigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday -At 09:00
Register-ScheduledTask -TaskName "ShopeeStore-WeeklyRun" -Action $weeklyAction `
    -Trigger $weeklyTrigger -Settings $settings -Force `
    -Description "Weekly Shopee camisetas deep scrape + trend report + image harvest"

$pulseAction = New-ScheduledTaskAction -Execute $python -Argument "`"$main`" pulse" -WorkingDirectory $root
$pulseTrigger = New-ScheduledTaskTrigger -Daily -At 08:30
Register-ScheduledTask -TaskName "ShopeeStore-DailyPulse" -Action $pulseAction `
    -Trigger $pulseTrigger -Settings $settings -Force `
    -Description "Daily Shopee top-20 spike radar"

Write-Output "Registered: ShopeeStore-WeeklyRun (Mon 09:00), ShopeeStore-DailyPulse (daily 08:30)"
Write-Output "Tasks run only while this user is logged on. Verify: Get-ScheduledTask -TaskName ShopeeStore*"
