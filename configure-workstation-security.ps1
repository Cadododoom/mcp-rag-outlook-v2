# Interactive Workstation Security Configuration & Passcode Rotation Script
$ErrorActionPreference = "Stop"

Write-Host "==========================================================" -ForegroundColor Green
Write-Host "     AI WORKSTATION REMOTE ACCESS PASSCODE ROTATOR        " -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Green

# Helper function to generate secure random strings (default to 32 characters)
function Get-RandomString ($Length = 32) {
    $Bytes = New-Object Byte[] $Length
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($Bytes)
    return [System.Convert]::ToBase64String($Bytes).Replace("/", "").Replace("+", "").Replace("=", "").Substring(0, $Length)
}

# -----------------------------------------------------------------------------
# 1. Hermes Web Dashboard basic auth
# -----------------------------------------------------------------------------
Write-Host "`n[1/3] Configuring Hermes Web Dashboard Auth (32-character security)..." -ForegroundColor Cyan
$HermesEnv = "C:\Users\jeffr\AppData\Local\hermes\.env"

$Username = Read-Host "Enter Hermes Dashboard Username [default: admin]"
if ([string]::IsNullOrEmpty($Username)) {
    $Username = "admin"
}

$Password = Read-Host "Enter Hermes Dashboard Password [leave blank to auto-generate 32-char password]"
if ([string]::IsNullOrEmpty($Password)) {
    $Password = Get-RandomString 32
    Write-Host "Auto-generated secure password: $Password" -ForegroundColor Yellow
}

# Use python virtual environment to hash the password
Write-Host "Hashing password using scrypt..." -ForegroundColor Yellow
$PythonExe = "C:\Users\jeffr\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe"
$Hash = & $PythonExe -c "from plugins.dashboard_auth.basic import hash_password; print(hash_password('$Password'))"
$Secret = Get-RandomString 32

if (-not (Test-Path $HermesEnv)) {
    New-Item -ItemType File -Path $HermesEnv -Force | Out-Null
}

$EnvContent = Get-Content $HermesEnv
$NewEnvContent = @()

# Process .env lines, removing existing auth keys
foreach ($Line in $EnvContent) {
    if ($Line -match "^HERMES_DASHBOARD_BASIC_AUTH_USERNAME=" -or 
        $Line -match "^HERMES_DASHBOARD_BASIC_AUTH_PASSWORD_HASH=" -or 
        $Line -match "^HERMES_DASHBOARD_BASIC_AUTH_SECRET=" -or
        $Line -match "^#\s*HERMES_DASHBOARD_BASIC_AUTH_USERNAME=" -or 
        $Line -match "^#\s*HERMES_DASHBOARD_BASIC_AUTH_PASSWORD_HASH=" -or 
        $Line -match "^#\s*HERMES_DASHBOARD_BASIC_AUTH_SECRET=") {
        continue
    }
    $NewEnvContent += $Line
}

# Append the new uncommented credentials
$NewEnvContent += "HERMES_DASHBOARD_BASIC_AUTH_USERNAME=$Username"
$NewEnvContent += "HERMES_DASHBOARD_BASIC_AUTH_PASSWORD_HASH=$Hash"
$NewEnvContent += "HERMES_DASHBOARD_BASIC_AUTH_SECRET=$Secret"

Set-Content -Path $HermesEnv -Value $NewEnvContent -Encoding utf8
Write-Host "Successfully configured Hermes Dashboard auth credentials in .env." -ForegroundColor Green


# -----------------------------------------------------------------------------
# 2. OpenChamber UI Password
# -----------------------------------------------------------------------------
Write-Host "`n[2/3] Configuring OpenChamber UI Password (32-character security)..." -ForegroundColor Cyan
$OcPassword = Read-Host "Enter OpenChamber UI Password [leave blank to auto-generate 32-char password]"
if ([string]::IsNullOrEmpty($OcPassword)) {
    $OcPassword = Get-RandomString 32
    Write-Host "Auto-generated secure password: $OcPassword" -ForegroundColor Yellow
}

# Set persistent system environment variable
[Environment]::SetEnvironmentVariable("UI_PASSWORD", $OcPassword, "User")
$env:UI_PASSWORD = $OcPassword
Write-Host "Successfully configured OpenChamber UI_PASSWORD environment variable." -ForegroundColor Green


# -----------------------------------------------------------------------------
# 3. vLLM Auth Proxy Token
# -----------------------------------------------------------------------------
Write-Host "`n[3/3] Configuring vLLM LAN API Token (32-character security)..." -ForegroundColor Cyan
$vLlmEnv = "C:\Users\jeffr\.gemini\antigravity\scratch\SGlang_5060ti\.env"

$vLlmToken = Read-Host "Enter vLLM Auth Token [leave blank to auto-generate 32-char token]"
if ([string]::IsNullOrEmpty($vLlmToken)) {
    $vLlmToken = Get-RandomString 32
    Write-Host "Auto-generated secure token: $vLlmToken" -ForegroundColor Yellow
}

if (-not (Test-Path $vLlmEnv)) {
    New-Item -ItemType File -Path $vLlmEnv -Force | Out-Null
}

$vLlmEnvContent = Get-Content $vLlmEnv
$NewvLlmEnvContent = @()
foreach ($Line in $vLlmEnvContent) {
    if ($Line -match "^VLLM_AUTH_TOKEN=") {
        continue
    }
    $NewvLlmEnvContent += $Line
}
$NewvLlmEnvContent += "VLLM_AUTH_TOKEN=$vLlmToken"
Set-Content -Path $vLlmEnv -Value $NewvLlmEnvContent -Encoding utf8
Write-Host "Successfully configured VLLM_AUTH_TOKEN in vLLM env file." -ForegroundColor Green


# -----------------------------------------------------------------------------
# 4. Restarting Affected Services to Apply Credentials
# -----------------------------------------------------------------------------
Write-Host "`nRestarting services to apply new credentials..." -ForegroundColor Yellow

# Restart vLLM Proxy container
Write-Host "Restarting vLLM Auth Proxy container..." -ForegroundColor Yellow
cmd.exe /c "cd `"C:\Users\jeffr\.gemini\antigravity\scratch\SGlang_5060ti`" && docker compose up -d --force-recreate vllm-auth-proxy"

# Restart Hermes Dashboard background process
Write-Host "Restarting Hermes Web Dashboard server..." -ForegroundColor Yellow
$DashboardProcess = Get-Process | Where-Object {$_.ProcessName -match "python" -and $_.CommandLine -match "dashboard"} -ErrorAction SilentlyContinue
if ($DashboardProcess) {
    $DashboardProcess | Stop-Process -Force
    Write-Host "Stopped old dashboard server." -ForegroundColor Yellow
}

$RunDashboardScript = "C:\Users\jeffr\.geminintigravity\scratch\mcp-rag-outlook\run-hermes-dashboard.ps1"
if (Test-Path $RunDashboardScript) {
    Start-Process powershell.exe -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$RunDashboardScript`"" -WindowStyle Minimized
    Write-Host "Launched Hermes Web Dashboard server with remote access enabled." -ForegroundColor Green
}

Write-Host "`n==========================================================" -ForegroundColor Green
Write-Host "    SECURITY ROTATION COMPLETED! WRITE DOWN CREDENTIALS   " -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Green
Write-Host "Hermes Dashboard: Username: $Username | Password: $Password" -ForegroundColor Cyan
Write-Host "OpenChamber Password: $OcPassword" -ForegroundColor Cyan
Write-Host "vLLM LAN Auth Token: $vLlmToken" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Green
