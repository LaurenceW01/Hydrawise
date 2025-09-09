@echo off
echo Restarting Hydrawise Collector Service...
echo This requires administrator privileges.
echo.

nssm stop hydrawisecollector
timeout /t 3 /nobreak > nul
nssm start hydrawisecollector

echo.
echo Service restart completed.
echo Monitor logs with: tail -f logs\nssm_stdout.log
pause

