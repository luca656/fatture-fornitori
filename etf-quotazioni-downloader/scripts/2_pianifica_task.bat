@echo off
REM ============================================================
REM  2_pianifica_task.bat
REM  Da eseguire UNA SOLA VOLTA, dopo "1_installa.bat".
REM  Registra un'attivita' nel Task Scheduler di Windows che lancia
REM  "esegui.bat" ogni giorno, cosi' il report si aggiorna da solo.
REM
REM  Puoi cambiare l'orario modificando il valore ORARIO qui sotto
REM  (formato HH:MM, 24 ore). Di default: le 19:30, a mercati europei
REM  chiusi.
REM ============================================================

set ORARIO=19:30
set NOME_TASK=ETF Quotazioni Downloader

cd /d "%~dp0.."
set CARTELLA=%cd%

echo.
echo Registro l'attivita' pianificata "%NOME_TASK%" alle ore %ORARIO% ogni giorno...
echo (potrebbe essere richiesta l'autorizzazione di Windows)
echo.

schtasks /Create /TN "%NOME_TASK%" /TR "\"%CARTELLA%\scripts\esegui.bat\"" /SC DAILY /ST %ORARIO% /F

if errorlevel 1 (
    echo.
    echo Non sono riuscito a creare l'attivita' automaticamente.
    echo Puoi crearla manualmente da "Utilita' di pianificazione" di Windows,
    echo puntando al file: %CARTELLA%\scripts\esegui.bat
) else (
    echo.
    echo Fatto! Ogni giorno alle %ORARIO% verra' generato automaticamente
    echo il nuovo report in: %CARTELLA%\report\ultimo_report.html
    echo.
    echo Per disattivare in futuro: apri "Utilita' di pianificazione di Windows"
    echo e cerca l'attivita' "%NOME_TASK%", oppure esegui:
    echo   schtasks /Delete /TN "%NOME_TASK%" /F
)

echo.
pause
