@echo off
set CURRENT_DIR=%~dp0
cd /d %CURRENT_DIR%
start "" "%CURRENT_DIR%venv\Scripts\pythonw.exe" "%CURRENT_DIR%app.pyw"
exit
