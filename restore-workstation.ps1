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
Write-Host "`n[1/8] Restoring clean code repositories from Google Drive..." -ForegroundColor Cyan
$Repos = @("mcp-rag-outlook", "SGlang_5060ti", "Qwen3-TTS-Stack", "vLLM-Container-Manager", "Hermes-Swarm-Director")

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
Write-Host "`n[2/8] Restoring Milvus database volumes..." -ForegroundColor Cyan
$DbBackupPath = "$BackupRoot\database_volumes"
if (Test-Path $DbBackupPath) {
    New-Item -ItemType Directory -Path $DbVolumes -Force | Out-Null
    robocopy $DbBackupPath $DbVolumes /MIR /MT:8 /FFT /R:3 /W:5 /NP /NDL /NFL
    Write-Host "Milvus standalone database volumes restored successfully." -ForegroundColor Green
} else {
    Write-Warning "Database backup volumes not found on G Drive."
}

# 4. Restore Active Host Configs
Write-Host "`n[3/8] Restoring user configuration profiles..." -ForegroundColor Cyan
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

# 4b. Restore Hermes Agent AppData (databases, profiles, sessions, memories)
Write-Host "`nRestoring Hermes Agent active AppData (state, profiles, sessions)..." -ForegroundColor Cyan
$HermesAppDir = "C:\Users\jeffr\AppData\Local\hermes"
$HermesAppSource = "$BackupRoot\hermes_app_data"

if (Test-Path $HermesAppSource) {
    if (-not (Test-Path $HermesAppDir)) {
        New-Item -ItemType Directory -Path $HermesAppDir -Force | Out-Null
        Write-Host "Created missing local Hermes folder: $HermesAppDir" -ForegroundColor Yellow
    }
    
    # Restore directories
    $HermesFolders = @("sessions", "memories", "state-snapshots")
    foreach ($Folder in $HermesFolders) {
        if (Test-Path "$HermesAppSource\$Folder") {
            robocopy "$HermesAppSource\$Folder" "$HermesAppDir\$Folder" /MIR /MT:8 /FFT /R:3 /W:5 /NP /NDL /NFL
        }
    }
    
    # Restore custom profiles and skills (unzip)
    $HermesZips = @("profiles", "skills")
    foreach ($Folder in $HermesZips) {
        $ZipPath = "$HermesAppSource\$Folder.zip"
        if (Test-Path $ZipPath) {
            $DestFolder = "$HermesAppDir\$Folder"
            if (-not (Test-Path $DestFolder)) {
                New-Item -ItemType Directory -Path $DestFolder -Force | Out-Null
            }
            Write-Host "Unzipping $ZipPath to $DestFolder..." -ForegroundColor Yellow
            Expand-Archive -Path $ZipPath -DestinationPath $DestFolder -Force
        }
    }
    
    # Restore database files and config parameters
    $HermesFiles = @("state.db", "config.yaml", "auth.json", ".env", "SOUL.md", "hermes-setup.exe")
    foreach ($File in $HermesFiles) {
        if (Test-Path "$HermesAppSource\$File") {
            Copy-Item "$HermesAppSource\$File" "$HermesAppDir\$File" -Force
        }
    }
    Write-Host "Hermes Agent active AppData restored successfully." -ForegroundColor Green

    # Install Web Dashboard dependencies in the virtual environment
    $VenvPip = "$HermesAppDir\hermes-agent\venv\Scripts\pip.exe"
    if (Test-Path $VenvPip) {
        Write-Host "Installing Web Dashboard and terminal extras..." -ForegroundColor Yellow
        Start-Process $VenvPip -ArgumentList "install 'hermes-agent[web,pty]'" -Wait -NoNewWindow
    }

    # Automatically install/update Hermes Desktop App
    $DesktopInstaller = "$HermesAppDir\hermes-setup.exe"
    if (Test-Path $DesktopInstaller) {
        Write-Host "Installing Hermes Desktop application silently..." -ForegroundColor Yellow
        Start-Process $DesktopInstaller -ArgumentList "/S" -Wait
        Write-Host "Hermes Desktop application installed successfully." -ForegroundColor Green
    }
} else {
    Write-Warning "Hermes active AppData backup not found on G Drive."
}


# 5. Verify Embedding GGUF Model
Write-Host "`n[4/8] Verifying embedding model GGUF file..." -ForegroundColor Cyan
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
Write-Host "`n[5/8] Re-installing Node.js package dependencies..." -ForegroundColor Cyan
$McpDir = "$ScratchDir\mcp-rag-outlook\mcp_server"
if (Test-Path $McpDir) {
    cmd.exe /c "cd `"$McpDir`" && npm install"
    Write-Host "Node.js packages installed successfully." -ForegroundColor Green
}

# 7. Start Docker Stacks & Native Vulkan Server
Write-Host "`n[6/8] Starting Docker container stacks..." -ForegroundColor Cyan
Write-Host "Launching RAG database and Kokoro TTS services..." -ForegroundColor Yellow
cmd.exe /c "cd `"$ScratchDir\mcp-rag-outlook`" && docker compose up -d"

Write-Host "Launching vLLM GPU inference server and auth proxy..." -ForegroundColor Yellow
cmd.exe /c "cd `"$ScratchDir\SGlang_5060ti`" && docker compose up -d"

Write-Host "Launching Qwen3-TTS streaming and web servers on AMD GPU..." -ForegroundColor Yellow
cmd.exe /c "cd `"$ScratchDir\Qwen3-TTS-Stack`" && docker compose up -d"


# 7b. Set Up and Launch Native Vulkan Embedding Server on AMD GPU
Write-Host "`n[7/8] Setting up and starting native Vulkan embedding server..." -ForegroundColor Cyan
$SetupVulkanScript = "$ScratchDir\mcp-rag-outlook\setup-vulkan-embedding.ps1"
$RunVulkanScript = "$ScratchDir\mcp-rag-outlook\run-vulkan-embedding.ps1"

if (Test-Path $SetupVulkanScript) {
    Write-Host "Downloading Vulkan binaries and auto-configuring GPU indices..." -ForegroundColor Yellow
    powershell.exe -ExecutionPolicy Bypass -File $SetupVulkanScript
    
    if (Test-Path $RunVulkanScript) {
        Write-Host "Launching Vulkan embedding server in a minimized window..." -ForegroundColor Green
        Start-Process powershell.exe -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$RunVulkanScript`"" -WindowStyle Minimized
    }
} else {
    Write-Warning "Vulkan setup script not found at $SetupVulkanScript"
}

# 7c. Set Up and Launch Hermes Web Dashboard Server
Write-Host "`n[7c] Setting up and starting Hermes Web Dashboard server..." -ForegroundColor Cyan
$RunDashboardScript = "$ScratchDir\mcp-rag-outlook\run-hermes-dashboard.ps1"

if (-not (Test-Path $RunDashboardScript)) {
    $DashboardContent = @"
# Start Hermes Web Dashboard bound to all interfaces
Set-Location "C:\Users\jeffr\AppData\Local\hermes\hermes-agent"
& "C:\Users\jeffr\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe" -m hermes_cli.main dashboard --host 0.0.0.0 --port 9119 --no-open
"@
    Out-File -InputObject $DashboardContent -FilePath $RunDashboardScript -Encoding utf8
    Write-Host "Created run-hermes-dashboard.ps1 script." -ForegroundColor Yellow
}

Write-Host "Launching Hermes Web Dashboard server in a minimized window..." -ForegroundColor Green
Start-Process powershell.exe -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$RunDashboardScript`"" -WindowStyle Minimized

# 7d. Launch Hermes Swarm Director Orchestration Suite
Write-Host "`n[7d] Starting Hermes Swarm Director Orchestration suite..." -ForegroundColor Cyan
$RunDirectorScript = "$ScratchDir\mcp-rag-outlook\run-hermes-swarm-director.ps1"
if (Test-Path $RunDirectorScript) {
    Write-Host "Launching Hermes Swarm Director backend services in a minimized window..." -ForegroundColor Green
    Start-Process powershell.exe -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$RunDirectorScript`"" -WindowStyle Minimized
} else {
    Write-Warning "Hermes Swarm Director launch script not found at $RunDirectorScript"
}

# 8. Register Background Auto-Backup Scheduler Task
Write-Host "`n[8/8] Registering 15-minute scheduled cloud backup task..." -ForegroundColor Cyan
$Action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-WindowStyle Hidden -Command & '$ScratchDir\mcp-rag-outlook\backup-workstation.ps1'"
$Trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes 15)
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
Register-ScheduledTask -TaskName "MilvusSyncGDrive" -Action $Action -Trigger $Trigger -Settings $Settings -Force | Out-Null
Write-Host "Registered background backup scheduler task 'MilvusSyncGDrive'." -ForegroundColor Green

# 9. Configure GPU WDDM TDR Registry Delays (AMD RX 5700 Vulkan TTS Support)
Write-Host "`n[9/9] Configuring GPU WDDM TDR registry delays..." -ForegroundColor Cyan
$RegistryPath = "HKLM:\SYSTEM\CurrentControlSet\Control\GraphicsDrivers"
if (Test-Path $RegistryPath) {
    $CurrentTdr = Get-ItemProperty -Path $RegistryPath -Name "TdrDelay" -ErrorAction SilentlyContinue
    $CurrentTdrDdi = Get-ItemProperty -Path $RegistryPath -Name "TdrDdiDelay" -ErrorAction SilentlyContinue
    
    $NeedsRestart = $false
    
    if ($null -eq $CurrentTdr -or $CurrentTdr.TdrDelay -ne 30) {
        Set-ItemProperty -Path $RegistryPath -Name "TdrDelay" -Value 30 -Type DWord -Force | Out-Null
        Write-Host "Set TdrDelay registry key to 30." -ForegroundColor Green
        $NeedsRestart = $true
    }
    if ($null -eq $CurrentTdrDdi -or $CurrentTdrDdi.TdrDdiDelay -ne 30) {
        Set-ItemProperty -Path $RegistryPath -Name "TdrDdiDelay" -Value 30 -Type DWord -Force | Out-Null
        Write-Host "Set TdrDdiDelay registry key to 30." -ForegroundColor Green
        $NeedsRestart = $true
    }
    
    if ($NeedsRestart) {
        Write-Host "`n[WARNING] GPU TDR registry modifications were applied to support AMD Vulkan TTS weights processing." -ForegroundColor Yellow
        Write-Host "A system restart is required for these registry changes to take effect." -ForegroundColor Yellow
        
        $Response = Read-Host "Would you like to restart the workstation now? (y/n)"
        if ($Response -eq "y" -or $Response -eq "yes") {
            Write-Host "Restarting workstation in 5 seconds..." -ForegroundColor Red
            Start-Sleep -Seconds 5
            Restart-Computer -Force
        } else {
            Write-Host "Please remember to restart the machine manually later before using the AMD GPU for TTS." -ForegroundColor Yellow
        }
    } else {
        Write-Host "GPU WDDM TDR registry values already correctly configured (TdrDelay = 30)." -ForegroundColor Green
    }
}

Write-Host "`n==========================================================" -ForegroundColor Green
Write-Host "       AI WORKSTATION RESTORE COMPLETED SUCCESSFULLY!       " -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Green
Write-Host "`n[TIP] Run 'powershell -File C:\Users\jeffr\.gemini\antigravity\scratch\mcp-rag-outlook\configure-workstation-security.ps1' to rotate/set fresh passwords for remote access." -ForegroundColor Cyan
