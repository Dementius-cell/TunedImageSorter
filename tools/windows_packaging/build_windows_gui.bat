@echo off
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0build_windows_gui.ps1" %*
exit /b %ERRORLEVEL%
