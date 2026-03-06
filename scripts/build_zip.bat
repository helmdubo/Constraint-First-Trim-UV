@echo off
REM ============================================================
REM  CFTUV Build ZIP — собирает аддон в zip для установки
REM ============================================================

setlocal enabledelayedexpansion

set "SCRIPT_DIR=%~dp0"
set "PROJECT_DIR=%SCRIPT_DIR%.."
set "OUTPUT=%PROJECT_DIR%\cftuv.zip"

REM --- Удаляем старый zip ---
if exist "%OUTPUT%" del "%OUTPUT%"

REM --- Собираем zip через PowerShell ---
powershell -NoProfile -Command ^
  "Add-Type -Assembly 'System.IO.Compression.FileSystem'; " ^
  "$src = '%PROJECT_DIR%\cftuv'; " ^
  "$tmp = Join-Path $env:TEMP 'cftuv_build'; " ^
  "if (Test-Path $tmp) { Remove-Item $tmp -Recurse -Force }; " ^
  "Copy-Item $src $tmp -Recurse; " ^
  "Get-ChildItem $tmp -Recurse -Directory -Filter '__pycache__' | Remove-Item -Recurse -Force; " ^
  "Get-ChildItem $tmp -Recurse -File -Filter '*.pyc' | Remove-Item -Force; " ^
  "Compress-Archive -Path $tmp -DestinationPath '%OUTPUT%'; " ^
  "Remove-Item $tmp -Recurse -Force; " ^
  "Write-Host '[OK] ZIP создан: %OUTPUT%'"

if exist "%OUTPUT%" (
    echo.
    echo ============================================================
    echo  Готово! Файл: %OUTPUT%
    echo.
    echo  Установка в Blender:
    echo    Edit - Preferences - Add-ons - Install - выбрать cftuv.zip
    echo ============================================================
) else (
    echo [ERROR] Не удалось создать ZIP
)

pause
