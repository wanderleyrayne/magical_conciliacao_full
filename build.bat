@echo off
REM ============================================================
REM  BUILD Magical Conciliacao - arquivo unico (.exe)
REM  Execute: build.bat
REM ============================================================

echo.
echo  Magical Conciliacao - Build
echo ============================================================

if exist build rmdir /s /q build
if exist dist  rmdir /s /q dist

pyinstaller ^
  --noconfirm ^
  --onefile ^
  --windowed ^
  --name "Magical_Conciliacao" ^
  --icon=assets\icon.ico ^
  --add-data "assets;assets" ^
  --add-data "core;core" ^
  --add-data "database;database" ^
  --add-data "ui;ui" ^
  --add-data "utils;utils" ^
  --add-data "config_inicial.json;." ^
  --add-data "setup_inicial.py;." ^
  --hidden-import openpyxl ^
  --hidden-import et_xmlfile ^
  --hidden-import openpyxl.cell._writer ^
  --hidden-import rapidfuzz ^
  --hidden-import rapidfuzz.fuzz ^
  --hidden-import rapidfuzz.process ^
  --hidden-import requests ^
  --hidden-import numpy ^
  --hidden-import numpy.core ^
  --hidden-import tkinter ^
  --hidden-import tkinter.ttk ^
  --hidden-import tkinter.messagebox ^
  --hidden-import tkinter.filedialog ^
  --hidden-import tkinter.scrolledtext ^
  --collect-submodules pandas ^
  --collect-submodules openpyxl ^
  --collect-submodules numpy ^
  --collect-data openpyxl ^
  main.py

if %ERRORLEVEL% EQU 0 (
  echo.
  echo  Build concluido!
  echo  Executavel: dist\Magical_Conciliacao.exe
  dir dist\Magical_Conciliacao.exe | find "Magical"
) else (
  echo.
  echo  ERRO no build.
)

pause