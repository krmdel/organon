# Remove the cron dispatcher scheduled task. Job files are left untouched.

# Derive the same slug used during install
$ProjectDir = Split-Path -Parent $PSScriptRoot
$ProjectSlug = (Split-Path -Leaf $ProjectDir).ToLower() -replace '[^a-z0-9-]', '-'
$TaskName = "Organon-$ProjectSlug"

$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if (-not $existing) {
    Write-Host "Cron dispatcher is not installed. Nothing to remove."
    exit 0
}

Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false

Write-Host "Cron dispatcher removed."
Write-Host "Your job files in cron/jobs/ are still there - they just won't run automatically."
