"""
Comprehensive Built-in Help System & Function Guide for ARGAS Seismic Scouting Suite
Provides documentation on every feature, calculation, and workflow.
"""

HELP_TOPICS = {
    "Overview & Architecture": """
================================================================================
ARGAS SEISMIC SCOUTING SUITE & REPORT GENERATOR — USER MANUAL
================================================================================
Powered by Nasrullah Khan
Saudi Aramco Concession Scouting Standard (Crew S-86 / GDAD-SL-012 Compliant)

The ARGAS Seismic Scouting Suite is a professional desktop engineering tool
specifically designed for geophysical survey reconnaissance, geomatics,
HSE risk assessment, and publication-ready report production.

KEY ARCHITECTURAL HIGHLIGHTS:
1. Pluggable Reporting Engine: Built on a modular architecture supporting:
   • Preliminary Scouting Report for a New Prospect (Current Active Focus)
   • Vib GNSS Positioning Test Report (Future Module)
   • Survey Equipment Positioning Test Report (Future Module)
   • VSP Survey Report (Future Module)
   • Detailed Block-by-Block Scouting Report (Future Module)
2. Exact Template Fidelity: Injects data directly into the benchmark
   Saudi Aramco / ARGAS Word document (.docx) template preserving 100% of
   formatting, font hierarchies, tables, headers, and footers.
3. Lossless Maps & ~10 MB PDF Calibration: Exports print-quality PDFs via
   Word COM Automation, exempting all GIS maps and vector diagrams from lossy
   compression while calibrating field photo progressive JPEG streams.
4. Multimodal Free AI Support: Free Gemini API integration for visual photo
   captioning, custom map descriptions, and regional fact-checking.
""",

    "Tab 1: Project Setup & Metadata": """
================================================================================
TAB 1: PROJECT SETUP & METADATA (COVER, TABLE 0 & TABLE 1)
================================================================================

PURPOSE:
Defines project identity, document control revision tracking, sign-offs, and
client distribution lists matching Saudi Aramco GDAD standard format.

FUNCTIONS & CONTROLS:
• Report Profile Dropdown: Switch between saved survey profiles or create custom
  templates. Default: "ARGAS Preliminary Scouting Report - Saudi Aramco".
• Save Profile Button: Serializes current settings to a permanent JSON file in
  the profiles/ directory.
• Prospect Name: Official Saudi Aramco exploration prospect or 3D block name.
• Crew Name: Assigned seismic crew code (e.g. Crew S-86).
• Report Date: Calendar month and year (e.g. October 2026).
• Contract Number: Saudi Aramco contract/work-order identifier (e.g. 340400001).
• Revision Control: Revision No (Rev 0, Rev 1), Revision Date, Prepared by,
  Reviewed by, and Approved by names/titles.
• Distribution List (Table 1): Full recipient list including Saudi Aramco GDAD
  Representatives, ARGAS Operations Management, and Field Party Chiefs.
""",

    "Tab 2: Scouting Operations & Team": """
================================================================================
TAB 2: SCOUTING OPERATIONS & TEAM (TABLE 3 & TABLE 4)
================================================================================

PURPOSE:
Dynamically manages the field personnel roster, survey equipment assets,
scouting calendar dates, objectives, and radio communication channels.

FUNCTIONS & CONTROLS:
• Date Travel to Area: Date crew mobilized from base camp to prospect.
• Scouting Dates: Calendar range and total operational field days.
• ⚡ Auto-Scan Dates from GPX Track: Automatically scans imported GPS track logs,
  extracts UTC timestamps, and populates exact calendar dates and days.
• Scouting Team Roster (Table 3):
  - [ + Add Team Member ]: Prompts for Name, Title, and Operational Scope.
  - [ ✏ Edit Member ]: Modifies selected personnel details.
  - [ 🗑 Delete Member ]: Removes personnel from Table 3.
  - [ 🔄 Reset Defaults ]: Restores standard ARGAS Crew S-86 team roster.
• Equipment Roster (Table 4):
  - [ + Add Equipment ]: Prompts for Item, Type/Model, Qty, Fleet No, Remark.
  - [ ✏ Edit Equipment ]: Modifies selected equipment asset.
  - [ 🗑 Delete Equipment ]: Removes asset from Table 4.
• Objectives of the Scout (Section 4): Standard Saudi Aramco reconnaissance
  scopes (boundary checks, sabkha probing, pipeline standoffs, camps).
• Communication Means (Section 5): Radio frequencies (VHF Simplex, Aramco
  Digital Trunking, Satellite, GSM 4G/5G).
""",

    "Tab 3: Boundary Coordinates (Table 5)": """
================================================================================
TAB 3: PROSPECT BOUNDARY COORDINATES & GEOMETRICS (TABLE 5)
================================================================================

PURPOSE:
Ingests single or multi-block concession boundary coordinates, calculates
geometric perimeters and surface areas, and builds Table 5.

INPUT CSV SPECIFICATION:
Create a comma-separated (CSV) file with the following headers:
Block_Name, Point_ID, Easting, Northing, Latitude, Longitude, Notes

EXAMPLE:
Block-1, P01, 712543.20, 2987654.10, 26.987654, 49.123456, NW Corner
Block-1, P02, 735412.80, 2987654.10, 26.987654, 49.354123, NE Corner
Block-2, P01, 695432.10, 2950123.40, 26.645321, 48.954321, Corner 1

FUNCTIONS & CONTROLS:
• Browse...: Selects the boundary coordinate CSV or TXT file.
• Sample CSV Template: Automatically generates 'sample_prospect_boundaries.csv'.
• ▶ Parse & Calculate Geometry:
  - Groups coordinates by concession block.
  - Computes polygon boundary closure.
  - Calculates perimeter in kilometers (km).
  - Calculates area in square kilometers (km²) using the Shoelace formula.
  - Formats Table 5 in the Word report with all blocks, corners, and totals.
""",

    "Tab 4: Field Tracks & Notes": """
================================================================================
TAB 4: FIELD TRACKS & DIGITAL NOTES
================================================================================

PURPOSE:
Ingests and verifies spatial coverage of all scouted vehicle tracks and
digital observation notes.

FUNCTIONS & CONTROLS:
• Scouted GPS Track File (*.gpx, *.kml):
  - Browse and analyze vehicle GPX/KML track files.
  - Calculates total kilometers scouted across the survey area.
  - Computes spatial bounding box (min/max latitude and longitude).
• Digital Field Notes (CSV / GPX / QField Package):
  - Ingests waypoint notes recorded during field traverses.
  - Displays Waypoint ID, Coordinates, and Observation Remarks in an
    interactive, searchable table.
  - Notes are automatically correlated with photos during curation.
""",

    "Tab 5: Map Figures Matrix": """
================================================================================
TAB 5: MAP FIGURES MATRIX (ALL OPTIONAL + CUSTOM MAPS)
================================================================================

PURPOSE:
Configures all report map graphics. Every map is completely optional. If a
map is omitted, no empty frames or broken placeholders are generated.

CORE STANDARD MAPS (OPTIONAL):
• Map 1: Regional Access and Road Network to Prospect (Section 1 / Section 3)
• Map 2: Survey Prospect Boundary and Block Division Map (Section 1 / Section 4)
• Map 3: Digital Elevation Model (DEM) & Topography Map (Section 6)
• Map 4: Ground Slope Gradient and Surface Roughness Map (Section 6)
• Map 5: Geomorphic Surface Terrain Classification Map (Section 6)
• Map 6: Operational Terrain Hazards & Sabkha Geofences (Section 11)
• Map 8: Proposed Main Seismic Camp, Fly Camps & Water Points (Section 9)
• Map 9: Emergency Medical Evacuation Routes & Hospital Distance Map (Section 10)

CUSTOM MAPS ENGINE:
• [ + Add Custom Map Figure ]: Adds any user-specified map (e.g. Pipeline
  Corridors, Blast Radius Buffers, Hydrology/Flood Plains).
• Custom Map Dialog prompts for:
  - Map Image File (*.png, *.jpg, *.tif)
  - Figure Number & Title
  - Target Report Section (Dropdown selection)
  - Technical Description & Operational Summary
  - ⚡ AI Draft Description: One-click drafting using Free Gemini AI.
""",

    "Tab 6: Terrain GIS & Pie Chart": """
================================================================================
TAB 6: TERRAIN GIS CLASSIFICATION & 300 DPI PIE CHART (SECTION 6)
================================================================================

PURPOSE:
Processes ESRI polygon shapefiles (e.g. Terrain_Cut_SF.shp), calculates exact
geomorphic areas and percentages, generates publication-grade pie charts, and
writes Section 6.

FUNCTIONS & CONTROLS:
• Terrain Polygon Shapefile (*.shp): Selects the input GIS vector layer.
• Descriptor Field Selector: Automatically detects the classification column
  (e.g. 'Descriptor', 'Class', 'Terrain') or allows user manual selection.
• ▶ Run GIS Classification & Pie Chart:
  - Computes polygon areas directly from vertex geometry using the Shoelace
    formula in projected UTM square meters or geographic coordinates.
  - Automatically identifies all distinct terrain classes.
  - Generates a 300 DPI Matplotlib corporate pie chart saved as PNG.
  - Displays live thumbnail preview in UI.
  - Automatically maps each class to Saudi Aramco Area Types (Types A to H).
  - Synthesizes comprehensive narrative text for Section 6.
""",

    "Tab 7: Remoteness & Contractual Areas (Sec 7)": """
================================================================================
TAB 7: REMOTENESS & CONTRACTUAL OPERATIONAL AREAS (SECTION 7 & TABLE 6)
================================================================================

PURPOSE:
Calculates Saudi Aramco contractual terrain payment classifications (Types A
through H) and logistical remoteness parameters for Section 7 and Table 6.

CONTRACTUAL TERRAIN TYPES:
• Type A: Oil/Gas infrastructure, pipelines, plants (50m GDAD buffers)
• Type B: Plains, undulating sand sheets, gravel flats, sand dikaka
• Type C: Moving sand dunes, steep slip faces (Dune vibrator tires)
• Type D: Escarpments, rugged cliffs, jebels (Climbing lines & detours)
• Type E: Deep sand / Rub' al Khali mega-dune topography
• Type F: Municipalities, villages, residential settlements (100m standoff)
• Type G: Agriculture, date palm plantations, irrigated enclosures
• Type H: Coastal and inland sabkhas, high water table salt crusts

FUNCTIONS & CONTROLS:
• Contractual Shapefile Picker: Ingests the Aramco area boundary layer.
• Remoteness Zone Dropdown: Selects operational remoteness category.
• Base Distance (km): Distance from logistical supply hub to camp.
• Updates Table 6 (Operational Area Classification) and Section 7 narrative.
""",

    "Tab 8: Photos & Vision AI": """
================================================================================
TAB 8: PHOTOS & VISION AI CAPTIONING (PHOTO PLATES)
================================================================================

PURPOSE:
Curates high-resolution field photos, clears desert haze, tags GPS coordinates,
identifies objects using Free AI Vision, and manages non-geotagged photos.

FUNCTIONS & CONTROLS:
• Photos Folder: Source directory containing raw field photographs.
• Target Photo Count: Desired curated quota (default: 60).
• Enhancement Checkboxes: Dehazing, unsharp masking, and color tuning.
• Geotag Status Column:
  - ✔ Geotagged: Green indicator showing GPS latitude and longitude.
  - ✖ NO GPS: Highlighted in red/orange warning text.
• Checkbox: [x] Include Non-Geotagged Photos in Report:
  - If checked, non-geotagged photos are appended at the very end of the
    photo section under a dedicated sub-heading.
  - If unchecked, non-geotagged photos are excluded from the document.
• [ 🗑 Reject Selected Photo ]: Removes photo from report generation.
• [ 🔍 Review & Edit Photo Captions ]: Opens the interactive PhotoReviewDialog
  displaying 540x360 image thumbnails, metadata, and live caption editor.
• ⚡ AI Re-Generate: Calls Free Gemini Vision to re-describe the photo.
""",

    "Tab 9: Report Assembly & PDF (~10MB)": """
================================================================================
TAB 9: REPORT ASSEMBLY & CALIBRATED PDF EXPORT (~10 MB)
================================================================================

PURPOSE:
Assembles the complete Microsoft Word document (.docx) preserving 100% template
fidelity, and exports a print-quality PDF calibrated to ~10 MB.

FUNCTIONS & CONTROLS:
• Template Word Doc (*.docx): Master benchmark template (LIDAM II Template).
• Output Directory: Destination folder for generated DOCX and PDF deliverables.
• Free Gemini API Key: Optional key for multi-modal vision and AI drafting.
• ▶ Generate Complete Word Report (*.docx):
  - Updates Cover, Table 0, Table 1, Table 2, Table 3, Table 4, Table 5, Table 6.
  - Updates Section 4 (Objectives), Section 5 (Comms), Section 6 (Terrain).
  - Updates Section 7 (Remoteness & Contractual Categories).
  - Enriches Section 11 (10 terrain obstacles subsections).
  - Enriches Section 12 (Saudi Aramco GDAD-SL-012 HSE Risk Matrix Table).
  - Enriches Section 13 (Conclusion & Recommendations).
  - Injects active maps and 300 DPI terrain pie chart.
  - Appends 2-per-row photo plates.
  - Injects "Powered by Nasrullah Khan" in cover and footers.
• 📄 Export Calibrated PDF (~10 MB):
  - Word COM Automation export (wdExportOptimizeForPrint).
  - Maps 1–12 and vector graphics preserved 100% lossless.
  - Field photos stream-calibrated to deliver a final file size of ~10 MB.
• 📁 Open Output Folder: Opens destination directory in Windows Explorer.
"""
,

    "Tab 10: Daily Field Journal & Mobile Sync": """
================================================================================
TAB 10: DAILY FIELD JOURNAL & MOBILE COMPANION SYNCHRONIZATION
================================================================================

PURPOSE:
Enables continuous, on-the-fly field thought recording during scouting operations.
Scouts can record very rough notes, fragmented impressions, or voice dictations
at any moment during the day. The integrated AI semantic engine continuously
analyzes, categorizes, and organizes these entries into the 14 standard Saudi
Aramco report sections, automatically pre-filling section prompts for final report
synthesis.

KEY CAPABILITIES:
1. Continuous Rough Thought Capture:
   • Type or paste rough field thoughts, voice transcripts, or bullet points.
   • Optional GPS coordinates (Latitude/Longitude) for spatial referencing.
   • Timestamped automatically to maintain an auditable chronological field log.

2. AI Semantic Categorization:
   • Automatically evaluates the content of each entry against a high-precision
     geophysical, HSE, logistics, and terrain vocabulary taxonomy.
   • Assigns each observation to its matching report section (e.g. Access Routes,
     Permitting & Security, Surface Obstacles, Campsite Logistics, Hazards).
   • Displays confidence score and allows manual re-categorization if desired.

3. Section Prompt Pre-filling & Synthesis:
   • [ ⚡ Pre-fill Section Prompts ]: Synthesizes all field thoughts for each
     section into organized, structured section prompts.
   • Directly feeds into Strategy 4 (Full AI Report Synthesis) and Strategy 7
     (Interactive Section Prompts Dialog), ensuring zero field observations are lost.

4. Mobile Companion Synchronization (*.scoutpkg):
   • [ 📦 Import Mobile Package... ]: Seamlessly unzips and ingests field packages
     created by mobile scouts in the field.
   • Automatically unpacks photos into project photo directories, loads GPX
     tracks and waypoints, and merges journal thoughts into Tab 10.
   • [ 📤 Export Field Package... ]: Bundles desktop project data into a portable
     package for handoff or backup.

5. Field Companion Apps (Included):
   • Instant Offline Web PWA (mobile_web_scout/index.html):
     - Runs directly on iOS Safari and Android Chrome without installation.
     - Live speech-to-text dictation, offline map caching, waypoint capture,
       and one-tap *.scoutpkg export.
   • Flutter Cross-Platform Mobile App (mobile_app/):
     - Full native Android APK & iOS application codebase with offline tile
       caching, background GPS tracking, and voice note transcription.
""",

    "Report Template Processing Strategies": """
================================================================================
REPORT TEMPLATE PROCESSING STRATEGIES & AI CO-AUTHORING
================================================================================

The suite provides 7 specialized operational strategies accessible via the top
strategy ribbon dropdown and Tab 9:

1. COPY TEMPLATE AS-IS (SIZE REDUCTION & OPTIMIZATION ONLY) [DEFAULT]
   - Clones all template text, tables, figures, and styling verbatim.
   - Non-destructive compression on embedded media targeting the strict ~10MB PDF limit.
   - No editorial content or numbers are altered. Ideal for archiving and publishing
     already verified and finalized documents.

2. VERIFY CONTENT & HIGHLIGHT CONCERNS IN YELLOW (NO UPDATES)
   - Read-only QA / Peer Review Mode.
   - Scans template text, dates, coordinates, and tables against active project data.
   - Highlights discrepancies, outdated numbers, and unverified statements in YELLOW.
   - Original text is preserved intact so technical reviewers can inspect differences.

3. UPDATE CONTENT & HIGHLIGHT CHANGES (SYNCHRONIZE PROJECT DATA)
   - Synchronizes Table 0-5, title cover, and metadata with active project parameters.
   - Applies change-tracking visual highlights (BRIGHT GREEN / CYAN) to all updated
     cells and paragraphs so reviewers can instantly spot automated changes.

4. STYLE & HEADINGS ONLY (FULL AI REPORT SYNTHESIS FROM ATTACHED FILES)
   - Preserves template styling, branding, and standard headings.
   - Executes multi-source AI research synthesizing text from attached coordinates,
     GIS terrain metrics, Aramco area breakdowns, field GPS tracks, and photo tags.
   - If no data or user prompt exists for a section, leaves the heading and inserts:
     [ACTION REQUIRED: This section needs to be written by the user. No relevant field
      measurements or attached data files were detected for this topic.]

5. EXECUTIVE SUMMARY & KEY SURVEY KPI DASHBOARD ONLY
   - Generates a high-level executive dashboard table summarizing prospect area,
     blocks, terrain distribution, crew roster, and geodetic reference.
   - Ideal for executive management, weekly client briefings, and operational dashboards.

6. SAUDI ARAMCO & OGP STANDARDS COMPLIANCE AUDIT (GDAD-SL-012R03)
   - Evaluates survey geometry and document completeness against 8 core GDAD rules:
     * Minimum 50m pipeline standoff buffer
     * Maximum 250m well tie deviation
     * Maximum 5° line deflection angle at dogleg turns
     * Full-fold boundary polygon closure
     * Ain el Abd 1970 / UTM Zone 39N coordinate datum verification
     * 3-tier document revision sign-offs (Prepared, Reviewed, Approved)
     * 100% terrain classification coverage
     * Georeferenced field photo documentation
   - Generates a styled Compliance Verification Matrix table with green/red status cells.

7. INTERACTIVE AI SECTION CO-AUTHORING & REVIEW WIZARD
   - Opens the Section Prompts Dialog allowing field engineers and geophysicists
     to provide specific guidance, notes, or bullet points for each of the 14 sections.
   - Synthesizes user guidance with attached field data into publication-ready prose.

INTERACTIVE SECTION PROMPTS DIALOG:
   - Click "Configure Section Prompts..." on the top ribbon or in Tab 9.
   - Select any section to view its auto-detected sources and input field notes.
   - Click "Test AI Draft" for an instant live synthesis preview.
"""
}


class HelpDialog:
    """Displays a modern, searchable user manual and function guide."""
    def __init__(self, parent):
        import tkinter as tk
        from tkinter import ttk, scrolledtext

        self.win = tk.Toplevel(parent)
        self.win.title("ARGAS Seismic Scouting Suite — Function Guide & User Manual")
        self.win.geometry("960x700")
        self.win.minsize(800, 560)
        self.win.configure(bg="#0A0F1D")
        self.win.transient(parent)

        container = ttk.Frame(self.win, padding=12)
        container.pack(fill="both", expand=True)

        top = ttk.Frame(container)
        top.pack(fill="x", pady=(0, 8))
        ttk.Label(top, text="📘 Complete Function Guide & User Manual", font=("Segoe UI", 13, "bold"), foreground="#38BDF8").pack(side="left")
        ttk.Label(top, text="⚡ Powered by Nasrullah Khan", font=("Segoe UI", 9, "bold italic"), foreground="#38BDF8").pack(side="right")

        split = ttk.Frame(container)
        split.pack(fill="both", expand=True)

        # Topic Selector
        left = ttk.LabelFrame(split, text=" Guide Topics ", padding=6)
        left.pack(side="left", fill="y", padx=(0, 6))

        self.topic_listbox = tk.Listbox(left, bg="#0F172A", fg="#F8FAFC", selectbackground="#0284C7",
                                        selectforeground="#FFFFFF", font=("Segoe UI", 9, "bold"), width=28, height=18,
                                        relief="flat", highlightthickness=1, highlightcolor="#38BDF8", highlightbackground="#334155")
        self.topic_listbox.pack(side="left", fill="both", expand=True)
        sb1 = ttk.Scrollbar(left, orient="vertical", command=self.topic_listbox.yview)
        self.topic_listbox.configure(yscrollcommand=sb1.set)
        sb1.pack(side="right", fill="y")

        for topic in HELP_TOPICS.keys():
            self.topic_listbox.insert("end", f"  {topic}")

        # Content Viewer
        right = ttk.LabelFrame(split, text=" Documentation & Instructions ", padding=6)
        right.pack(side="right", fill="both", expand=True)

        self.text_area = scrolledtext.ScrolledText(right, bg="#0F172A", fg="#F8FAFC", insertbackground="#38BDF8",
                                                  font=("Consolas", 10), wrap="word", relief="flat",
                                                  highlightthickness=1, highlightcolor="#38BDF8", highlightbackground="#334155")
        self.text_area.pack(fill="both", expand=True)

        self.topic_listbox.bind("<<ListboxSelect>>", self.on_topic_selected)
        
        # Bottom bar
        bot = ttk.Frame(container)
        bot.pack(fill="x", pady=(8, 0))
        ttk.Button(bot, text="Close", command=self.win.destroy).pack(side="right")

        # Select first topic
        if HELP_TOPICS:
            self.topic_listbox.selection_set(0)
            self.display_topic(list(HELP_TOPICS.keys())[0])

    def on_topic_selected(self, event=None):
        sel = self.topic_listbox.curselection()
        if sel:
            topic_name = list(HELP_TOPICS.keys())[sel[0]]
            self.display_topic(topic_name)

    def display_topic(self, topic_name: str):
        content = HELP_TOPICS.get(topic_name, "No content available.")
        self.text_area.configure(state="normal")
        self.text_area.delete("1.0", "end")
        self.text_area.insert("1.0", content.strip())
        self.text_area.configure(state="disabled")
