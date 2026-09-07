param(
    [string]$PythonExe = "",
    [string[]]$ForbiddenTerms = @()
)

$ErrorActionPreference = "Stop"

if (-not $PythonExe) {
    $workspacePython = Join-Path (Resolve-Path ".") ".venv\Scripts\python.exe"
    if (Test-Path -LiteralPath $workspacePython) {
        $PythonExe = $workspacePython
    }
    else {
        $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
        if ($pythonCommand) {
            $PythonExe = $pythonCommand.Source
        }
        else {
            $codexPython = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
            if (Test-Path -LiteralPath $codexPython) {
                $PythonExe = $codexPython
            }
        }
    }
}

if (-not $PythonExe -or -not (Test-Path -LiteralPath $PythonExe)) {
    throw "Python was not found. Pass -PythonExe with the full path to python.exe."
}

& $PythonExe scripts\data_contract.py check
if ($LASTEXITCODE -ne 0) { throw "Data contract check failed." }

& $PythonExe scripts\result_freeze.py check
if ($LASTEXITCODE -ne 0) { throw "Frozen result check failed." }

$auditArguments = @("scripts\audit_project.py")
foreach ($term in $ForbiddenTerms) {
    $auditArguments += "--forbidden"
    $auditArguments += $term
}
& $PythonExe @auditArguments
if ($LASTEXITCODE -ne 0) { throw "Project audit failed." }

& .\scripts\check_submission.ps1 -ForbiddenTerms $ForbiddenTerms
if ($LASTEXITCODE -ne 0) { throw "Submission check failed." }

Write-Host "Final automated checks passed. Review state/audit_report.json, then pass G6."
