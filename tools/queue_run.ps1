# Runs one queue job for Fronta.cmd: in its own cmd process (so "set" in a job
# does not leak into the next one) and with a time limit, after which the
# whole process tree -- a hung game included -- is killed.
# The limit is 3600 s unless the job says otherwise in a line "rem timeout=<s>".
param([Parameter(Mandatory)][string]$Job, [int]$Default = 3600)
$limit = $Default
foreach ($line in Get-Content -LiteralPath $Job -TotalCount 20) {
    if ($line -match '^\s*rem\s+timeout=(\d+)') { $limit = [int]$Matches[1] }
}
$p = Start-Process -FilePath $env:ComSpec -ArgumentList '/c', "`"$Job`"" -NoNewWindow -PassThru
if (-not $p.WaitForExit($limit * 1000)) {
    & taskkill.exe /T /F /PID $p.Id | Out-Null
    Write-Output "timeout after $limit s"
    exit 124
}
exit $p.ExitCode
