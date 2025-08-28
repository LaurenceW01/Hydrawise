@echo off
set "LOG=%USERPROFILE%\WakeTask\wake-log.txt"
if not exist "%USERPROFILE%\WakeTask" mkdir "%USERPROFILE%\WakeTask"
echo [%date% %time%] Woke up and ran wake-test.bat >> "%LOG%"