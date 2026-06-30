@echo off
chcp 65001 >nul
cd /d "%~dp0"
title GOOD ENGINEERS OS
set ST_PORT=8501

echo.
echo  Demarrage de GOOD ENGINEERS OS...
echo  Dossier: %CD%
echo  URL:     http://localhost:%ST_PORT%
echo.

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -m streamlit run app.py --server.port %ST_PORT%
    goto fin
)

where python >nul 2>&1
if %ERRORLEVEL% equ 0 (
    python -m streamlit run app.py --server.port %ST_PORT%
    goto fin
)

where py >nul 2>&1
if %ERRORLEVEL% equ 0 (
    py -m streamlit run app.py --server.port %ST_PORT%
    goto fin
)

echo [ERREUR] Python introuvable. Installez Python 3.11+ puis:
echo   cd "%CD%"
echo   python -m venv .venv
echo   .venv\Scripts\pip install -r requirements.txt
echo Ensuite relancez ce fichier.
pause
exit /b 1

:fin
if %ERRORLEVEL% neq 0 pause
