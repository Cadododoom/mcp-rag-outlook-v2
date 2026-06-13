# Restore Milvus database volumes from Google Drive (G:)
$Source = "G:\My Drive\MilvusBackup"
$Destination = "C:\Users\jeffr\.gemini\antigravity\scratch\mcp-rag-outlook\volumes"

Write-Host "Starting Milvus database restoration from Google Drive ($Source)..." -ForegroundColor Cyan

if (-not (Test-Path $Source)) {
    Write-Error "Google Drive backup directory not found: $Source. Make sure Google Drive is mounted as G:."
    Exit 1
}

# Create destination directory if it doesn't exist
if (-not (Test-Path $Destination)) {
    New-Item -ItemType Directory -Path $Destination -Force | Out-Null
    Write-Host "Created missing local destination folder: $Destination" -ForegroundColor Yellow
}

# Run Robocopy for fast, multi-threaded incremental mirror copy from G: to local SSD
robocopy $Source $Destination /MIR /MT:8 /FFT /R:3 /W:5 /NP /NDL /NFL

if ($LASTEXITCODE -lt 8) {
    Write-Host "Restoration completed successfully!" -ForegroundColor Green
} else {
    Write-Warning "Restoration completed with warnings (Robocopy Exit Code: $LASTEXITCODE)."
}
