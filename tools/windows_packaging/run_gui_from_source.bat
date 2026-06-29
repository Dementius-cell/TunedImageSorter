@echo off
setlocal
cd /d "%~dp0..\.."
py -m face_sorter_mvp.ui
exit /b %ERRORLEVEL%
