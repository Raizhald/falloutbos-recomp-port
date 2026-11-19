# Read-only preflight. Does not install tools, extract discs or run the game.
[CmdletBinding()]
param(
    [string]$Python = 'py',
    [string]$CMake = 'cmake'
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Missing = 0

function Report([bool]$Ok, [string]$Name, [string]$Detail) {
    if ($Ok) { Write-Host "[OK] $Name : $Detail" }
    else { Write-Host "[MISSING] $Name : $Detail"; $script:Missing++ }
}

$gitCommand = Get-Command git -ErrorAction SilentlyContinue
Report ([bool]$gitCommand) 'Git' 'required for source checkouts'
if ($gitCommand) {
    $bashPath = Join-Path (Split-Path (Split-Path $gitCommand.Source)) 'bin/bash.exe'
    Report (Test-Path -LiteralPath $bashPath) 'Git Bash' $bashPath
}

$pythonCommand = Get-Command $Python -ErrorAction SilentlyContinue
if ($pythonCommand -and $pythonCommand.Source -match 'WindowsApps[\\/]python') {
    $pythonCommand = $null # Store execution alias is not an installed interpreter.
}
if ($pythonCommand) {
    $pythonArgs = @()
    if ($pythonCommand.Name -ieq 'py.exe') { $pythonArgs = @('-3') }
    & $pythonCommand.Source @pythonArgs -c 'import sys; print(sys.version); sys.exit(0 if sys.version_info >= (3,10) else 1)'
    Report ($LASTEXITCODE -eq 0) 'Python >= 3.10' $pythonCommand.Source
    & $pythonCommand.Source @pythonArgs -c 'import capstone; print(capstone.__version__)'
    Report ($LASTEXITCODE -eq 0) 'Capstone' 'Python disassembler dependency'
} else { Report $false 'Python' 'use -Python with an installed interpreter path' }

$cmakeCommand = Get-Command $CMake -ErrorAction SilentlyContinue
if ($cmakeCommand) {
    $versionOutput = & $cmakeCommand.Source --version
    $cmakeOk = $LASTEXITCODE -eq 0
    $versionMatch = [regex]::Match(($versionOutput -join "`n"), 'cmake version (\d+\.\d+\.\d+)')
    $cmakeOk = $cmakeOk -and $versionMatch.Success
    if ($cmakeOk) { $cmakeOk = [version]$versionMatch.Groups[1].Value -ge [version]'3.20.0' }
    Report $cmakeOk 'CMake >= 3.20' "$($versionMatch.Groups[1].Value) at $($cmakeCommand.Source)"
} else { Report $false 'CMake' 'use -CMake with an installed cmake.exe path' }

$vswherePath = "${env:ProgramFiles(x86)}/Microsoft Visual Studio/Installer/vswhere.exe"
$vcPath = $null
if (Test-Path -LiteralPath $vswherePath) {
    $vcPath = & $vswherePath -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
}
Report ([bool]$vcPath) 'Visual C++ tools' "$vcPath"

$toolkitPath = Join-Path $ProjectRoot 'deps/xboxrecomp'
$toolkitPresent = Test-Path -LiteralPath (Join-Path $toolkitPath 'CMakeLists.txt')
Report $toolkitPresent 'xboxrecomp' $toolkitPath
if ($toolkitPresent -and $gitCommand) {
    $actualRevision = & git -C $toolkitPath rev-parse HEAD
    if ($LASTEXITCODE -eq 0) {
        $expectedRevision = (Get-Content -LiteralPath (Join-Path $ProjectRoot 'config/toolkit-revision.txt') -Raw).Trim()
        Report ($actualRevision -eq $expectedRevision) 'Toolkit baseline revision' "$actualRevision (expected $expectedRevision)"
    } else { Report $false 'Toolkit baseline revision' 'cannot read Git revision' }
}

Report (Test-Path -LiteralPath (Join-Path $ProjectRoot 'game/default.xbe') -PathType Leaf) 'Game data' 'game/default.xbe from your own USA Xbox disc'
Write-Host ""
if ($Missing) { Write-Host "$Missing prerequisite(s) missing or mismatched. No changes made."; exit 1 }
Write-Host 'Preflight passed. Compilation and gameplay still need separate verification.'
exit 0
