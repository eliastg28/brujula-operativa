# Instala todo lo necesario (una sola vez)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Test-Path ".venv")) { python -m venv .venv }
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

Push-Location frontend
npm install --no-audit --no-fund
Pop-Location

if (-not (Test-Path ".env")) { Copy-Item .env.example .env; Write-Host "Creado .env desde .env.example (Modo Demo)" }
Write-Host "`nListo. Ejecuta .\start.ps1 para levantar la app." -ForegroundColor Green
