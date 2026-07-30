@echo off
cd /d "%~dp0"
echo ============================================================
echo   Sync local files to RunPod container
echo ============================================================
echo.
echo Target: https://40e69wcbga2q1d-8888.proxy.runpod.net
echo Remote: /workspace/H100_package_realeval
echo.
python scripts\sync_to_runpod.py ^
    --base-url https://40e69wcbga2q1d-8888.proxy.runpod.net ^
    --token vbul2cc1qmltayxrjyws ^
    --local-root "%cd%" ^
    --remote-root /workspace/H100_package_realeval
echo.
echo ============================================================
echo   Sync complete!
echo ============================================================
pause
