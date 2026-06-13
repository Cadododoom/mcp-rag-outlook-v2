# Master AI Workstation Rebuild & Setup Script
# Run this on a fresh OS checkpoint to restore everything.

$RepoDir = "C:/Users/jeffr/.gemini/antigravity/scratch/mcp-rag-outlook"
$VllmDir = "C:/Users/jeffr/.gemini/antigravity/scratch/vLLM_5060TI"

Write-Host "==========================================================" -ForegroundColor Green
Write-Host "       AI WORKSTATION MASTER REBUILD & RESTORE STACK       " -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Green

# 1. Restore database from Google Drive
Write-Host "`n[1/6] Restoring Milvus database from Google Drive (G:)..." -ForegroundColor Cyan
& "$RepoDir\restore-db.ps1"

# 2. Check and copy GGUF embedding model
Write-Host "`n[2/6] Checking GGUF embedding model..." -ForegroundColor Cyan
$ModelDest = "$RepoDir\models\nomic-embed-text-v1.5.Q8_0.gguf"
if (-not (Test-Path $ModelDest)) {
    $CachedModel = "C:\Users\jeffr\.lmstudio\models\nomic-ai\nomic-embed-text-v1.5-GGUF\nomic-embed-text-v1.5.Q8_0.gguf"
    if (Test-Path $CachedModel) {
        Write-Host "Found cached embedding model, copying to repository..." -ForegroundColor Yellow
        New-Item -ItemType Directory -Path "$RepoDir\models" -Force | Out-Null
        Copy-Item $CachedModel $ModelDest -Force
        Write-Host "Embedding model copied successfully." -ForegroundColor Green
    } else {
        Write-Warning "Embedding model not found in repo or cache. Please download nomic-embed-text-v1.5.Q8_0.gguf to $RepoDir\models\"
    }
} else {
    Write-Host "Embedding model verified present in repository." -ForegroundColor Green
}

# 3. Install NPM dependencies for MCP launchers
Write-Host "`n[3/6] Installing Node.js dependencies for MCP servers..." -ForegroundColor Cyan
if (Test-Path "$RepoDir\mcp_server") {
    cmd.exe /c "cd `"$RepoDir\mcp_server`" && npm install"
}

# 4. Configure OpenCode Profile
Write-Host "`n[4/6] Registering RAG configurations in OpenCode..." -ForegroundColor Cyan
$OpenCodeConfig = "$Home\.config\opencode\opencode.json"
$OpenCodeConfigDir = Split-Path $OpenCodeConfig -Parent
if (-not (Test-Path $OpenCodeConfigDir)) {
    New-Item -ItemType Directory -Path $OpenCodeConfigDir -Force | Out-Null
}
if (Test-Path $OpenCodeConfig) {
    Copy-Item $OpenCodeConfig "$OpenCodeConfig.bak" -Force
    Write-Host "Backed up existing OpenCode configuration to opencode.json.bak" -ForegroundColor Yellow
}
Copy-Item "$RepoDir\config\opencode_virtual_ctx.json" $OpenCodeConfig -Force
Write-Host "Enforced 22k Virtual Context profile in OpenCode." -ForegroundColor Green

# 5. Configure Hermes Agent Config
Write-Host "`n[5/6] Registering MCP servers in Hermes Agent..." -ForegroundColor Cyan
$HermesConfig = "$Home\.hermes\config.yaml"
$HermesConfigDir = Split-Path $HermesConfig -Parent
if (-not (Test-Path $HermesConfigDir)) {
    New-Item -ItemType Directory -Path $HermesConfigDir -Force | Out-Null
}
if (Test-Path $HermesConfig) {
    Copy-Item $HermesConfig "$HermesConfig.bak" -Force
    Write-Host "Backed up existing Hermes configuration to config.yaml.bak" -ForegroundColor Yellow
    $Content = Get-Content $HermesConfig -Raw
    if ($Content -notmatch "mcp_servers:") {
        $McpBlock = @"

mcp_servers:
  code-indexer:
    command: "node"
    args: ["$RepoDir/mcp_server/launch-mcp.js"]
  memory-manager:
    command: "node"
    args: ["$RepoDir/mcp_server/launch-memory-mcp.js"]
"@
        Add-Content -Path $HermesConfig -Value $McpBlock
        Write-Host "Registered local MCP servers in Hermes config.yaml" -ForegroundColor Green
    } else {
        Write-Host "MCP block already exists in Hermes config.yaml. Please verify paths manually if needed." -ForegroundColor Yellow
    }
} else {
    # Write a new config
    $NewConfig = @"
provider: custom
model:
  default: nvidia/Qwen3.6-35B-A3B-NVFP4
base_url: http://localhost:8000/v1
api_key: none
generation:
  temperature: 0.6
  max_tokens: 4096
  top_p: 0.95
  top_k: 20
  presence_penalty: 0.0
  repetition_penalty: 1.0
  min_p: 0.0

mcp_servers:
  code-indexer:
    command: "node"
    args: ["$RepoDir/mcp_server/launch-mcp.js"]
  memory-manager:
    command: "node"
    args: ["$RepoDir/mcp_server/launch-memory-mcp.js"]
"@
    Set-Content -Path $HermesConfig -Value $NewConfig
    Write-Host "Created new Hermes config.yaml with local MCP servers." -ForegroundColor Green
}

# 6. Start Docker Stacks
Write-Host "`n[6/6] Launching Docker stacks..." -ForegroundColor Cyan
Write-Host "Starting RAG and embedding containers..." -ForegroundColor Yellow
cmd.exe /c "cd `"$RepoDir`" && docker compose up -d"
Write-Host "Starting vLLM and proxy containers..." -ForegroundColor Yellow
cmd.exe /c "cd `"$VllmDir`" && docker compose up -d"

# 7. Register 15-Minute Sync Task Scheduler
Write-Host "`nRegistering 15-minute background database sync task..." -ForegroundColor Cyan
$Action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-WindowStyle Hidden -Command & '$RepoDir\backup-db.ps1'"
$Trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes 15)
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
Register-ScheduledTask -TaskName "MilvusSyncGDrive" -Action $Action -Trigger $Trigger -Settings $Settings -Force | Out-Null
Write-Host "Registered background sync task 'MilvusSyncGDrive' in Windows Task Scheduler." -ForegroundColor Green

Write-Host "`n==========================================================" -ForegroundColor Green
Write-Host "AI WORKSTATION DEPLOYED AND RESTORED SUCCESSFULLY!" -ForegroundColor Green
Write-Host "OpenCode and Hermes Agent have been updated and are active." -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Green
