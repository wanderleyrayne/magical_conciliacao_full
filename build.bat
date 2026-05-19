@echo off
REM ============================================================
REM  BUILD Magical Conciliacao - arquivo unico (.exe)
REM  Execute: build.bat
REM ============================================================
echo.
echo  Magical Conciliacao - Build v5.0.0
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
  --hidden-import reportlab ^
  --hidden-import reportlab.lib ^
  --hidden-import reportlab.lib.pagesizes ^
  --hidden-import reportlab.lib.colors ^
  --hidden-import reportlab.lib.units ^
  --hidden-import reportlab.lib.styles ^
  --hidden-import reportlab.lib.enums ^
  --hidden-import reportlab.platypus ^
  --hidden-import reportlab.platypus.tables ^
  --hidden-import reportlab.platypus.paragraph ^
  --hidden-import reportlab.pdfgen ^
  --hidden-import reportlab.pdfgen.canvas ^
  --collect-submodules pandas ^
  --collect-submodules openpyxl ^
  --collect-submodules numpy ^
  --collect-submodules reportlab ^
  --collect-data openpyxl ^
  --collect-data reportlab ^
  main.py

if %ERRORLEVEL% EQU 0 (
  echo.
  echo  Build concluido com sucesso!
  echo  Executavel: dist\Magical_Conciliacao.exe
  dir dist\Magical_Conciliacao.exe | find "Magical"
  echo.
  echo  Proximos passos:
  echo  1. Teste o executavel em dist\Magical_Conciliacao.exe
  echo  2. Faca upload para a release v5.0.0 no GitHub
) else (
  echo.
  echo  ERRO no build! Verifique as mensagens acima.
)
pause