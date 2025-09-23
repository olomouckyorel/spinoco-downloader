@echo off
REM scripts/smoke5.bat - Thin wrapper pro tools/smoke5.py

REM Přejdi do kořenového adresáře projektu
cd /d "%~dp0\.."

REM Spusť smoke test
python tools/smoke5.py %*
