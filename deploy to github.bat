@echo off
setlocal enabledelayedexpansion

echo Step 1: Checking Git installation
where git >nul 2>nul
if %errorlevel% neq 0 (
    echo Git is not installed or not in the system PATH.
    echo Please install Git and try again.
    goto :error
)

echo Step 2: Checking cURL installation
where curl >nul 2>nul
if %errorlevel% neq 0 (
    echo cURL is not installed or not in the system PATH.
    echo Please install cURL and try again.
    goto :error
)

echo Step 3: Prompting for GitHub credentials
set /p github_username=Enter your GitHub username: 
set /p github_token=Enter your GitHub personal access token: 

echo Step 4: Getting repository name and adding timestamp
for %%I in (.) do set "repo_name=%%~nxI"
set "timestamp=%date:~-4,4%%date:~-10,2%%date:~-7,2%_%time:~0,2%%time:~3,2%%time:~6,2%"
set "timestamp=%timestamp: =0%"
set "unique_repo_name=%repo_name%_%timestamp%"
set "url_repo_name=%unique_repo_name: =-%"
echo Original repository name: %repo_name%
echo Unique repository name: %unique_repo_name%
echo URL-friendly repository name: %url_repo_name%

echo Step 5: Initializing local Git repository
git init
if %errorlevel% neq 0 goto :error

echo Step 6: Adding files to local repository
git add .
if %errorlevel% neq 0 (
    echo Failed to add files to Git repository.
    git status
    goto :error
)

echo Step 7: Committing files
git commit -m "Initial commit"
if %errorlevel% neq 0 (
    echo Failed to commit files.
    git status
    goto :error
)

echo Step 8: Creating GitHub repository
curl -H "Authorization: token %github_token%" https://api.github.com/user/repos -d "{\"name\":\"%url_repo_name%\"}"
if %errorlevel% neq 0 (
    echo Failed to create GitHub repository. Please check your token and try again.
    goto :error
)

echo Step 9: Adding remote origin
set "remote_url=https://github.com/%github_username%/%url_repo_name%.git"
echo Remote URL: %remote_url%
git remote add origin "%remote_url%"
if %errorlevel% neq 0 (
    echo Failed to add remote origin.
    git remote -v
    goto :error
)
echo Verifying remote...
git remote -v

echo Step 10: Ensuring we're on the main branch
git branch -M main
if %errorlevel% neq 0 (
    echo Failed to rename branch to main.
    git branch
    goto :error
)

echo Step 11: Pushing to GitHub
echo Attempting to push to %remote_url%
git push -u origin main
if %errorlevel% neq 0 (
    echo Failed to push to GitHub. Attempting to diagnose the issue...
    echo Checking remote URL:
    git remote -v
    echo Checking branch name:
    git branch
    echo Checking git status:
    git status
    echo Checking recent commits:
    git log --oneline -n 5
    goto :error
)

echo Repository created and files pushed successfully!
echo You can find your new repository at: https://github.com/%github_username%/%url_repo_name%
goto :end

:error
echo An error occurred. Please check the output above for details.
pause
exit /b 1

:end
echo Script completed.
pause