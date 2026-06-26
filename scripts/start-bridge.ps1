param(
    [string]$ConfigPath = ".\config.json",
    [string]$PythonPath = ""
)

function Resolve-Python {
    param([string]$RequestedPath)

    if ($RequestedPath -and (Test-Path $RequestedPath)) {
        return (Resolve-Path $RequestedPath).Path
    }

    $commands = @(
        "python",
        "py"
    )

    foreach ($command in $commands) {
        $resolved = Get-Command $command -ErrorAction SilentlyContinue
        if ($resolved) {
            if ($command -eq "py") {
                return "py -3"
            }
            return $resolved.Source
        }
    }

    $bundled = Join-Path $HOME ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
    if (Test-Path $bundled) {
        return $bundled
    }

    throw "No Python runtime found. Install Python 3 or pass -PythonPath."
}

$python = Resolve-Python -RequestedPath $PythonPath
$script = Join-Path $PSScriptRoot "..\bridge\airlabs_bridge.py"

if ($python -eq "py -3") {
    py -3 $script --config $ConfigPath
} else {
    & $python $script --config $ConfigPath
}
