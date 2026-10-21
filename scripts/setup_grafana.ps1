<#
  setup_grafana.ps1 - one-time setup: download the standalone Grafana OSS zip (official dl.grafana.com) into <project>\tools\grafana
  and install the free "Infinity" data-source plugin into <project>\grafana\plugins. Nothing is installed system-wide.
  Safe to re-run: skips what already exists; the download resumes if interrupted.
#>
param(
  [string]$Version = '13.2.4',
  [string]$PluginVersion = '4.1.2'
)
$ErrorActionPreference = 'Stop'
$root   = Split-Path -Parent $PSScriptRoot
$tools  = Join-Path $root 'tools'
$home_  = Join-Path $tools 'grafana'
$plug   = Join-Path $root 'grafana\plugins'
New-Item -ItemType Directory -Force $tools, $plug | Out-Null

if (-not (Test-Path (Join-Path $home_ 'bin\grafana.exe'))) {
  $zip = Join-Path $tools "grafana-$Version.windows-amd64.zip"
  $url = "https://dl.grafana.com/oss/release/grafana-$Version.windows-amd64.zip"
  if (-not (Test-Path $zip) -or ((Get-Item $zip).Length -lt 400MB)) {
    Write-Host "Downloading $url (about 470 MB) ..."
    & curl.exe -sS -L --fail -C - -o $zip $url
    if ($LASTEXITCODE -ne 0) { throw "download failed (exit $LASTEXITCODE); re-run the script to resume" }
  }
  Write-Host 'Unzipping ...'
  $tmp = Join-Path $tools '_unzip'
  if (Test-Path $tmp) { Remove-Item $tmp -Recurse -Force }
  Expand-Archive -Path $zip -DestinationPath $tmp -Force
  $inner = Get-ChildItem $tmp -Directory | Where-Object { Test-Path (Join-Path $_.FullName 'bin\grafana.exe') } | Select-Object -First 1
  if (-not $inner) { throw 'grafana.exe not found in the archive' }
  if (Test-Path $home_) { Remove-Item $home_ -Recurse -Force }
  Move-Item $inner.FullName $home_
  Remove-Item $tmp -Recurse -Force
  Write-Host "Grafana unpacked to $home_"
} else { Write-Host "Grafana already present: $home_" }

$infinity = Join-Path $plug 'yesoreyeram-infinity-datasource'
if (-not (Test-Path $infinity)) {
  Write-Host "Installing Infinity plugin $PluginVersion ..."
  $pz = Join-Path $tools "infinity-$PluginVersion.zip"
  $purl = "https://grafana.com/api/plugins/yesoreyeram-infinity-datasource/versions/$PluginVersion/download?os=windows&arch=amd64"
  & curl.exe -sS -L --fail -o $pz $purl
  if ($LASTEXITCODE -ne 0) {
    $purl = "https://grafana.com/api/plugins/yesoreyeram-infinity-datasource/versions/$PluginVersion/download"
    & curl.exe -sS -L --fail -o $pz $purl
    if ($LASTEXITCODE -ne 0) { throw 'plugin download failed' }
  }
  Expand-Archive -Path $pz -DestinationPath $plug -Force
  Remove-Item $pz -Force
}
Write-Host ("Plugin folder: " + ((Get-ChildItem $plug -Directory).Name -join ', '))
Write-Host 'Setup complete. Next: scripts\start_dashboard.ps1'
