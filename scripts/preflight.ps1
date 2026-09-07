param(
    [string]$PythonExe = ""
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

Write-Host "Using Python: $PythonExe"
& $PythonExe scripts\project_doctor.py
if ($LASTEXITCODE -ne 0) { throw "Environment check failed." }

& $PythonExe -m py_compile scripts\data_contract.py scripts\run_experiment.py scripts\audit_project.py scripts\result_freeze.py scripts\gatekeeper.py scripts\score_problems.py scripts\benchmark_suite.py scripts\model_benchmarks.py
if ($LASTEXITCODE -ne 0) { throw "Python syntax check failed." }

& $PythonExe -m unittest discover -s tests -v
if ($LASTEXITCODE -ne 0) { throw "Automated tests failed." }

Write-Host "Preflight checks passed."
