@echo off
REM ============================================================
REM  1_installa.bat
REM  Da eseguire UNA SOLA VOLTA la prima volta, con doppio click.
REM  Crea l'ambiente Python (venv) e installa le librerie necessarie.
REM ============================================================

cd /d "%~dp0.."

echo.
echo === ETF Quotazioni Downloader - Installazione ===
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo ERRORE: Python non risulta installato o non e' nel PATH.
    echo Scarica e installa Python da https://www.python.org/downloads/
    echo Durante l'installazione, spunta la casella "Add Python to PATH".
    echo.
    pause
    exit /b 1
)

echo Creo l'ambiente virtuale in ".venv" ...
python -m venv .venv

echo Installo le librerie necessarie ...
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements.txt

echo.
echo Installazione completata.
echo Ora esegui "2_pianifica_task.bat" per programmare il download giornaliero automatico,
echo oppure esegui "esegui.bat" per lanciare subito un aggiornamento manuale.
echo.
pause
