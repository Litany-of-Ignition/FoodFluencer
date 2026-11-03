@echo off
title FoodFluencer
cd /d "%~dp0"
where python >nul 2>nul
if errorlevel 1 (
  echo Python is not installed. Get it from https://www.python.org/downloads/ and tick "Add python.exe to PATH".
  pause
  exit /b 1
)
python -c "import flask, PIL, comfy_sdk" >nul 2>nul
if errorlevel 1 (
  echo First run: installing what FoodFluencer needs. This takes a minute...
  python -m pip install -r requirements.txt
  if errorlevel 1 (
    echo Install failed. Check your internet connection and try again.
    pause
    exit /b 1
  )
)
echo FoodFluencer is starting. Keep this window open while you use it. Close it to stop.
python app.py
pause
