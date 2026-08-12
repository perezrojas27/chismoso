<#
.SYNOPSIS
  Instala el cliente local Albatros Edge (consola :8003) en Windows.

.DESCRIPTION
  Copia backend/edge_app + shared a C:\AlbatrosEdge, crea venv, instala
  requirements-edge.txt, configura WinSW como servicio albatros-edge.

.PARAMETER RepoRoot
  Raíz del repo Albatros Biométrico (donde están backend/ y packaging/).

.PARAMETER InstallDir
  Destino. Por defecto C:\AlbatrosEdge

.PARAMETER SkipService
  Solo copia e instala deps; no registra el servicio WinSW.
#>
param(
  [string]$RepoRoot = "",
  [string]$InstallDir = "C:\AlbatrosEdge",
  [switch]$SkipService
)

$ErrorActionPreference = "Stop"

if (-not $RepoRoot) {
  $RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
}

$BackendSrc = Join-Path $RepoRoot "backend"
if (-not (Test-Path (Join-Path $BackendSrc "edge_app\main.py"))) {
  throw "No se encontró edge_app en $BackendSrc. Pase -RepoRoot a la raíz del repo."
}

Write-Host "==> Destino: $InstallDir"
New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $InstallDir "backend") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $InstallDir "backend\data") | Out-Null

Write-Host "==> Copiando edge_app + shared..."
robocopy (Join-Path $BackendSrc "edge_app") (Join-Path $InstallDir "backend\edge_app") /E /NFL /NDL /NJH /NJS /nc /ns /np | Out-Null
robocopy (Join-Path $BackendSrc "shared") (Join-Path $InstallDir "backend\shared") /E /NFL /NDL /NJH /NJS /nc /ns /np | Out-Null

$reqEdge = Join-Path $BackendSrc "requirements-edge.txt"
$reqFull = Join-Path $BackendSrc "requirements.txt"
$reqDst = Join-Path $InstallDir "backend\requirements-edge.txt"
if (Test-Path $reqEdge) {
  Copy-Item $reqEdge $reqDst -Force
} else {
  Copy-Item $reqFull $reqDst -Force
}

$xmlSrc = Join-Path $RepoRoot "albatros-edge.xml"
$xmlPack = Join-Path $PSScriptRoot "albatros-edge.xml"
if (Test-Path $xmlPack) { Copy-Item $xmlPack (Join-Path $InstallDir "albatros-edge.xml") -Force }
elseif (Test-Path $xmlSrc) { Copy-Item $xmlSrc (Join-Path $InstallDir "albatros-edge.xml") -Force }

$envExample = Join-Path $RepoRoot ".env.edge-sede.example"
$envDst = Join-Path $InstallDir "backend\.env"
if (-not (Test-Path $envDst)) {
  if (Test-Path $envExample) {
    Copy-Item $envExample $envDst
    Write-Host "==> Creado backend\.env desde plantilla. EDITAR antes de producción."
  } else {
    @"
SOURCE=hikvision
SITE_CODE=oficina_central
SITE_NAME=Sede
EDGE_DATA_DIR=$InstallDir\backend\data
EDGE_ADMIN_USER=admin
EDGE_ADMIN_PASSWORD=
AUTH_DISABLED=true
INTEGRADO_BASE_URL=
ENROLLMENT_TOKEN=
"@ | Set-Content -Path $envDst -Encoding UTF8
  }
}

$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) { throw "Python no está en PATH. Instale Python 3.11+ y reinicie." }

Write-Host "==> Creando venv..."
$venv = Join-Path $InstallDir ".venv"
if (-not (Test-Path $venv)) {
  & python -m venv $venv
}

Write-Host "==> pip install (requirements-edge)..."
& (Join-Path $venv "Scripts\python.exe") -m pip install --upgrade pip
& (Join-Path $venv "Scripts\pip.exe") install -r $reqDst

if ($SkipService) {
  Write-Host "==> SkipService: no se registró WinSW."
  Write-Host "Arranque manual:"
  Write-Host "  cd $InstallDir\backend"
  Write-Host "  $InstallDir\.venv\Scripts\python.exe -m uvicorn edge_app.main:app --host 0.0.0.0 --port 8003"
  exit 0
}

$winsw = Join-Path $InstallDir "winsw.exe"
if (-not (Test-Path $winsw)) {
  Write-Host "==> Descargando WinSW..."
  [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
  Invoke-WebRequest -Uri "https://github.com/winsw/winsw/releases/download/v2.12.0/WinSW-x64.exe" -OutFile $winsw
}
Copy-Item (Join-Path $InstallDir "albatros-edge.xml") (Join-Path $InstallDir "winsw.xml") -Force

Write-Host "==> Registrando servicio albatros-edge..."
Push-Location $InstallDir
try {
  & .\winsw.exe stop 2>$null
  & .\winsw.exe uninstall 2>$null
  & .\winsw.exe install
  & .\winsw.exe start
} finally {
  Pop-Location
}

Write-Host ""
Write-Host "Listo. Consola: http://127.0.0.1:8003/"
Write-Host "Edite $envDst (INTEGRADO_BASE_URL, ENROLLMENT_TOKEN, EDGE_ADMIN_PASSWORD)."
Write-Host "Servicio: albatros-edge (services.msc)"
