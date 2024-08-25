@echo off
setlocal enabledelayedexpansion

:: Enable command echoing for debugging
@echo on

echo Step 1: Checking Git installation
where git
if %errorlevel% neq 0 (
    echo Git is not installed or not in the system PATH.
    echo Please install Git and try again.
    pause
    exit /b 1
)

echo Step 2: Checking cURL installation
where curl
if %errorlevel% neq 0 (
    echo cURL is not installed or not in the system PATH.
    echo Please install cURL and try again.
    pause
    exit /b 1
)

echo Step 3: Prompting for GitHub credentials
set /p github_username=Enter your GitHub username: 
set /p github_token=Enter your GitHub personal access token: 

echo Step 4: Getting repository name
for %%I in (.) do set "repo_name=%%~nxI"
echo Repository name: %repo_name%

echo Step 5: Initializing local Git repository
git init
if %errorlevel% neq 0 (
    echo Failed to initialize Git repository.
    pause
    exit /b 1
)

echo Step 6: Adding files to local repository
git add .
if %errorlevel% neq 0 (
    echo Failed to add files to Git repository.
    git status
    pause
    exit /b 1
)

echo Step 7: Committing files
git commit -m "Initial commit"
if %errorlevel% neq 0 (
    echo Failed to commit files.
    git status
    pause
    exit /b 1
)

echo Step 8: Creating GitHub repository
curl -H "Authorization: token %github_token%" https://api.github.com/user/repos -d "{\"name\":\"%repo_name%\"}"
if %errorlevel% neq 0 (
    echo Failed to create GitHub repository. Please check your token and try again.
    pause
    exit /b 1
)

echo Step 9: Adding remote origin
git remote add origin https://github.com/%github_username%/%repo_name%.git
if %errorlevel% neq 0 (
    echo Failed to add remote origin.
    git remote -v
    pause
    exit /b 1
)

echo Step 10: Ensuring we're on the main branch
git branch -M main
if %errorlevel% neq 0 (
    echo Failed to rename branch to main.
    git branch
    pause
    exit /b 1
)

echo Step 11: Pushing to GitHub
git push -u origin main -v
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
    
    echo Please check the output above for any issues.
    pause
    exit /b 1
)

echo Repository created and files pushed successfully!
pause

:: Disable command echoing
@echo off