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

:: Check if curl is installed
where curl >nul 2>nul
if %errorlevel% neq 0 (
    echo cURL is not installed or not in the system PATH.
    echo Please install cURL and try again.
    pause
    exit /b 1
)

:: Prompt for GitHub username and personal access token
set /p github_username=Enter your GitHub username: 
set /p github_token=Enter your GitHub personal access token: 

:: Get the name of the current folder
for %%I in (.) do set "repo_name=%%~nxI"

:: Initialize the repository
git init

:: Add all files in the current directory and subdirectories
git add .

:: Commit the files
git commit -m "Initial commit"

:: Create a new repository on GitHub using the API
echo Creating GitHub repository...
curl -H "Authorization: token %github_token%" https://api.github.com/user/repos -d "{\"name\":\"%repo_name%\"}" >nul

if %errorlevel% neq 0 (
    echo Failed to create GitHub repository. Please check your token and try again.
    pause
    exit /b 1
)

:: Add the remote origin
git remote add origin https://github.com/%github_username%/%repo_name%.git

:: Push the changes
git push -u origin master

echo Repository created and files pushed successfully!
pause