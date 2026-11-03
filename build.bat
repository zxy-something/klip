@echo off
setlocal
cd /d "%~dp0"

echo [1/3] Generating icons...
python tools\make_icon.py || goto :error

echo [2/3] Building Klip.exe...
python -m PyInstaller --noconfirm --clean Klip.spec || goto :error

echo [3/3] Copying executable...
copy /y "dist\Klip.exe" "Klip.exe" >nul || goto :error

echo.
echo Ready: %CD%\Klip.exe
exit /b 0

:error
echo.
echo Build failed.
exit /b 1
