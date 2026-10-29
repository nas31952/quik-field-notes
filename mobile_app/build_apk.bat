@echo off
title Build Quik Field Notes APK (Galaxy Note 8 & All Android)
echo =========================================================================
echo Building Universal Release APK for Samsung Galaxy Note 8 and All Android
echo Quik Field Notes
echo Powered by Nasrullah Khan
echo =========================================================================
echo.
echo Checking Flutter SDK...
where flutter >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Flutter SDK not found on PATH.
    echo Please install Flutter SDK from https://flutter.dev and add to PATH.
    echo Or use the GitHub Actions automated cloud build workflow:
    echo .github/workflows/build_mobile.yml
    pause
    exit /b 1
)

echo.
echo [1/3] Getting Flutter packages...
call flutter pub get

echo.
echo [2/3] Building Universal Release APK (minSdkVersion 21, MultiDex enabled)...
call flutter build apk --release --split-per-abi=false

echo.
if exist "build\app\outputs\flutter-apk\app-release.apk" (
    echo =========================================================================
    echo [SUCCESS] Universal Android APK built successfully!
    echo Output: build\app\outputs\flutter-apk\app-release.apk
    echo.
    echo Compatible with:
    echo - Samsung Galaxy Note 8 (Android 7.1.1, 8.0, 9.0 Pie)
    echo - All older and newer Android devices (Android 5.0 to Android 15)
    echo =========================================================================
) else (
    echo [ERROR] Build failed. Please check Gradle output above.
)
pause

