# Quik Field Notesing Suite — QField-Style Mobile Field Companion (PWA)

**Powered by Nasrullah Khan**  
*Field Operations Concession Scouting Standard (GDAD-SL-012 Compliant)*

---

## 🌟 Overview

The **Quik Field Notes Mobile Companion** (`mobile_web_scout/index.html`) is a streamlined, **QField-inspired** GIS field application designed for desert seismic reconnaissance on mobile devices (Samsung Galaxy Note 8, modern Androids, iPhone & iPad).

It features a full-screen GIS map canvas with high-contrast floating HUD, single-tap floating action docks, and a **"Fast & Furious" Multi-Accent Speech-to-Text Engine** tuned specifically for Middle Eastern and South Asian geophysical scouting crews.

---

## 🛰️ Fixing "GNSS Searching" — Secure Context (HTTPS) Requirement

Modern mobile operating systems (**iOS Safari** and **Android Chrome**) strictly enforce that **GPS (GNSS Location)** and **Microphone (Speech Recognition)** are restricted to **SECURE CONTEXTS (HTTPS)**.

When accessed over plain HTTP (`http://192.168...:8080`), mobile browsers block GPS hardware access for security, resulting in `GNSS: Searching`.

### ✅ How to Enable Instant GPS Fix on iPhone & Android:
1. Double-click `start_mobile_server.bat` on your laptop/workstation.
2. Note your IP address (e.g. `192.168.0.195`).
3. On your phone (Galaxy Note 8 or iPhone), open the **SECURE HTTPS URL**:
   ```
   https://<YOUR_IP>:8443
   ```
   *(e.g., `https://192.168.0.195:8443`)*
4. **Bypass the One-Time Browser Warning**:
   - **On Android Chrome**: Tap **"Advanced"** ➔ Tap **"Proceed to 192.168... (unsafe)"**.
   - **On iPhone Safari**: Tap **"Show Details"** ➔ Tap **"visit this website"** ➔ Tap **"Visit Website"**.
5. When prompted **"Allow 'Field Operations Scout' to access your location?"**, tap **"Allow"** (or **"While using the app"**).
6. **GNSS satellites and Speech-to-Text will unlock immediately!**

---

## 📱 QField-Inspired Interface

1. **Full-Screen GIS Canvas**:
   - High-resolution ESRI Satellite Imagery and OpenStreetMap tile layers.
   - Built-in map tile caching for 100% offline remote desert operations.
   - Central crosshair reticle for precise spatial feature inspection.

2. **Top Floating HUD**:
   - Live GNSS accuracy indicator (e.g. `GNSS: ±1.8m` on satellites, or `GNSS: ±25m (Net)` indoors).
   - Active Project ID badge (e.g. Area North or No Project).
   - One-tap Track Recording toggle button (`Track` / `Stop`).

3. **Floating Side Action Dock** (Large touch targets for one-handed/vehicle mount operation):
   - 🎯 **Center on GNSS**: Instantly re-centers map on surveyor position. If indoors, offers to simulate position at crosshair.
   - 🎙️ **Fast & Furious Hero Mic**: Single-tap continuous streaming voice dictation with animated audio wave visualizer.
   - 📍 **Quick Waypoint Drop**: Log obstacles (Sabkhas, Dunes, Pipelines, Camps, Hazards) at the crosshair or current GPS.
   - 📷 **Geotagged Camera**: Instant camera trigger with automatic EXIF coordinate stamping.
   - 🗺️ **Layer Switcher**: Toggle between Satellite Imagery and OpenStreetMap.
   - 📂 **Pull-up Drawer**: Slides up the Daily Field Journal and `.scoutpkg` export tools.

---

## 🎙️ "Fast & Furious" Multi-Accent Speech-to-Text Engine

The voice engine recognizes speech in real time with instantaneous word-by-word streaming:

### Supported Accents & Dialects:
- 🇸🇦 **English (Saudi & Gulf Arab Accents)** (`en-SA`): Tuned for Arabic phonetic articulation.
- 🇵🇰 **English (South Asian Accents)** (`en-IN`): Tuned for Pakistani, Indian, and Filipino field crews.
- 🇵🇰 **Roman Urdu (Voice to Roman Urdu)**: Dictate in conversational Urdu (`"yahan aage bara sand dune hai vibrator phans sakti hai"`); the engine transliterates speech into Roman Urdu English text in real time!
- 🇸🇦 **Roman Arabic (Arabizi / Franco-Arabic)**: Dictate in conversational Arabic (`"fi sabkha hena w tareeq masdood"`); the engine transliterates speech into Arabizi (`3arabizi`) Latin text in real time!
- 🇸🇦 **Native Arabic (العربية)** (`ar-SA`): Full native Arabic speech recognition.
- 🇵🇰 **Native Urdu (اردو)** (`ur-PK`): Full native Urdu speech recognition.
- 🌐 **International English** (`en-US`): Standard international English.

---

## 📦 One-Tap Desktop Synchronization (`*.scoutpkg`)

1. Tap **"📦 Export .scoutpkg"** inside the bottom drawer.
2. A single archive containing all tracks, waypoints, photos, and journal thoughts is downloaded.
3. Open the desktop **Seismic Scouting Suite**:
   - Click **"📦 Import Mobile Package..."** on the top ribbon or in **Tab 10**.
   - Select the `.scoutpkg` file.
   - All observations, photos, and GPS tracks are instantly imported into the 14 report sections!
