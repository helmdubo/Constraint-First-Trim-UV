@echo off
setlocal enabledelayedexpansion

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "PROJECT_DIR=%%~fI"
set "SOURCE_DIR=%PROJECT_DIR%\cftuv"
set "OUTPUT=%PROJECT_DIR%\cftuv.zip"
set "TMP_ROOT=%TEMP%\cftuv_build"

if exist "%OUTPUT%" del "%OUTPUT%"

powershell -NoProfile -Command ^
  "$src = '%SOURCE_DIR%'; " ^
  "$tmpRoot = '%TMP_ROOT%'; " ^
  "if (Test-Path $tmpRoot) { Remove-Item $tmpRoot -Recurse -Force }; " ^
  "New-Item -ItemType Directory -Path $tmpRoot | Out-Null; " ^
  "Copy-Item $src $tmpRoot -Recurse; " ^
  "$tmpAddon = Join-Path $tmpRoot 'cftuv'; " ^
  "Get-ChildItem $tmpAddon -Recurse -Directory -Filter '__pycache__' | Remove-Item -Recurse -Force; " ^
  "Get-ChildItem $tmpAddon -Recurse -File -Filter '*.pyc' | Remove-Item -Force; " ^
  "Compress-Archive -Path $tmpAddon -DestinationPath '%OUTPUT%'; " ^
  "Remove-Item $tmpRoot -Recurse -Force; " ^
  "Write-Host '[OK] ZIP created: %OUTPUT%'"

if exist "%OUTPUT%" (
    echo.
    echo ============================================================
    echo  Ready: %OUTPUT%
    echo.
    echo  Install in Blender:
    echo    Edit - Preferences - Add-ons - Install - choose cftuv.zip
    echo ============================================================
) else (
    echo [ERROR] Failed to create ZIP
)

pause
