# Registers a Windows scheduled task that runs scraper\run.py every 30 minutes
# while you are logged in. Re-run to update; remove with:
#   Unregister-ScheduledTask -TaskName "GeotagDashboardUpdate" -Confirm:$false

$root = Split-Path -Parent $PSScriptRoot
$python = (Get-Command python).Source
$pythonw = Join-Path (Split-Path $python) "pythonw.exe"   # no console window

$action = New-ScheduledTaskAction -Execute $pythonw -Argument "`"$root\scraper\run.py`"" -WorkingDirectory $root
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes 30)
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopIfGoingOnBatteries -AllowStartIfOnBatteries `
    -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 25)

Register-ScheduledTask -TaskName "GeotagDashboardUpdate" -Action $action -Trigger $trigger -Settings $settings `
    -Description "Downloads Green TN Mission exports and rebuilds the geotag summary" -Force | Out-Null

Write-Host "Scheduled: GeotagDashboardUpdate runs every 30 minutes."
