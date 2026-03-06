$ErrorActionPreference = "Stop"

$RootDir = (Resolve-Path "$PSScriptRoot\..").Path
Set-Location $RootDir

py -m pip install --upgrade pip
py -m pip install -r requirements-build.txt
py -m PyInstaller --clean desktop_windows.spec
Write-Host "Built Windows executable: dist\CardOptimiser.exe"

$InnoSetup = Get-Command "ISCC.exe" -ErrorAction SilentlyContinue
if ($InnoSetup) {
    & $InnoSetup.Path "packaging\windows\installer.iss"
    Write-Host "Built Windows installer: dist\CardOptimiserSetup.exe"
} else {
    Write-Host "ISCC.exe not found; skipped installer build."
}
