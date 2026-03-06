@echo off
REM ============================================================
REM  CFTUV Lint — проверка синтаксиса Python файлов
REM ============================================================

setlocal enabledelayedexpansion

set "SCRIPT_DIR=%~dp0"
set "PROJECT_DIR=%SCRIPT_DIR%.."
set "ERRORS=0"
set "CHECKED=0"

echo Проверка синтаксиса cftuv/ ...
echo.

for /r "%PROJECT_DIR%\cftuv" %%f in (*.py) do (
    set /a CHECKED+=1
    python -m py_compile "%%f" 2>nul
    if !errorlevel! neq 0 (
        echo [FAIL] %%f
        set /a ERRORS+=1
    )
)

echo.
if %ERRORS% equ 0 (
    echo [OK] Все %CHECKED% файлов прошли проверку синтаксиса.
) else (
    echo [FAIL] %ERRORS% из %CHECKED% файлов с ошибками.
)

pause
