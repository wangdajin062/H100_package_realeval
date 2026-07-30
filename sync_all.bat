@echo off
cd /d "%~dp0"
echo ============================================================
echo   Syncing ALL files to RunPod (auto-loop until complete)
echo ============================================================
:loop
python -u upload_timed.py
if %errorlevel% neq 0 (
    echo [ERROR] Upload failed, retrying in 3s...
    timeout /t 3 /nobreak >nul
)
REM Check if all done
python -c "import json; d=json.load(open('.upload_state.json','r',encoding='utf-8')); print(f'{len(d[\"done\"])}'); exit(0 if len(d['done']) >= 193 else 1)"
if %errorlevel% neq 0 goto loop
echo.
echo ============================================================
echo   ALL DONE!
echo ============================================================
pause
