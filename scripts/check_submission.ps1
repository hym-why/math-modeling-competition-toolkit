param(
    [string]$SubmissionDir = "submission",
    [string[]]$ForbiddenTerms = @()
)

$ErrorActionPreference = "Stop"
$limitBytes = 20MB
$root = Resolve-Path "."
$dir = Join-Path $root $SubmissionDir

Write-Host "Checking submission directory: $dir"

if (-not (Test-Path $dir)) {
    Write-Error "Missing submission directory: $SubmissionDir"
}

$files = Get-ChildItem -Path $dir -File
if ($files.Count -eq 0) {
    Write-Warning "No files found in $SubmissionDir yet."
}

foreach ($file in $files) {
    if ($file.Length -gt $limitBytes) {
        Write-Error "$($file.Name) is larger than 20MB."
    }

    foreach ($term in $ForbiddenTerms) {
        if ($file.Name -like "*$term*") {
            Write-Error "$($file.Name) contains forbidden identity term: $term"
        }
    }
}

$paper = $files | Where-Object { $_.Extension -in ".pdf", ".doc", ".docx" }
$support = $files | Where-Object { $_.Extension -in ".zip", ".rar" }

if (-not $paper) {
    Write-Warning "No paper file (.pdf/.doc/.docx) found."
}

if (-not $support) {
    Write-Warning "No supporting material archive (.zip/.rar) found."
}

$freezePath = Join-Path $root "state\frozen_results.json"
if (-not (Test-Path $freezePath)) {
    Write-Warning "No frozen result manifest found. Run: python scripts/result_freeze.py freeze"
}
else {
    $manifest = Get-Content -Raw -Encoding UTF8 $freezePath | ConvertFrom-Json
    $outputsDir = Join-Path $root $manifest.outputs_dir
    foreach ($item in $manifest.files) {
        $resultPath = Join-Path $outputsDir $item.path
        if (-not (Test-Path -LiteralPath $resultPath)) {
            Write-Error "Frozen result is missing: $($item.path)"
        }
        $actualHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $resultPath).Hash.ToLowerInvariant()
        if ($actualHash -ne $item.sha256) {
            Write-Error "Frozen result changed: $($item.path)"
        }
    }
    Write-Host "Frozen result hashes match the manifest."
}

Write-Host "Basic submission check finished."
Write-Host "Manual checks still required: anonymity inside files, paper/support consistency, references, AI declaration, and runnable code."
