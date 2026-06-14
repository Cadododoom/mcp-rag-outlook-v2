# Master AI Workstation Cloud Backup Script
# Synchronizes all code repositories, database volumes, and active config files to Google Drive (G:)

$BackupRoot = "G:\My Drive\AI_Workstation_Backup"
$ScratchDir = "C:\Users\jeffr\.gemini\antigravity\scratch"
$DbVolumes = "$ScratchDir\mcp-rag-outlook\volumes"

Write-Host "==========================================================" -ForegroundColor Green
Write-Host "       STARTING MASTER AI WORKSTATION CLOUD BACKUP       " -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Green

# 1. Verify Google Drive mount
if (-not (Test-Path "G:\")) {
    Write-Error "Google Drive mount (G:) was not found. Please ensure Google Drive is running and mounted."
    Exit 1
}

# Create backup directories if they don't exist
New-Item -ItemType Directory -Path "$BackupRoot\repositories" -Force | Out-Null
New-Item -ItemType Directory -Path "$BackupRoot\database_volumes" -Force | Out-Null
New-Item -ItemType Directory -Path "$BackupRoot\host_configs" -Force | Out-Null

# 2. Backup Database Volumes
Write-Host "`n[1/3] Mirroring Milvus database volumes..." -ForegroundColor Cyan
if (Test-Path $DbVolumes) {
    robocopy $DbVolumes "$BackupRoot\database_volumes" /MIR /MT:8 /FFT /R:3 /W:5 /NP /NDL /NFL
} else {
    Write-Warning "Local database volumes not found at $DbVolumes. Skipping volume backup."
}

# 3. Backup Repositories (with exclusions)
Write-Host "`n[2/3] Mirroring code repositories (excluding caches & node_modules)..." -ForegroundColor Cyan
$Repos = @("mcp-rag-outlook", "vLLM_5060TI", "Qwen3-TTS-Stack", "vLLM-Container-Manager", "Hermes-Swarm-Director")

foreach ($Repo in $Repos) {
    $SourcePath = "$ScratchDir\$Repo"
    $DestPath = "$BackupRoot\repositories\$Repo"
    
    if (Test-Path $SourcePath) {
        Write-Host "Backing up $Repo..." -ForegroundColor Yellow
        
        # Configure Robocopy parameters with exclusions:
        # Excludes: node_modules, huggingface-cache, vllm-cache, hf-cache, local database volumes
        $ExcludeDirs = @("node_modules", "huggingface-cache", "vllm-cache", "hf-cache", "volumes", "venv", ".venv")
        
        robocopy $SourcePath $DestPath /MIR /MT:8 /FFT /R:3 /W:5 /NP /NDL /NFL /XD $ExcludeDirs
    } else {
        Write-Warning "Repository $Repo not found locally. Skipping."
    }
}

# 4. Backup Active Host Configs
Write-Host "`n[3/3] Backing up host configuration profiles..." -ForegroundColor Cyan
$OpenCodeConfig = "$Home\.config\opencode\opencode.json"
$HermesConfig = "$Home\.hermes\config.yaml"

if (Test-Path $OpenCodeConfig) {
    Copy-Item $OpenCodeConfig "$BackupRoot\host_configs\opencode.json" -Force
    Write-Host "Saved OpenCode configuration profile." -ForegroundColor Green
}
if (Test-Path $HermesConfig) {
    Copy-Item $HermesConfig "$BackupRoot\host_configs\hermes_config.yaml" -Force
    Write-Host "Saved Hermes Agent configuration profile." -ForegroundColor Green
}

# 5. Backup Hermes Agent AppData (databases, profiles, sessions, memories)
Write-Host "`n[4/4] Backing up Hermes Agent active AppData (state, profiles, sessions)..." -ForegroundColor Cyan
$HermesAppDir = "C:\Users\jeffr\AppData\Local\hermes"
$HermesAppDest = "$BackupRoot\hermes_app_data"

if (Test-Path $HermesAppDir) {
    New-Item -ItemType Directory -Path $HermesAppDest -Force | Out-Null
    
    # Mirror standard active state/profile directories (excluding profiles and skills since they are zipped)
    $HermesFolders = @("sessions", "memories", "state-snapshots")
    foreach ($Folder in $HermesFolders) {
        if (Test-Path "$HermesAppDir\$Folder") {
            robocopy "$HermesAppDir\$Folder" "$HermesAppDest\$Folder" /MIR /MT:8 /FFT /R:3 /W:5 /NP /NDL /NFL
        }
    }
    
    # Backup custom profiles and skills by zipping them (massive reduction in file count, avoids cloud sync locks)
    $HermesZips = @("profiles", "skills")
    foreach ($Folder in $HermesZips) {
        $SrcDir = "$HermesAppDir\$Folder"
        $DestZip = "$HermesAppDest\$Folder.zip"
        $TempZip = "$env:TEMP\$Folder.zip"
        if (Test-Path $SrcDir) {
            Write-Host "Zipping $Folder to $DestZip..." -ForegroundColor Yellow
            if (Test-Path $TempZip) {
                Remove-Item $TempZip -Force
            }
            Compress-Archive -Path "$SrcDir\*" -DestinationPath $TempZip -Force
            if (Test-Path $DestZip) {
                try {
                    Remove-Item $DestZip -Force
                } catch {
                    Write-Warning "File locked: $DestZip. Retrying in 2 seconds..."
                    Start-Sleep -Seconds 2
                    Remove-Item $DestZip -Force
                }
            }
            Copy-Item $TempZip $DestZip -Force
            Remove-Item $TempZip -Force
        }
    }
    
    # Copy database files and config parameters
    $HermesFiles = @("state.db", "config.yaml", "auth.json", ".env", "SOUL.md", "hermes-setup.exe")
    foreach ($File in $HermesFiles) {
        if (Test-Path "$HermesAppDir\$File") {
            Copy-Item "$HermesAppDir\$File" "$HermesAppDest\$File" -Force
        }
    }
    Write-Host "Hermes Agent active AppData backed up successfully." -ForegroundColor Green
} else {
    Write-Warning "Hermes AppData folder not found at $HermesAppDir."
}

# 6. Backup Hermes Swarm Director active database and environment config
Write-Host "`n[5/5] Backing up Hermes Swarm Director active databases..." -ForegroundColor Cyan
$SwarmDirectorLocal = "$ScratchDir\Hermes-Swarm-Director"
$SwarmDirectorDest = "$BackupRoot\hermes_swarm_director_backup"

if (Test-Path $SwarmDirectorLocal) {
    New-Item -ItemType Directory -Path $SwarmDirectorDest -Force | Out-Null
    if (Test-Path "$SwarmDirectorLocal\director.db") {
        # Safe file copy since it's local
        Copy-Item "$SwarmDirectorLocal\director.db" "$SwarmDirectorDest\director.db" -Force
        Write-Host "Backed up Hermes Swarm Director database (director.db)." -ForegroundColor Green
    }
    if (Test-Path "$SwarmDirectorLocal\.env") {
        Copy-Item "$SwarmDirectorLocal\.env" "$SwarmDirectorDest\.env" -Force
        Write-Host "Backed up Hermes Swarm Director configuration (.env)." -ForegroundColor Green
    }
} else {
    Write-Warning "Hermes Swarm Director workspace not found at $SwarmDirectorLocal."
}

# Copy the master restore script directly to the backup root so it is easily accessible on a fresh OS
Copy-Item "$ScratchDir\mcp-rag-outlook\restore-workstation.ps1" "$BackupRoot\restore-workstation.ps1" -Force

Write-Host "`n==========================================================" -ForegroundColor Green
Write-Host "        MASTER WORKSTATION BACKUP COMPLETED SUCCESSFULLY!  " -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Green

