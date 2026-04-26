@echo off
REM Script para ativar auto-commit no Windows

setlocal enabledelayedexpansion

REM Cores (Windows 10+)
for /F %%A in ('echo prompt $E ^| cmd') do set "ESC=%%A"

echo %ESC%[36m======================================================%ESC%[0m
echo %ESC%[36m ⚽ SISTEMA DE AUTO-COMMIT - FOOTBALL ANALYTICS%ESC%[0m
echo %ESC%[36m======================================================%ESC%[0m
echo.

REM Verificar se Python está instalado
python --version >nul 2>&1
if errorlevel 1 (
    echo %ESC%[31m❌ Python não está instalado ou não está no PATH%ESC%[0m
    pause
    exit /b 1
)

echo %ESC%[32m✅ Python encontrado%ESC%[0m

REM Verificar se Git está instalado
git --version >nul 2>&1
if errorlevel 1 (
    echo %ESC%[31m❌ Git não está instalado ou não está no PATH%ESC%[0m
    pause
    exit /b 1
)

echo %ESC%[32m✅ Git encontrado%ESC%[0m
echo.

REM Determinar modo de execução
if "%1"=="dry-run" (
    echo %ESC%[33m⚠️  MODO DRY-RUN: Nenhum commit será feito de verdade%ESC%[0m
    echo.
    echo Iniciando em modo de teste...
    python auto_commit.py --dry-run
) else (
    echo %ESC%[32m🟢 MODO NORMAL: Commits reais serão feitos%ESC%[0m
    echo.
    echo Iniciando sistema de auto-commit...
    python auto_commit.py
)

if errorlevel 1 (
    echo.
    echo %ESC%[31m❌ Erro ao executar auto-commit%ESC%[0m
    pause
    exit /b 1
)

echo.
echo %ESC%[32m✅ Auto-commit finalizado%ESC%[0m
pause
