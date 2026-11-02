@echo off
cd /d "%~dp0"
where pythonw >nul 2>nul
if %errorlevel% equ 0 (
    start "" pythonw vscode_app.py
) else (
    start "" "dist\FPGA Studio\FPGA Studio.exe"
)
