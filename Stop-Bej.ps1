$ErrorActionPreference = 'Stop'
$bejPidPath = Join-Path $PSScriptRoot '.bej-local\runtime.pid'
if (-not (Test-Path -LiteralPath $bejPidPath)) { Write-Output 'No Bej runtime is recorded.'; return }
$bejProcessId = [int](Get-Content -LiteralPath $bejPidPath -Raw)
$bejProcess = Get-CimInstance Win32_Process -Filter "ProcessId = $bejProcessId"
$bejServerPath = Join-Path $PSScriptRoot 'bej-companion\server.py'
if (-not $bejProcess) { Write-Output 'The recorded Bej process has already stopped.'; return }
if ($bejProcess.Name -ne 'python.exe' -or -not $bejProcess.CommandLine.Contains($bejServerPath)) {
  throw 'The recorded process does not match this Bej service. No process was stopped.'
}
Stop-Process -Id $bejProcessId
Remove-Item -LiteralPath $bejPidPath
Write-Output 'Stopped this Bej local service.'
