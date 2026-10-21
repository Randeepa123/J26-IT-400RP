<# stop_dashboard.ps1 - stop the Grafana container, the API and the optional daily runner started by start_dashboard.ps1.
   (Docker Desktop itself is left running; close it from its tray icon if you want.) #>
$root = Split-Path -Parent $PSScriptRoot
$run  = Join-Path $root 'grafana\runtime'
try { & docker rm -f kukule-grafana 2>$null | Out-Null; Write-Host 'Grafana container stopped' } catch { Write-Host 'Docker not running' }
foreach ($n in 'api', 'runner') {
  $f = Join-Path $run "$n.pid"
  if (Test-Path $f) {
    $id = [int](Get-Content $f)
    $p = Get-Process -Id $id -ErrorAction SilentlyContinue
    if ($p) { Stop-Process -Id $id -Force; Write-Host "stopped $n (pid $id)" } else { Write-Host "$n not running" }
    Remove-Item $f -Force
  }
}
