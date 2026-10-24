@echo off
cd /d "%~dp0"
python start_causalbench.py
if errorlevel 1 pause
