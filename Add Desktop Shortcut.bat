@echo off
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -Command "$s=(New-Object -ComObject WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Desktop')+'\FoodFluencer.lnk'); $s.TargetPath='%~dp0Start FoodFluencer.bat'; $s.WorkingDirectory='%~dp0'; $s.IconLocation='%~dp0static\FoodFluencer.ico'; $s.Description='FoodFluencer'; $s.Save()"
if errorlevel 1 (
  echo Could not add the shortcut.
) else (
  echo Done. Look for FoodFluencer on your desktop.
)
pause
