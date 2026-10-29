# ARGAS Seismic Scouting Suite & Report Generator
**Powered by Nasrullah Khan**

Comprehensive desktop suite for Saudi Aramco seismic exploration reconnaissance and automated report generation (Crew S-86 / Saudi Aramco GDAD-SL-012 compliant). Generates official Preliminary Scouting Reports matching the benchmark Saudi Aramco / ARGAS template, integrates multi-block boundary geomatics, dynamic map figures (core optional 1, 2, 3, 4, 5, 6, 8, 9 & custom maps), 300 DPI terrain pie charts, Free AI Vision captioning with an interactive review thumbnail modal, and lossless-map ~10 MB PDF size optimization into a single standalone executable.

---

## Modular Architecture & Pluggable Report Framework

The system is built on an extensible reporting engine designed for seismic survey operations:
- **`Preliminary Scouting Report for a New Prospect`** *(Current Core Focus)*: Full prospect reconnaissance, geomorphic classification, hazards, permitting, logistics, camps, and photo plates.
- **`Vib GNSS Positioning Test Report`** *(Upcoming)*: Vibrator navigation RTK positioning repeatability, dynamic lag, phase/gravity checks, and Aramco GDAD tolerance verifications.
- **`Survey Equipment Positioning Test Report`** *(Upcoming)*: Base station calibration, GNSS rover baseline tests, total station EDM calibration, and geodetic network control.
- **`VSP Survey Report`** *(Upcoming)*: Borehole/wellhead geophone array geometry, zero-offset/walkaway source positions, and time-depth curve verification.
- **`Detailed Block by Block Scouting Report`** *(Upcoming)*: Line-by-line obstacle catalog, culvert clearances, detours, and source/receiver skip maps.

---

## Core Tabs & Capabilities

### Tab 1: Project Setup & Document Metadata
- **Profile Management**: Default profile `"ARGAS Preliminary Scouting Report - Saudi Aramco"` derived from `ARGAS S86-340400001_LIDAM II Scouting Report_August 2026_Template.docx`.
- **Project Metadata**: Prospect Name, Crew Name (`Crew S-86`), Report Date, Contract Number, Contractor Name.
- **Document Control & Sign-offs**: Revision Number (`Rev 0`), Revision Date, Prepared by, Reviewed by, Approved by.
- **Distribution List (Table 1)**: Interactive recipient management (Saudi Aramco GDAD, Party Chief, Operations, QHSE).

### Tab 2: Scouting Operations, Team & Logistics
- **Scouting Calendar & Travel Dates**: Ingests travel dates and operational days with **`⚡ Auto-Scan Dates from GPX Track`** to read exact field timestamps.
- **Scouting Team Roster (Table 3)**: Interactive personnel grid (Party Chief, Chief Surveyor, Vibrator Supervisor, QHSE Officer, Permitting Officer).
- **Equipment Roster (Table 4)**: Pre-populated Aramco survey equipment catalog (4WD Vehicles, Polaris 6x6 Buggies, Trimble R12i GNSS, inReach Messengers, Soil Penetrometers, First Aid Kits).
- **Objectives of the Scout**: Checklist of standard Aramco scouting objectives with full text editing.
- **Communication Means**: Multi-network radio selection (VHF Simplex, Aramco Trunking, Satellite, GSM 4G/5G).

### Tab 3: Prospect Boundary Coordinates (Table 5)
- **Multi-Block CSV Ingestion**: Ingests boundary coordinate files with fields `Block_Name, Point_ID, Easting, Northing, Latitude, Longitude, Notes`.
- **Automated Geometry Engine**: Calculates vertex counts, closed perimeters (km), and surface areas (km²) using the Shoelace formula.
- **Table 5 Auto-Formatting**: Formats single or multi-block boundaries matching exact Saudi Aramco template specifications.
- **Sample CSV Generator**: One-click generation of `sample_prospect_boundaries.csv`.

### Tab 4: Field Tracks & Digital Notes
- **Track Log Ingestion (GPX / KML)**: Calculates total distance scouted, GPS fix count, operational time span, and spatial bounding box.
- **Digital Field Notes**: Ingests CSV, GPX waypoints, or QField mobile packages (`.qfield` / GeoPackage / GeoJSON) with an interactive searchable viewer.

### Tab 5: Dynamic Map Figures Matrix (All Optional + Custom Maps)
- **Core Standard Maps (All Optional)**:
  - `Map 1`: Regional Access & Prospect Location Map
  - `Map 2`: Prospect Boundary & Block Division Map
  - `Map 3`: Digital Elevation Model (DEM) & Topography Map
  - `Map 4`: Terrain Slope & Surface Roughness Map
  - `Map 5`: Geomorphic Terrain Classification Map
  - `Map 6`: Hazards, Sabkha & Restricted Zones Map
  - `Map 8`: Proposed Camps, Staging Yards & Water Sources Map
  - `Map 9`: Medical Facilities & Medevac Route Map
- **Custom Maps System (`+ Add Custom Map Figure`)**:
  - Add any number of custom map figures (e.g. Pipeline Corridors, Quarry Blast Zones, Flood Plains).
  - Prompts the user for:
    - Map Image File
    - Figure Number & Title
    - Target Report Section (Dropdown selection)
    - Detailed Technical Description & Operational Summary
    - **`⚡ AI Draft Description`**: One-click technical narrative drafting using Free Gemini AI.

### Tab 6: Terrain GIS & Pie Chart Generator (Section 6 & Table 6)
- **Shapefile Ingestion**: Directly parses terrain polygon shapefiles (`Terrain_Cut_SF.shp`).
- **Statistical Breakdown**: Calculates surface area in km² and percentage (%) for each geomorphic class.
- **Aramco Area Classification (Table 6)**: Automatically maps categories to Saudi Aramco Area Types (Types A through H).
- **300 DPI Pie Chart Generator**: Generates publication-grade Matplotlib pie charts automatically embedded into Section 6.
- **Section 6 Narrative Synthesis**: Generates rich geomorphic descriptions of trafficability and vibrator operations.

### Tab 7: Photos & Vision AI Captioning
- **Photo Ingestion & Enhancement**: Dehazing, unsharp masking, and color balance tuned for desert terrain.
- **Spatial Waypoint Correlator**: Computes geodesic distance to nearest field waypoint.
- **Short Descriptive Captioning**: Generates concise, template-compliant captions describing what is viewed in the frame.
- **Free AI Vision Object Identification**: Identifies foreground physical objects for ambiguous field photos.

### Tab 8: Report Assembly & Calibrated PDF (~10 MB)
- **Word Document Assembly (`python-docx`)**: Clones benchmark template, updates Tables 0–6, injects active maps, pie charts, and photo plates with 100% style preservation.
- **Word COM Automation**: Direct export to PDF using Microsoft Word COM (`ExportAsFixedFormat`) with zero formatting or font discrepancies.
- **Stream Calibration**: Automatically calibrates progressive JPEG streams to deliver a final PDF of **~10 MB** with **100% lossless GIS maps**.

---

## Running the Application

- **Standalone Executable**: Run `SeismicScoutingSuite.exe` (or `dist\SeismicScoutingSuite.exe`) — completely standalone, no external dependencies required.
- **Python Source**: `python scouting_photo_enhancer.py`.
- **Recompile**: Run `build_exe.bat` or `python -m PyInstaller --noconfirm --clean SeismicScoutingSuite.spec`.

