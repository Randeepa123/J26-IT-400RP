<#
.SYNOPSIS
    Starts the native web Live Dashboard for Component 3 (No Docker required).
.DESCRIPTION
    Runs the Python API server and opens the interactive Live Dashboard in your default web browser.
    Works independently of Docker and Smart App Control.
#>
param(
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir = Split-Path -Parent $ScriptDir

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host " Kukule Ganga Hydro Optimizer - Native Web Live Dashboard" -ForegroundColor Green
Write-Host " (Zero Docker / Native Browser)" -ForegroundColor Yellow
Write-Host "==========================================================" -ForegroundColor Cyan

Set-Location $RootDir
python src\component3\run_dashboard.py
