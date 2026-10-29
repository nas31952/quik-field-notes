# Quik Field Notes — Flutter Cross-Platform Client

**Powered by Nasrullah Khan**  
*Professional Field Reconnaissance Standard*

---

## 🌟 Overview

The **Quik Field Notes** is a native cross-platform application for **Android** and **iOS** built with Flutter.

Featuring a simplified **QField-inspired full-screen GIS canvas** and a **"Fast & Furious" Multi-Accent Speech-to-Text Engine**, it allows field scouts to effortlessly record observations, GPS tracks, waypoints, and photos even while driving across desert concessions.

---

## 📱 QField-Inspired Architecture

- **Full-Screen GIS View**: Map canvas as primary UI (`flutter_map`) with satellite imagery and OpenStreetMap.
- **Top HUD**: Live GNSS precision badge (`±2.1m`), active Project ID, and one-tap track recording toggle.
- **Side Action Dock**: Large, glove-friendly floating action buttons for GNSS centering, waypoint drop, geotagged photos, and map layer switching.
- **Hero Microphone Button**: Floating high-visibility mic button that triggers streaming low-latency voice dictation with visual feedback.
- **Sliding Drawer / Bottom Sheet**: Pulls up to reveal the voice transcription console, accent selector, field journal feed, and `.scoutpkg` export button.

---

## 🎙️ "Fast & Furious" Multi-Accent Speech-to-Text Engine

Tuned specifically for multicultural seismic crews operating in Saudi Arabia and the Middle East:

### Supported Language & Accent Modes:
1. 🇸🇦 **English (Saudi & Gulf Arab Accents)** (`en_SA`): Trained on Middle Eastern English articulation.
2. 🇵🇰 **English (South Asian Accents)** (`en_IN`): Trained on South Asian (Pakistani, Indian) English phrasing.
3. 🇵🇰 **Roman Urdu (Voice to Roman Urdu)**: Dictate in Urdu (`"aage sabkha hai aur pipeline road block hai"`); the engine transliterates speech into Roman Urdu English text on the fly!
4. 🇸🇦 **Roman Arabic (Arabizi / Franco-Arabic)**: Dictate in Arabic (`"fi sabkha kabeera w tareeq masdood"`); the engine transliterates into Arabizi (`3arabizi`) Latin text on the fly!
5. 🇸🇦 **Native Arabic (العربية)** (`ar_SA`): Full native Arabic speech recognition.
6. 🇵🇰 **Native Urdu (اردو)** (`ur_PK`): Full native Urdu speech recognition.
7. 🌐 **International English** (`en_US`): General international English.

### Real-Time Seismic Lexicon & Accent Normalizer:
Automatically corrects phonetically confused field words into standardized Field Operations seismic terms:
- `"sabka"` / `"sabkah"` ➔ **Sabkha**
- `"wibrator"` / `"vibrater"` ➔ **Vibrator**
- `"jabal"` / `"gebel"` ➔ **Jebel**
- `"pipe line"` / `"utility line"` ➔ **Pipeline Corridor**
- `"dikaaka"` / `"dikaka"` ➔ **Sand Dikaka**
- `"mustashfa"` / `"aspatal"` ➔ **Hospital / Medevac**
- `"tasreeh"` / `"clearance"` ➔ **Permitting Clearance**
- `"khatar"` / `"danger"` ➔ **HSE Hazard**
- `"nefood"` / `"nafud"` ➔ **Sand Dunes**

---

## 🚀 Building & Deployment

### 1. Prerequisites
- Flutter SDK 3.19+ ([https://flutter.dev](https://flutter.dev))
- Android SDK 34+ (for Android APK build)
- Xcode 15+ (for iOS build)

### 2. Android Build:
```bash
cd D:\Development\USSIP\tools\ScoutingPhotoEnhancer\mobile_app
flutter pub get
flutter build apk --release
```
The resulting APK (`build/app/outputs/flutter-apk/app-release.apk`) can be installed directly onto any Android phone.

### 3. iOS Build:
```bash
flutter build ios --release
```
Open `ios/Runner.xcworkspace` in Xcode, select your Apple Developer signing team, and deploy to your connected iPhone.

---

## 📦 Package Synchronization (`*.scoutpkg`)
At the end of a scouting trip, tap **"Export .scoutpkg"** to generate a single standardized package and import it directly into the desktop **Seismic Scouting Suite** (`Tab 10` or top ribbon).
