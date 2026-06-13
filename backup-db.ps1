# Backup Milvus database volumes to Google Drive (G:)
$Source = "C:\Users\jeffr\.gemini\antigravity\scratch\mcp-rag-outlook\volumes"
$Destination = "G:\My Drive\MilvusBackup"

Write-Host "Starting Milvus database replication to Google Drive ($Destination)..." -ForegroundColor Cyan

if (-not (Test-Path $Source)) {
    Write-Error "Source directory not found: $Source"
    Exit 1
}

# Run Robocopy for fast, multi-threaded incremental mirror copy
# /MIR mirrors directory tree, /MT:8 uses 8 threads, /FFT uses FAT file times (good for cloud syncs)
robocopy $Source $Destination /MIR /MT:8 /FFT /R:3 /W:5 /NP /NDL /NFL

if ($LASTEXITCODE -lt 8) {
    Write-Host "Backup completed successfully!" -ForegroundColor Green
} else {
    Write-Warning "Backup completed with warnings or files were locked (Robocopy Exit Code: $LASTEXITCODE)."
}
