$ErrorActionPreference = "Stop"

$RootDir = (Resolve-Path "$PSScriptRoot\..").Path
Set-Location $RootDir

py -m pip install --upgrade pip
py -m pip install -r requirements-build.txt
py -m PyInstaller --clean desktop.spec

$ZipPath = Join-Path $RootDir "dist\CardOptimiser-windows.zip"
if (Test-Path $ZipPath) {
    Remove-Item $ZipPath -Force
}
Compress-Archive -Path "dist\CardOptimiser\*" -DestinationPath $ZipPath
Write-Host "Built Windows app folder: dist\CardOptimiser"
Write-Host "Built Windows ZIP: $ZipPath"

$InnoSetup = Get-Command "ISCC.exe" -ErrorAction SilentlyContinue
if ($InnoSetup) {
    & $InnoSetup.Path "packaging\windows\installer.iss"
    Write-Host "Built Windows installer: dist\CardOptimiserSetup.exe"
} else {
    Write-Host "ISCC.exe not found; skipped installer build."
}
