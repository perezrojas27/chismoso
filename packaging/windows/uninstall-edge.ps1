<#
.SYNOPSIS
  Detiene y desinstala el servicio Albatros Edge en Windows.
#>
param(
  [string]$InstallDir = "C:\AlbatrosEdge",
  [switch]$RemoveFiles
)

$ErrorActionPreference = "Stop"
$winsw = Join-Path $InstallDir "winsw.exe"
if (Test-Path $winsw) {
  Push-Location $InstallDir
  try {
    & .\winsw.exe stop 2>$null
    & .\winsw.exe uninstall 2>$null
  } finally {
    Pop-Location
  }
}
if ($RemoveFiles) {
  Remove-Item -Recurse -Force $InstallDir -ErrorAction SilentlyContinue
  Write-Host "Eliminado $InstallDir"
} else {
  Write-Host "Servicio desinstalado. Datos en $InstallDir conservados (use -RemoveFiles para borrar)."
}
