@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\activate.bat" (
    echo ERROR: Virtual environment not found. Run setup first.
    exit /b 1
)
call .venv\Scripts\activate.bat

if not exist "logs" mkdir logs

set LOG_DATE=%DATE:~10,4%%DATE:~4,2%%DATE:~7,2%
python main.py >> "logs\tempo_%LOG_DATE%.log" 2>&1

if %ERRORLEVEL% NEQ 0 (
    echo Tempo report FAILED on %DATE% %TIME% >> "logs\tempo_%LOG_DATE%.log"
)
