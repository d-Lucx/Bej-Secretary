param([switch]$NoBrowser)
$ErrorActionPreference = 'Stop'
$bejRoot = $PSScriptRoot
$bejPython = Join-Path $bejRoot '.bej-local\venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $bejPython)) { throw 'Local Python environment missing. See README.md setup steps.' }
if (-not (Test-Path -LiteralPath (Join-Path $bejRoot 'dist-bej\bej.html'))) { throw 'Build the Bej UI first: npm run build:bej' }
$bejArgs = @((Join-Path $bejRoot 'bej-companion\server.py'))
if ($NoBrowser) { $bejArgs += '--no-open' }
& $bejPython @bejArgs
