@echo off
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
set PYTHONUNBUFFERED=1
echo ===== %date% %time% ===== >> loglar\zamanli.log
"venv\Scripts\python.exe" main.py 192.168.56.0/24 --snmp-yok >> loglar\zamanli.log 2>&1
