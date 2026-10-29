# Quik Field Notes — Installation & Deployment Guide
## For Samsung Galaxy Note 8, Older & Newer Android Devices, and Apple iOS

**Powered by Nasrullah Khan**  
*Professional Field Reconnaissance Standard*

---

## 📱 Hardware & OS Compatibility Matrix

| Device Category | Supported Operating Systems | Key Hardware Features |
|---|---|---|
| **Samsung Galaxy Note 8** | **Android 7.1.1 (Nougat), Android 8.0/8.1 (Oreo), Android 9.0 (Pie)** | Exynos 8895 / Snapdragon 835, 64-bit & 32-bit ABI, MultiDex enabled, Legacy External Storage enabled |
| **All Other Android Devices** | **Android 5.0 (Lollipop) through Android 15+** | Full ABI compatibility (`arm64-v8a`, `armeabi-v7a`, `x86_64`) |
| **Apple iPhone & iPad** | **iOS 13.0 through iOS 18+** | iPhone 6s/7/8/X/11/12/13/14/15/16, iPad Air/Pro/Mini |

---

## 🚀 Part 1: Android Deployment (Samsung Galaxy Note 8 & All Androids)

### Method 1: Instant Zero-Install Deployment (Fastest — 30 Seconds!)
Because field scouts often operate in desert base camps without developer laptops, the companion is available as a **Progressive Web App (PWA)** that installs directly onto the Galaxy Note 8 home screen as a standalone application:
1. Double-click `mobile_web_scout/start_mobile_server.bat` on your camp workstation or laptop.
2. Note your IP address shown on screen (e.g. `192.168.1.50` or mobile hotspot `192.168.43.1`).
3. On your **Galaxy Note 8** (connected to the same Wi-Fi or phone hotspot):
   - Open **Samsung Internet** or **Google Chrome**.
   - Navigate to `http://<YOUR_IP>:8080`.
   - Tap the three dots menu (or bottom bar) and select **"Add page to" ➔ "Home screen"** (or **"Install app"**).
4. The **Quik Field Notes** icon appears on the Galaxy Note 8 home screen, launching full-screen without any browser address bars, with offline GIS map caching, speech recognition, and GPS logging!

---

### Method 2: Building & Installing the Native Android APK

#### Configuration Highlights in `mobile_app/android/app/build.gradle`:
- `minSdkVersion 21`: Guarantees seamless execution on Samsung Galaxy Note 8 (API 24–28) as well as modern Android 14/15 phones.
- `multiDexEnabled true`: Prevents the 64K method index limit on Android 7/8/9 devices.
- `requestLegacyExternalStorage="true"`: Grants unhindered file system access so `.scoutpkg` packages, photos, and GPX files can be saved and transferred freely.

#### Steps to Compile the Release APK:
1. On a machine with Flutter SDK:
   ```bash
   cd mobile_app
   flutter pub get
   flutter build apk --release --split-per-abi=false
   ```
   *(Or simply double-click `mobile_app/build_apk.bat`)*
2. The output file is generated at:
   ```
   mobile_app/build/app/outputs/flutter-apk/app-release.apk
   ```
3. Transfer `app-release.apk` to your Galaxy Note 8 via USB cable, WhatsApp, or Google Drive.
4. On the Galaxy Note 8:
   - Tap `app-release.apk` in **My Files**.
   - If prompted, toggle **"Allow from this source"** under Settings ➔ Install unknown apps.
   - Tap **Install**.

---

## 🍎 Part 2: Apple iOS Deployment (iPhone & iPad)

### Method 1: Instant iOS Safari Installation (Recommended)
1. Open `http://<YOUR_IP>:8080` in **Safari** on your iPhone or iPad.
2. Tap the **Share** button (box with an arrow pointing up).
3. Scroll down and tap **"Add to Home Screen"**.
4. Tap **Add**. The app will run full-screen, utilizing Apple's native speech recognition and GPS framework 100% offline.

---

### Method 2: Building the Native iOS App Bundle via Xcode
1. In `mobile_app`:
   ```bash
   flutter pub get
   flutter build ios --release --no-codesign
   ```
2. Open the project in Xcode:
   ```bash
   open ios/Runner.xcworkspace
   ```
3. Under **Signing & Capabilities**, select your Apple Developer account / Team.
4. Connect your iPhone via USB, select it as the build target, and click **Run** (or select **Product ➔ Archive** to export an Ad-Hoc / Enterprise IPA).
5. File sharing is enabled (`UIFileSharingEnabled = true` in `Info.plist`), allowing scouts to copy `.scoutpkg` archives straight out of the iOS **Files** app!

---

## ☁️ Part 3: Automated Free Cloud Compilation (GitHub Actions)

A zero-setup automated CI/CD pipeline is pre-configured in `.github/workflows/build_mobile.yml`:
1. Push this repository to GitHub.
2. Under the **Actions** tab, select **"Build Quik Field Notes"** and click **Run workflow**.
3. In under 5 minutes, GitHub's cloud builders automatically compile:
   - `Quik Field Notes_Seismic_Scout_Android_Universal.apk` (Tested for Note 8 and all Androids)
   - `Quik Field Notes_Seismic_Scout_iOS.ipa` (For iPhone & iPad)
4. Download the ready-to-install packages straight from GitHub!

---

## 📦 Synchronizing with Desktop Seismic Scouting Suite

1. Record voice thoughts, waypoints, photos, and tracks in the field on your Galaxy Note 8 or iPhone.
2. Tap **"Export .scoutpkg"** on the mobile device.
3. Transfer the `.scoutpkg` file to the camp desktop workstation via USB, Wi-Fi, or WhatsApp.
4. On the desktop **Seismic Scouting Suite**:
   - Click **"📦 Import Mobile Package..."** on the top ribbon or in **Tab 10**.
   - Select the `.scoutpkg` file.
   - Photos, waypoints, tracks, and speech notes automatically populate their respective Field Operations report sections!

