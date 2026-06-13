# Master AI Workstation Cloud Rebuild & Restore Script
# Restores all codebases, databases, host profiles, and scheduled backup loops from Google Drive (G:)

$BackupRoot = "G:\My Drive\AI_Workstation_Backup"
$ScratchDir = "C:\Users\jeffr\.gemini\antigravity\scratch"
$DbVolumes = "$ScratchDir\mcp-rag-outlook\volumes"

Write-Host "==========================================================" -ForegroundColor Green
Write-Host "       STARTING MASTER AI WORKSTATION CLOUD RESTORE        " -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Green

# 1. Verify Google Drive mount
if (-not (Test-Path "G:\")) {
    Write-Error "Google Drive mount (G:) was not found. Please ensure Google Drive is running and mounted."
    Exit 1
}

# Create base scratch directory if missing
if (-not (Test-Path $ScratchDir)) {
    New-Item -ItemType Directory -Path $ScratchDir -Force | Out-Null
    Write-Host "Created base scratch workspace directory." -ForegroundColor Yellow
}

# 2. Restore Code Repositories
Write-Host "`n[1/7] Restoring clean code repositories from Google Drive..." -ForegroundColor Cyan
$Repos = @("mcp-rag-outlook", "vLLM_5060TI", "Qwen3-TTS-Stack", "vLLM-Container-Manager")

foreach ($Repo in $Repos) {
    $SourcePath = "$BackupRoot\repositories\$Repo"
    $DestPath = "$ScratchDir\$Repo"
    
    if (Test-Path $SourcePath) {
        Write-Host "Restoring $Repo codebase..." -ForegroundColor Yellow
        # Multi-threaded mirroring back to local SSD
        robocopy $SourcePath $DestPath /MIR /MT:8 /FFT /R:3 /W:5 /NP /NDL /NFL
    } else {
        Write-Warning "Backup for repository $Repo not found on G Drive."
    }
}

# 3. Restore Database Volumes
Write-Host "`n[2/7] Restoring Milvus database volumes..." -ForegroundColor Cyan
$DbBackupPath = "$BackupRoot\database_volumes"
if (Test-Path $DbBackupPath) {
    New-Item -ItemType Directory -Path $DbVolumes -Force | Out-Null
    robocopy $DbBackupPath $DbVolumes /MIR /MT:8 /FFT /R:3 /W:5 /NP /NDL /NFL
    Write-Host "Milvus standalone database volumes restored successfully." -ForegroundColor Green
} else {
    Write-Warning "Database backup volumes not found on G Drive."
}

# 4. Restore Active Host Configs
Write-Host "`n[3/7] Restoring user configuration profiles..." -ForegroundColor Cyan
$OpenCodeConfigDir = "$Home\.config\opencode"
$HermesConfigDir = "$Home\.hermes"

if (-not (Test-Path $OpenCodeConfigDir)) {
    New-Item -ItemType Directory -Path $OpenCodeConfigDir -Force | Out-Null
}
if (-not (Test-Path $HermesConfigDir)) {
    New-Item -ItemType Directory -Path $HermesConfigDir -Force | Out-Null
}

$OpenCodeBackup = "$BackupRoot\host_configs\openCode.json"
$HermesBackup = "$BackupRoot\host_configs\hermes_config.yaml"

if (Test-Path $OpenCodeBackup) {
    Copy-Item $OpenCodeBackup "$OpenCodeConfigDir\opencode.json" -Force
    Write-Host "Enforced OpenCode configuration profile." -ForegroundColor Green
}
if (Test-Path $HermesBackup) {
    Copy-Item $HermesBackup "$HermesConfigDir\config.yaml" -Force
    Write-Host "Enforced Hermes Agent configuration profile." -ForegroundColor Green
}

# 5. Verify Embedding GGUF Model
Write-Host "`n[4/7] Verifying embedding model GGUF file..." -ForegroundColor Cyan
$ModelDest = "$ScratchDir\mcp-rag-outlook\models\nomic-embed-text-v1.5.Q8_0.gguf"
if (-not (Test-Path $ModelDest)) {
    $CachedModel = "C:\Users\jeffr\.lmstudio\models\nomic-ai\nomic-embed-text-v1.5-GGUF\nomic-embed-text-v1.5.Q8_0.gguf"
    if (Test-Path $CachedModel) {
        Write-Host "Found cached embedding model in LM Studio. Copying..." -ForegroundColor Yellow
        New-Item -ItemType Directory -Path (Split-Path $ModelDest) -Force | Out-Null
        Copy-Item $CachedModel $ModelDest -Force
        Write-Host "Embedding model restored successfully." -ForegroundColor Green
    } else {
        Write-Warning "Embedding model not found in repo or local cache. Please download nomic-embed-text-v1.5.Q8_0.gguf to $ScratchDir\mcp-rag-outlook\models\"
    }
} else {
    Write-Host "Embedding model verified present." -ForegroundColor Green
}

# 6. Install Node.js Dependencies for MCP
Write-Host "`n[5/7] Re-installing Node.js package dependencies..." -ForegroundColor Cyan
$McpDir = "$ScratchDir\mcp-rag-outlook\mcp_server"
if (Test-Path $McpDir) {
    cmd.exe /c "cd `"$McpDir`" && npm install"
    Write-Host "Node.js packages installed successfully." -ForegroundColor Green
}

# 7. Start Docker Stacks
Write-Host "`n[6/7] Starting Docker container stacks..." -ForegroundColor Cyan
Write-Host "Launching RAG database, Kokoro TTS, and isolated embedding server..." -ForegroundColor Yellow
cmd.exe /c "cd `"$ScratchDir\mcp-rag-outlook`" && docker compose up -d"

Write-Host "Launching vLLM GPU inference server and auth proxy..." -ForegroundColor Yellow
cmd.exe /c "cd `"$ScratchDir\vLLM_5060TI`" && docker compose up -d"

# 8. Register Background Auto-Backup Scheduler Task
Write-Host "`n[7/7] Registering 15-minute scheduled cloud backup task..." -ForegroundColor Cyan
$Action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-WindowStyle Hidden -Command & '$ScratchDir\mcp-rag-outlook\backup-workstation.ps1'"
$Trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes 15)
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
Register-ScheduledTask -TaskName "MilvusSyncGDrive" -Action $Action -Trigger $Trigger -Settings $Settings -Force | Out-Null
Write-Host "Registered background backup scheduler task 'MilvusSyncGDrive'." -ForegroundColor Green

Write-Host "`n==========================================================" -ForegroundColor Green
Write-Host "       AI WORKSTATION RESTORE COMPLETED SUCCESSFULLY!       " -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Green
