@echo off
setlocal
cd /d "%~dp0"

echo [1/3] Gerando icones...
python tools\make_icon.py || goto :error

echo [2/3] Compilando Klip.exe...
python -m PyInstaller --noconfirm --clean Klip.spec || goto :error

echo [3/3] Copiando executavel...
copy /y "dist\Klip.exe" "Klip.exe" >nul || goto :error

echo.
echo Pronto: %CD%\Klip.exe
exit /b 0

:error
echo.
echo Falha na compilacao.
exit /b 1
