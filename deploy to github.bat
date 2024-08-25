@echo off
setlocal enabledelayedexpansion

:: Check if git is installed
where git >nul 2>nul
if %errorlevel% neq 0 (
    echo Git is not installed or not in the system PATH.
    echo Please install Git and try again.
    pause
    exit /b 1
)

:: Initialize the repository
git init

:: Add all files in the current directory and subdirectories
git add .

:: Commit the files
git commit -m "Initial commit"

:: Provide instructions for creating a GitHub repository and pushing changes
echo.
echo Local repository created successfully!
echo.
echo To create a GitHub repository and push your changes:
echo 1. Go to https://github.com/new
echo 2. Create a new repository (do not initialize with README, license, or .gitignore)
echo 3. Copy the URL of your new repository
echo 4. Run the following commands in this directory:
echo    git remote add origin YOUR_REPOSITORY_URL
echo    git branch -M main
echo    git push -u origin main
echo.
echo Press any key to exit...
pause >nul