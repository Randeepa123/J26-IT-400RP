<#
  start_dashboard.ps1 - start everything for the Grafana presentation (Grafana runs in Docker; Windows Smart App Control blocks the native grafana.exe):
    1. dashboard data cache (built if missing)   2. dashboards JSON (regenerated)   3. API on this PC (127.0.0.1:8765)
    4. Docker Desktop + Grafana container (http://localhost:3000, anonymous viewer; admin login: admin / kukule-demo)   5. optional daily runner
  Usage:   scripts\start_dashboard.ps1 [-WithDailyRunner] [-NoBrowser] [-Rebuild]
  Stop:    scripts\stop_dashboard.ps1
#>
param([switch]$WithDailyRunner, [switch]$NoBrowser, [switch]$Rebuild)
$ErrorActionPreference = 'Stop'
$root    = Split-Path -Parent $PSScriptRoot
$gdir    = Join-Path $root 'grafana'
$run     = Join-Path $gdir 'runtime'
$logs    = Join-Path $root 'outputs\logs'
$apiPort = 8765
$image   = 'grafana/grafana:13.2.4-slim'
$name    = 'kukule-grafana'
New-Item -ItemType Directory -Force $run, $logs | Out-Null
$py = (Get-Command python -ErrorAction Stop).Source
function Test-Url($u) { try { (Invoke-WebRequest -UseBasicParsing -Uri $u -TimeoutSec 3).StatusCode -eq 200 } catch { $false } }
function Docker-Ready { try { (& docker info --format '{{.ServerVersion}}' 2>$null) -ne $null -and $LASTEXITCODE -eq 0 } catch { $false } }

# 1. data cache
if ($Rebuild -or -not (Test-Path (Join-Path $root 'outputs\dashboard_cache\trajectories.csv'))) {
  Write-Host 'Building dashboard data cache ...'
  & $py (Join-Path $root 'src\component3\build_dashboard_data.py') | Out-Null
}
# 2. dashboards (JSON) + provisioning files (container paths)
& $py (Join-Path $gdir 'build_dashboards.py') | Out-Host
function Render($src, $dst) { (Get-Content $src -Raw).Replace('{{API_PORT}}', "$apiPort") | Set-Content -Path $dst -Encoding UTF8 }
$prov = Join-Path $run 'provisioning'
New-Item -ItemType Directory -Force (Join-Path $prov 'datasources'), (Join-Path $prov 'dashboards') | Out-Null
Render (Join-Path $gdir 'templates\datasource.yaml.tmpl') (Join-Path $prov 'datasources\kukule.yaml')
Render (Join-Path $gdir 'templates\dashboards.yaml.tmpl') (Join-Path $prov 'dashboards\kukule.yaml')

# 3. API (listens on this PC only; the container reaches it through host.docker.internal)
if (-not (Test-Url "http://127.0.0.1:$apiPort/health")) {
  Write-Host 'Starting API ...'
  $p = Start-Process -FilePath $py -ArgumentList "`"$(Join-Path $root 'src\component3\api_server.py')`"" -WorkingDirectory $root -WindowStyle Hidden `
       -RedirectStandardOutput (Join-Path $logs 'api.log') -RedirectStandardError (Join-Path $logs 'api.err') -PassThru
  $p.Id | Set-Content (Join-Path $run 'api.pid')
  for ($i = 0; $i -lt 90 -and -not (Test-Url "http://127.0.0.1:$apiPort/health"); $i++) { Start-Sleep -Seconds 1 }
  if (-not (Test-Url "http://127.0.0.1:$apiPort/health")) { throw "API did not start; see $logs\api.err" }
} else { Write-Host 'API already running.' }

# 4. Docker Desktop + Grafana container
if (-not (Docker-Ready)) {
  $dd = 'C:\Program Files\Docker\Docker\Docker Desktop.exe'
  if (-not (Test-Path $dd)) { throw 'Docker Desktop is not installed.' }
  Write-Host 'Starting Docker Desktop ...'
  Start-Process $dd
  for ($i = 0; $i -lt 90 -and -not (Docker-Ready); $i++) { Start-Sleep -Seconds 4 }
  if (-not (Docker-Ready)) { throw 'Docker engine did not become ready. Open Docker Desktop, accept any prompt, and re-run.' }
}
if (-not (& docker images -q $image)) { Write-Host "Pulling $image ..."; & docker pull $image | Out-Host }
& docker rm -f $name 2>$null | Out-Null
$dash = Join-Path $gdir 'dashboards'
& docker run -d --name $name --restart unless-stopped -p 127.0.0.1:3000:3000 `
  -v "${dash}:/var/lib/grafana/dashboards:ro" -v "${prov}:/etc/grafana/provisioning:ro" -v kukule-grafana-data:/var/lib/grafana/data `
  -e GF_INSTALL_PLUGINS=yesoreyeram-infinity-datasource `
  -e GF_SECURITY_ADMIN_USER=admin -e GF_SECURITY_ADMIN_PASSWORD=kukule-demo -e GF_SECURITY_ALLOW_EMBEDDING=true `
  -e GF_AUTH_ANONYMOUS_ENABLED=true -e GF_AUTH_ANONYMOUS_ORG_ROLE=Viewer -e GF_USERS_DEFAULT_THEME=dark `
  -e GF_DASHBOARDS_DEFAULT_HOME_DASHBOARD_PATH=/var/lib/grafana/dashboards/1_live_plan.json -e GF_DASHBOARDS_MIN_REFRESH_INTERVAL=2s `
  -e GF_ANALYTICS_REPORTING_ENABLED=false -e GF_ANALYTICS_CHECK_FOR_UPDATES=false -e GF_ANALYTICS_CHECK_FOR_PLUGIN_UPDATES=false -e GF_NEWS_NEWS_FEED_ENABLED=false `
  --add-host=host.docker.internal:host-gateway $image | Out-Null
Write-Host 'Waiting for Grafana (first start installs the Infinity plugin) ...'
for ($i = 0; $i -lt 150 -and -not (Test-Url 'http://127.0.0.1:3000/api/health'); $i++) { Start-Sleep -Seconds 2 }
if (-not (Test-Url 'http://127.0.0.1:3000/api/health')) { & docker logs --tail 30 $name; throw 'Grafana did not become healthy.' }

# 5. optional daily runner
if ($WithDailyRunner) {
  $p = Start-Process -FilePath $py -ArgumentList "`"$(Join-Path $root 'src\component3\daily_runner.py')`"", '--watch', '--interval', '10' -WorkingDirectory $root -WindowStyle Hidden `
       -RedirectStandardOutput (Join-Path $logs 'daily_runner.log') -RedirectStandardError (Join-Path $logs 'daily_runner.err') -PassThru
  $p.Id | Set-Content (Join-Path $run 'runner.pid')
  Write-Host 'Daily runner watching data\live_inputs (every 10 s).'
}
$url = 'http://localhost:3000/d/kg-live'
Write-Host "`nDashboards ready: $url   (results: /d/kg-results   scenarios: /d/kg-scen)"
if (-not $NoBrowser) { Start-Process $url }
