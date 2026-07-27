# Removes the ShopeeStore scheduled tasks.
$ErrorActionPreference = "Continue"
Unregister-ScheduledTask -TaskName "ShopeeStore-WeeklyRun" -Confirm:$false
Unregister-ScheduledTask -TaskName "ShopeeStore-DailyPulse" -Confirm:$false
Write-Output "Removed ShopeeStore scheduled tasks."
