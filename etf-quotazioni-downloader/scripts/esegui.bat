@echo off
REM ============================================================
REM  esegui.bat
REM  Lancia l'aggiornamento delle quotazioni e il report del giorno.
REM  Usato sia per il lancio manuale (doppio click) sia dal
REM  Task Scheduler di Windows per l'esecuzione automatica giornaliera.
REM ============================================================

cd /d "%~dp0.."

if not exist ".venv\Scripts\python.exe" (
    echo ERRORE: ambiente non installato. Esegui prima "1_installa.bat".
    pause
    exit /b 1
)

".venv\Scripts\python.exe" main.py

if errorlevel 1 (
    echo.
    echo Si e' verificato un errore. Controlla il file di log nella cartella "log".
    pause
)
