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

:: Prompt for the GitHub repository name
set /p repo_name=Enter the name for your GitHub repository: 

:: Create a new repository on GitHub using the GitHub CLI
where gh >nul 2>nul
if %errorlevel% neq 0 (
    echo GitHub CLI is not installed or not in the system PATH.
    echo Please install GitHub CLI and try again.
    echo You can manually create a repository on GitHub and push your changes.
    pause
    exit /b 1
)

:: Create the repository and push the changes
gh repo create %repo_name% --public --source=. --remote=origin --push

echo Repository created and files pushed successfully!
pause