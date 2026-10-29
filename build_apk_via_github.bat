@echo off
title Cloud APK Generator via GitHub Actions
echo =========================================================================
echo Quik Field Notes — Cloud Mobile APK Generator
echo Powered by Nasrullah Khan
echo =========================================================================
echo.
echo This script pushes the mobile codebase to GitHub to trigger the automated
echo cloud build pipeline on GitHub Actions (Ubuntu cloud runner).
echo.
echo Result:
echo - Quik_Field_Notes_Universal.apk (Built with minSdkVersion 21 for Galaxy Note 8)
echo - Quik_Field_Notes_iOS.ipa (For iPhone)
echo =========================================================================
echo.

cd /d "%~dp0"

where git >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Git is not installed on PATH.
    pause
    exit /b 1
)

:: Initialize Git if not yet done
if not exist ".git" (
    echo [*] Initializing local Git repository...
    git init -b main
    git config user.name "Nasrullah Khan"
    git config user.email "nas31952@gmail.com"
)

:: Stage files and commit
echo [*] Staging mobile app and GitHub workflow files...
git add .gitignore
git add mobile_app/
git add mobile_web_scout/
git add .github/
git add build_apk_via_github.bat

git commit -m "Update Quik Field Notes Mobile with QField UI, Heading Navigation, Overlays, Digitizing, and Multi-Format Exports" >nul 2>&1

:: Check for remote origin
git remote get-url origin >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo =========================================================================
    echo [ACTION REQUIRED] Connect your GitHub Repository
    echo =========================================================================
    echo 1. Go to https://github.com/new in your browser.
    echo 2. Set Repository name to: quik-field-notes (Public recommended for free builds)
    echo 3. Do NOT check "Add a README" or ".gitignore".
    echo 4. Click "Create repository".
    echo 5. Copy the HTTPS repository URL (e.g. https://github.com/nas31952/quik-field-notes.git)
    echo =========================================================================
    echo.
    set /p REPO_URL="Paste your GitHub Repository URL here: "
    if "%REPO_URL%"=="" (
        echo [ERROR] No URL provided. Aborting.
        pause
        exit /b 1
    )
    git remote add origin %REPO_URL%
    git branch -M main
)

echo.
echo [*] Pushing codebase to GitHub to start Cloud APK build...
git push -u origin main

if %ERRORLEVEL% EQU 0 (
    echo.
    echo =========================================================================
    echo [SUCCESS] Codebase pushed successfully to GitHub!
    echo =========================================================================
    echo GitHub Actions cloud runner has started building your APK right now!
    echo.
    echo The build takes approximately 3 to 4 minutes.
    echo Once finished, you can download Quik_Field_Notes_Universal.apk directly:
    echo 1. Under the "Actions" tab on your GitHub repo.
    echo 2. Under the "Releases" section.
    echo =========================================================================
    
    :: Attempt to open the actions page
    for /f "tokens=*" %%a in ('git remote get-url origin') do set FULL_URL=%%a
    set ACTIONS_URL=%FULL_URL:.git=%/actions
    start %ACTIONS_URL%
) else (
    echo.
    echo [!] Push encountered an issue. Check your GitHub repository permissions or network.
)

pause
