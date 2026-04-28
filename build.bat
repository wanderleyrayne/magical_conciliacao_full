@echo off
REM ============================================================
REM  BUILD — Magical Conciliação
REM  Gera dist\Magical_Conciliacao.exe
REM  Execute: build.bat
REM ============================================================

echo.
echo  Magical Conciliacao — Build
echo ============================================================

REM Limpa builds anteriores
if exist build rmdir /s /q build
if exist dist  rmdir /s /q dist

pyinstaller ^
  --noconfirm ^
  --windowed ^
  --name "Magical_Conciliacao" ^
  --icon=assets\icon.ico ^
  --add-data "assets;assets" ^
  --add-data "core;core" ^
  --add-data "database;database" ^
  --add-data "ui;ui" ^
  --add-data "utils;utils" ^
  --hidden-import openpyxl ^
  --hidden-import et_xmlfile ^
  --hidden-import openpyxl.cell._writer ^
  --hidden-import rapidfuzz ^
  --hidden-import rapidfuzz.fuzz ^
  --hidden-import rapidfuzz.process ^
  --hidden-import requests ^
  --hidden-import numpy ^
  --hidden-import numpy.core ^
  --collect-submodules pandas ^
  --collect-submodules openpyxl ^
  --collect-submodules numpy ^
  --collect-data openpyxl ^
  main.py

if %ERRORLEVEL% EQU 0 (
  echo.
  echo  Build concluido com sucesso!
  echo  Executavel: dist\Magical_Conciliacao\Magical_Conciliacao.exe
  echo.
) else (
  echo.
  echo  ERRO no build. Verifique os logs acima.
  echo.
)

pause