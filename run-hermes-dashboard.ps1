# Smart Hermes Web Dashboard Startup Script
$EnvFile = "C:\Users\jeffr\AppData\Local\hermes\.env"
$HasAuth = $false

if (Test-Path $EnvFile) {
    $EnvContent = Get-Content $EnvFile
    $HasUser = $EnvContent | Select-String -SimpleMatch "HERMES_DASHBOARD_BASIC_AUTH_USERNAME="
    $HasHash = $EnvContent | Select-String -SimpleMatch "HERMES_DASHBOARD_BASIC_AUTH_PASSWORD_HASH="
    
    # Check if they are uncommented (i.e. do not start with '#')
    if ($HasUser -and -not $HasUser.Line.Trim().StartsWith("#") -and $HasHash -and -not $HasHash.Line.Trim().StartsWith("#")) {
        $HasAuth = $true
    }
}

Set-Location "C:\Users\jeffr\AppData\Local\hermes\hermes-agent"
$VenvPython = "C:\Users\jeffr\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe"

if ($HasAuth) {
    Write-Host "Auth credentials detected in .env. Binding to 0.0.0.0 for remote access." -ForegroundColor Green
    & $VenvPython -m hermes_cli.main dashboard --host 0.0.0.0 --port 9119 --no-open --skip-build
} else {
    Write-Host "No auth credentials detected in .env. Binding to 127.0.0.1 (local only) for security." -ForegroundColor Yellow
    & $VenvPython -m hermes_cli.main dashboard --host 127.0.0.1 --port 9119 --no-open --skip-build
}
