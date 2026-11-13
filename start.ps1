# Levanta MCP Server (:8001), Orquestador (:8000) y Web (:5173) en ventanas separadas
#   .\start.ps1          → normal
#   .\start.ps1 -Reset   → reinicia los datos de demo antes de arrancar
param([switch]$Reset)
Set-Location $PSScriptRoot
$py = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"

if ($Reset -and (Test-Path "data")) { Remove-Item -Recurse -Force "data"; Write-Host "Datos de demo reiniciados" }

Start-Process powershell -ArgumentList "-NoExit", "-Command", "`$host.UI.RawUI.WindowTitle='MCP Server :8001'; Set-Location '$PSScriptRoot'; & '$py' -m mcp_server.server"
Start-Sleep -Seconds 3
Start-Process powershell -ArgumentList "-NoExit", "-Command", "`$host.UI.RawUI.WindowTitle='Orquestador :8000'; Set-Location '$PSScriptRoot'; & '$py' -m uvicorn backend.main:app --port 8000"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "`$host.UI.RawUI.WindowTitle='Web :5173'; Set-Location '$PSScriptRoot\frontend'; npm run dev"
Start-Sleep -Seconds 6
Start-Process "http://localhost:5173"
Write-Host "Brújula Operativa corriendo en http://localhost:5173" -ForegroundColor Green
