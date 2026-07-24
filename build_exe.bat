@echo off
setlocal

cd /d "%~dp0"

echo.
echo ==========================================
echo  MJET-X Helper - EXE Build
echo ==========================================
echo.

if not exist "main.py" (
  echo FEHLER: main.py wurde nicht gefunden.
  echo Bitte diese Datei im MJET-X-Helper-Ordner starten.
  echo.
  pause
  exit /b 1
)

set "PYTHON_CMD="

where py >nul 2>nul
if not errorlevel 1 (
  py -3.11 -c "import sys" >nul 2>nul
  if not errorlevel 1 set "PYTHON_CMD=py -3.11"
)

if not defined PYTHON_CMD (
  where py >nul 2>nul
  if not errorlevel 1 set "PYTHON_CMD=py -3"
)

if not defined PYTHON_CMD (
  where python >nul 2>nul
  if not errorlevel 1 set "PYTHON_CMD=python"
)

if not defined PYTHON_CMD (
  echo FEHLER: Python wurde nicht gefunden.
  echo Bitte Python 3.11 oder neuer installieren und "Add Python to PATH" aktivieren.
  echo.
  pause
  exit /b 1
)

echo Verwende Python:
%PYTHON_CMD% --version
echo.

if not exist ".venv-build" (
  echo Erstelle lokale Build-Umgebung...
  %PYTHON_CMD% -m venv ".venv-build"
  if errorlevel 1 goto build_failed
)

set "VENV_PY=.venv-build\Scripts\python.exe"

if not exist "%VENV_PY%" (
  echo FEHLER: Build-Python wurde nicht gefunden: %VENV_PY%
  echo.
  pause
  exit /b 1
)

echo.
echo Installiere Build-Pakete...
"%VENV_PY%" -m pip install --upgrade pip setuptools wheel
if errorlevel 1 goto build_failed

"%VENV_PY%" -m pip install --upgrade pyinstaller PyMuPDF Pillow
if errorlevel 1 goto build_failed

echo.
echo Baue MJETXHelper.exe...
"%VENV_PY%" -m PyInstaller ^
  --onefile ^
  --noconsole ^
  --clean ^
  --name MJETXHelper ^
  --collect-all fitz ^
  --collect-all PIL ^
  --hidden-import fitz ^
  --hidden-import PIL ^
  --hidden-import PIL.Image ^
  --hidden-import PIL.ImageChops ^
  --hidden-import PIL.ImageFilter ^
  --hidden-import PIL.PngImagePlugin ^
  main.py
if errorlevel 1 goto build_failed

if exist "helper_config.json" (
  copy /Y "helper_config.json" "dist\helper_config.json" >nul
)

echo.
echo ==========================================
echo  Fertig.
echo ==========================================
echo.
echo EXE:
echo %CD%\dist\MJETXHelper.exe
echo.
echo Config wurde nach dist\helper_config.json kopiert.
echo.
pause
exit /b 0

:build_failed
echo.
echo ==========================================
echo  BUILD FEHLGESCHLAGEN
echo ==========================================
echo.
echo Bitte die Fehlermeldung oben ansehen.
echo Wenn Internet auf dem Maschinenrechner gesperrt ist, muessen PyInstaller,
echo PyMuPDF und Pillow vorher lokal/offline bereitgestellt werden.
echo.
pause
exit /b 1
