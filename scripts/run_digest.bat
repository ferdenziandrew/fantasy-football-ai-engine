@echo off
REM run_digest.bat -- runs the daily research digest and logs the result.
REM Lives in scripts\, one level below the project root, so it finds .env,
REM digest_history.json, and the sqlite DB the same way a manual run does.
REM
REM Uses the real python.exe directly (found via "py -0p") instead of the "py" launcher --
REM "py" was resolving to the Microsoft Store app-execution-alias stub
REM (C:\Users\ferde\AppData\Local\Microsoft\WindowsApps\py.exe), which is a known source of
REM silent failures when launched by Task Scheduler's non-interactive context even though it
REM works fine from a normal terminal.

setlocal
cd /d "%~dp0.."

if not exist logs mkdir logs

set LOGFILE=logs\digest_run_log.txt
echo. >> "%LOGFILE%"
echo ==================== %date% %time% ==================== >> "%LOGFILE%"

"C:\Users\ferde\AppData\Local\Python\pythoncore-3.14-64\python.exe" scripts\content\digest.py >> "%LOGFILE%" 2>&1

if %ERRORLEVEL% NEQ 0 (
    echo [FAILED] digest.py exited with code %ERRORLEVEL% >> "%LOGFILE%"
) else (
    echo [OK] digest.py completed successfully >> "%LOGFILE%"
)

endlocal
