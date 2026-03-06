@echo off
REM ============================================================
REM  CFTUV Dev Install — создаёт symlink в папку аддонов Blender
REM  Запускать от имени администратора!
REM ============================================================

setlocal enabledelayedexpansion

REM --- Версия Blender (по умолчанию 4.1) ---
set "BLENDER_VER=%~1"
if "%BLENDER_VER%"=="" set "BLENDER_VER=4.1"

REM --- Проверка прав администратора ---
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Этот скрипт требует прав администратора.
    echo         Правый клик на .bat файл - "Запуск от имени администратора"
    pause
    exit /b 1
)

REM --- Пути ---
set "SCRIPT_DIR=%~dp0"
set "PROJECT_DIR=%SCRIPT_DIR%.."
set "ADDON_SOURCE=%PROJECT_DIR%\cftuv"
set "BLENDER_ADDONS=%APPDATA%\Blender Foundation\Blender\%BLENDER_VER%\scripts\addons"
set "ADDON_TARGET=%BLENDER_ADDONS%\cftuv"

REM --- Проверяем что cftuv/ существует ---
if not exist "%ADDON_SOURCE%" (
    echo [ERROR] Папка cftuv/ не найдена: %ADDON_SOURCE%
    pause
    exit /b 1
)

REM --- Создаём папку addons если нет ---
if not exist "%BLENDER_ADDONS%" (
    echo [INFO] Создаю папку: %BLENDER_ADDONS%
    mkdir "%BLENDER_ADDONS%"
)

REM --- Удаляем старый symlink/папку если есть ---
if exist "%ADDON_TARGET%" (
    echo [INFO] Удаляю существующий: %ADDON_TARGET%
    rmdir "%ADDON_TARGET%" 2>nul
    if exist "%ADDON_TARGET%" (
        echo [ERROR] Не удалось удалить %ADDON_TARGET%
        echo         Возможно, Blender запущен. Закройте Blender и попробуйте снова.
        pause
        exit /b 1
    )
)

REM --- Создаём symlink ---
mklink /D "%ADDON_TARGET%" "%ADDON_SOURCE%"
if %errorlevel% neq 0 (
    echo [ERROR] Не удалось создать symlink
    pause
    exit /b 1
)

echo.
echo ============================================================
echo  [OK] Symlink создан!
echo.
echo  Источник:  %ADDON_SOURCE%
echo  Ссылка:    %ADDON_TARGET%
echo.
echo  Следующие шаги:
echo    1. Перезапустите Blender
echo    2. Edit - Preferences - Add-ons
echo    3. Найдите "Hotspot UV" и включите
echo    4. Панель появится в View3D - Sidebar (N) - Hotspot UV
echo ============================================================
echo.
pause
