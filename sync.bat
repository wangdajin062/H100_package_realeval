@echo off 
:: RealEval Sync Script - Push local changes to GitHub 
cd /d %%~dp0 
git add -A 
git commit -m "sync: %周三 2026/07/22% %11:57:50.04%" 
git push origin master:main 
echo. 
echo === Sync complete! === 
pause 
