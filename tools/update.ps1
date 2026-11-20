# Update.cmd: fetch the latest port and toolkit, then rebuild. Your game
# files, settings.ini, mkb.ini edits and saves are kept.
$ErrorActionPreference = 'Stop'
$Root    = Split-Path -Parent $PSScriptRoot
$Toolkit = Join-Path $Root 'deps\xboxrecomp'
$Log     = Join-Path $Root 'setup.log'
Set-Location $Root
"=== update $(Get-Date -Format s) ===" | Out-File $Log -Append -Encoding utf8

function Say($m)  { Write-Host $m; $m | Out-File $Log -Append -Encoding utf8 }
function Fail($m) { Write-Host ""; Write-Host "Update stopped: $m" -ForegroundColor Red
                    Write-Host "Details are in $Log"; Read-Host "Press Enter to close"; exit 1 }
function Run($what, [scriptblock]$cmd) {
    Say "--> $what"
    $prev = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    $global:LASTEXITCODE = 0
    & $cmd 2>&1 | ForEach-Object { "$_" } | Out-File $Log -Append -Encoding utf8
    $code = $LASTEXITCODE
    $ErrorActionPreference = $prev
    if ($code -ne 0) { Fail "$what failed." }
}

if (-not (Test-Path (Join-Path $Root 'bin\fbos.exe'))) { Fail "the game is not set up yet; run Setup.cmd first." }
if (Get-Process fbos -ErrorAction SilentlyContinue) { Fail "the game is running; close it first." }

$before = (git -C $Toolkit rev-parse HEAD)
Run 'updating the port' { git -C $Root pull --ff-only }
Run 'updating the toolkit' { git -C $Toolkit pull --ff-only }
$after = (git -C $Toolkit rev-parse HEAD)

# A new toolkit can translate the game's code differently: generate it again.
if ($before -ne $after -or -not (Test-Path (Join-Path $Root 'src\game\recomp\gen\recomp_funcs.h'))) {
    $bash = Join-Path (Split-Path (Split-Path (Get-Command git).Source)) 'bin\bash.exe'
    $env:RECOMP = $Toolkit
    Run 'generating C from your game (about 3 minutes)' { & $bash ./regen.sh }
}
Run 'building (several minutes)' { cmake --build build-msvc --config Release }
Say ""
Say "Up to date. Start the game with Play.cmd."
Read-Host "Press Enter to close"
