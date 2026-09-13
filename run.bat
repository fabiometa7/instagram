@echo off
cd /d "%~dp0"
if not exist .venv (
  python -m venv .venv
)
call .venv\Scripts\activate.bat
pip install -q -r requirements.txt
if "%IG_USERNAME%"=="" set IG_USERNAME=fabiometa_
echo.
echo   Content Hub running at http://127.0.0.1:5000
echo.
python app.py
