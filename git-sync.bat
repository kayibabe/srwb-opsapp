@echo off
cd /d "D:\WebApps\opsapp"

echo =======================================
echo   SRWB OpsApp - Git Sync
echo =======================================
echo.

set /p msg="Commit message: "

if "%msg%"=="" (
    echo [ERROR] Commit message cannot be empty.
    pause
    exit /b 1
)

echo.
echo [1/3] Staging all changes...
git add .

echo [2/3] Committing: %msg%
git commit -m "%msg%"

echo [3/3] Pushing to GitHub...
git push

echo.
echo =======================================
echo   Done! Changes pushed to GitHub.
echo =======================================
pause
