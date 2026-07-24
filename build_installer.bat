@echo off
setlocal

cd /d "%~dp0"

echo.
echo ==========================================
echo  MJET-X Helper - Installer Build
echo ==========================================
echo.

if not exist "dist\MJETXHelper.exe" (
  echo FEHLER: dist\MJETXHelper.exe wurde nicht gefunden.
  echo Bitte zuerst build_exe.bat starten.
  echo.
  pause
  exit /b 1
)

if not exist "installer.iss" (
  echo FEHLER: installer.iss wurde nicht gefunden.
  echo Bitte diese Datei im MJET-X-Helper-Ordner starten.
  echo.
  pause
  exit /b 1
)

set "ISCC_CMD="

where ISCC.exe >nul 2>nul
if not errorlevel 1 set "ISCC_CMD=ISCC.exe"

if not defined ISCC_CMD (
  if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC_CMD=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
)

if not defined ISCC_CMD (
  if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC_CMD=%ProgramFiles%\Inno Setup 6\ISCC.exe"
)

if not defined ISCC_CMD (
  echo FEHLER: Inno Setup wurde nicht gefunden.
  echo Bitte Inno Setup 6 installieren:
  echo https://jrsoftware.org/isdl.php
  echo.
  echo Danach diese Datei erneut starten.
  echo.
  pause
  exit /b 1
)

echo Verwende Inno Setup:
echo %ISCC_CMD%
echo.

"%ISCC_CMD%" "installer.iss"
if errorlevel 1 goto build_failed

echo.
echo ==========================================
echo  Fertig.
echo ==========================================
echo.
echo Installer:
echo %CD%\installer_dist\MJETXHelper_Setup_v1.1.1.exe
echo.
echo Diese Datei kann als GitHub Release-Datei hochgeladen werden.
echo.
pause
exit /b 0

:build_failed
echo.
echo ==========================================
echo  INSTALLER BUILD FEHLGESCHLAGEN
echo ==========================================
echo.
echo Bitte die Fehlermeldung oben ansehen.
echo.
pause
exit /b 1
