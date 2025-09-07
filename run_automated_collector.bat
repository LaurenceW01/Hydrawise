@echo off
REM Hydrawise Automated Collector Service Launcher
REM This batch file runs the automated collector in continuous mode

REM Change to the project directory
cd /d "C:\Users\laure\Dev\Hydrawise"

REM Activate the virtual environment and run the collector
call "hydrawise-venv\Scripts\activate.bat"

REM Run the automated collector in continuous mode with appropriate logging
python automated_collector.py --continuous --headless --log-level INFO

REM If the collector exits, wait 30 seconds before the service manager restarts it
timeout /t 30 /nobreak > nul

