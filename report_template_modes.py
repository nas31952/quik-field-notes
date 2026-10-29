"""
Report Template Processing Modes & Section Data Model for SeismicScoutingSuite
Defines the processing strategies for handling attached master template reports,
including size-reduction cloning, quality verification with yellow highlighting,
automatic synchronization with change tracking, and full AI synthesis with section co-authoring.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


class ReportTemplateProcessingMode:
    """Strategy constants for report template handling and AI authoring."""
    EXACT_COPY_SIZE_OPT = "1. Copy Template As-Is (Size Reduction & Optimization Only)"
    ANALYZE_VERIFY_HIGHLIGHT_YELLOW = "2. Verify Content & Highlight Concerns in Yellow (No Updates)"
    ANALYZE_UPDATE_HIGHLIGHT_CHANGES = "3. Update Content & Highlight Changes (Synchronize Project Data)"
    STYLE_HEADINGS_FULL_AI_SYNTHESIS = "4. Style & Headings Only (Full AI Report Synthesis from Attached Files)"
    EXECUTIVE_SUMMARY_KPI_SCORECARD = "5. Executive Summary & Key Survey KPI Dashboard Only"
    ARAMCO_OGP_STANDARDS_AUDIT = "6. Saudi Aramco & OGP Standards Compliance Audit (GDAD-SL-012R03)"
    INTERACTIVE_SECTION_COAUTHORING = "7. Interactive AI Section Co-Authoring & Review Wizard"

    @classmethod
    def all_modes(cls) -> List[str]:
        return [
            cls.EXACT_COPY_SIZE_OPT,
            cls.ANALYZE_VERIFY_HIGHLIGHT_YELLOW,
            cls.ANALYZE_UPDATE_HIGHLIGHT_CHANGES,
            cls.STYLE_HEADINGS_FULL_AI_SYNTHESIS,
            cls.EXECUTIVE_SUMMARY_KPI_SCORECARD,
            cls.ARAMCO_OGP_STANDARDS_AUDIT,
            cls.INTERACTIVE_SECTION_COAUTHORING,
        ]


MODE_METADATA: Dict[str, Dict[str, str]] = {
    ReportTemplateProcessingMode.EXACT_COPY_SIZE_OPT: {
        "title": "Exact Copy with Size Optimization Only (Default)",
        "badge": "SIZE OPTIMIZED",
        "badge_color": "#10B981",
        "description": (
            "Copies all template text, tables, figures, and formatting exactly as-is. "
            "Applies non-destructive compression to embedded images and strips XML bloat "
            "for maximum file size reduction (~10MB target) without altering editorial content."
        ),
        "modifies_text": False,
        "highlighting": "None",
        "uses_ai": False,
    },
    ReportTemplateProcessingMode.ANALYZE_VERIFY_HIGHLIGHT_YELLOW: {
        "title": "Verify & Highlight Concerns in Yellow (Read-Only QA Audit)",
        "badge": "AUDIT / YELLOW HIGHLIGHT",
        "badge_color": "#F59E0B",
        "description": (
            "Audits existing template contents against active survey data, coordinates, dates, and safety standards. "
            "Flags discrepancies, unverified claims, outdated figures, and missing checks in YELLOW. "
            "Original text is preserved without automatic modification for QA reviewer inspection."
        ),
        "modifies_text": False,
        "highlighting": "Yellow Discrepancy & Reviewer Callouts",
        "uses_ai": True,
    },
    ReportTemplateProcessingMode.ANALYZE_UPDATE_HIGHLIGHT_CHANGES: {
        "title": "Update Content & Highlight Changes (Synchronize Project Data)",
        "badge": "CHANGES TRACKED",
        "badge_color": "#0284C7",
        "description": (
            "Cross-references template contents against current survey coordinates, terrain profiles, and field data. "
            "Automatically updates outdated figures, station counts, boundaries, and obstacle logs with verified project numbers. "
            "Highlights all modified text and updated blocks in GREEN/CYAN change tracking markup."
        ),
        "modifies_text": True,
        "highlighting": "Green / Cyan Change Tracking",
        "uses_ai": True,
    },
    ReportTemplateProcessingMode.STYLE_HEADINGS_FULL_AI_SYNTHESIS: {
        "title": "Headings & Style Only (Full AI Report Synthesis from Attached Files)",
        "badge": "AI SYNTHESIS",
        "badge_color": "#8B5CF6",
        "description": (
            "Retains only the template visual styling, fonts, and section heading hierarchy. "
            "AI Analyzer researches all attached data (database, photos, maps, logs, user notes) to write full technical narratives. "
            "If no data or user input is found for a section, leaves the heading with a mandatory user-action comment."
        ),
        "modifies_text": True,
        "highlighting": "Full Technical AI Content + User Action Comments",
        "uses_ai": True,
    },
    ReportTemplateProcessingMode.EXECUTIVE_SUMMARY_KPI_SCORECARD: {
        "title": "Executive Summary & Survey KPI Dashboard Only",
        "badge": "EXECUTIVE KPI",
        "badge_color": "#EC4899",
        "description": (
            "Distills the template and field data into a concise, high-impact management briefing. "
            "Extracts key survey KPIs (Total Area, Clear vs Restricted, Top Hazards, Fleet Readiness, Critical Path) "
            "and produces an executive summary scorecard without verbose narrative text."
        ),
        "modifies_text": True,
        "highlighting": "Executive Metric Cards & Sign-off Blocks",
        "uses_ai": True,
    },
    ReportTemplateProcessingMode.ARAMCO_OGP_STANDARDS_AUDIT: {
        "title": "Saudi Aramco & OGP Standards Compliance Audit (GDAD-SL-012R03)",
        "badge": "STANDARDS AUDIT",
        "badge_color": "#F97316",
        "description": (
            "Performs rigorous standards compliance checking against Saudi Aramco GDAD-SL-012R03, SL-004R02, and SL-018R06. "
            "Verifies 50m pipeline buffers, sabkha trafficability, well ties <= 250m, and deflection angles <= 5°, "
            "inserting a formal Compliance Verification Matrix with Pass/Warning/Fail status."
        ),
        "modifies_text": True,
        "highlighting": "Compliance Matrix & Risk Highlights",
        "uses_ai": True,
    },
    ReportTemplateProcessingMode.INTERACTIVE_SECTION_COAUTHORING: {
        "title": "Interactive Turn-by-Turn Section Co-Authoring Wizard",
        "badge": "INTERACTIVE WIZARD",
        "badge_color": "#06B6D4",
        "description": (
            "Step-by-step turn-by-turn workflow guiding the user section-by-section. "
            "Allows the user to review attached sources, enter custom initial guidance, preview live AI drafts, "
            "edit prose inline, and approve each section prior to final document generation."
        ),
        "modifies_text": True,
        "highlighting": "User-Approved Custom Prose",
        "uses_ai": True,
    },
}


@dataclass
class ReportSectionItem:
    """Represents a discrete report section with template text, guidance, sources, and generated content."""
    section_id: str
    title: str
    category: str = "General"
    user_initial_prompt: str = ""
    detected_sources: List[str] = field(default_factory=list)
    original_template_content: str = ""
    generated_content: str = ""
    concerns_found: List[str] = field(default_factory=list)
    updates_made: List[str] = field(default_factory=list)
    status: str = "ready" # 'ready', 'needs_user_input', 'updated', 'warning', 'action_required'
    is_included: bool = True

    def has_available_info(self) -> bool:
        """Returns True if any user guidance, detected data sources, or template content exists."""
        return bool(self.user_initial_prompt.strip() or self.detected_sources or self.original_template_content.strip())


def get_default_scouting_sections() -> List[ReportSectionItem]:
    """Returns the standard catalog of Saudi Aramco / ARGAS Digital Scouting Report sections."""
    return [
        ReportSectionItem(
            section_id="sec_01_overview",
            title="1. Location & Prospect Overview",
            category="Overview & Location",
            detected_sources=["Boundary Polygon", "UTM Projection", "Core Map 1 (Overview)"],
        ),
        ReportSectionItem(
            section_id="sec_02_team",
            title="2. Scouting Team & Organization",
            category="Operations & Logistics",
            detected_sources=["Table 3 Team Roster", "Table 4 Equipment Inventory"],
        ),
        ReportSectionItem(
            section_id="sec_03_access",
            title="3. Access to Prospect & Main Highways",
            category="Logistics & Access",
            detected_sources=["Field Tracks", "Waypoints", "Core Map 3 (Access & Tracks)"],
        ),
        ReportSectionItem(
            section_id="sec_04_objectives",
            title="4. Objectives of the Scouting",
            category="Operational Scope",
            detected_sources=["Contract Scope", "Exploration Guidelines (GDAD-SL-012R03)"],
        ),
        ReportSectionItem(
            section_id="sec_05_comms",
            title="5. Communication Means & Emergency Contact",
            category="Safety & Comms",
            detected_sources=["VHF Frequencies", "Satellite Iridium / InReach", "GSM 4G/5G Coverage"],
        ),
        ReportSectionItem(
            section_id="sec_06_terrain",
            title="6. Terrain Description and Initial Terrain Classification",
            category="Geomatics & GIS",
            detected_sources=["GIS Terrain Polygon", "Slope Grid", "Figure 5 Terrain Map", "Terrain Pie Chart"],
        ),
        ReportSectionItem(
            section_id="sec_07_remoteness",
            title="7. Remoteness and Operation Area Types",
            category="Contractual & Commercial",
            detected_sources=["Base Distance (km)", "Aramco Contract Areas (A/B/C/D)", "Figure 7.1 Map", "Table 6"],
        ),
        ReportSectionItem(
            section_id="sec_08_permitting",
            title="8. Permitting Requirements & Third-Party Clearances",
            category="Permitting & Lands",
            detected_sources=["Agricultural Parcels", "Pipeline Right-of-Ways", "Military No-Go Zones"],
        ),
        ReportSectionItem(
            section_id="sec_09_camps",
            title="9. Camps Organization & Staging Logistics",
            category="Operations & Logistics",
            detected_sources=["Fly Camp Coordinates", "Water Well Locations", "Core Map 7 (Camps)"],
        ),
        ReportSectionItem(
            section_id="sec_10_hospitals",
            title="10. Local Hospital Support & Medevac Logistics",
            category="Health, Safety & Environment",
            detected_sources=["Regional Hospital Waypoints", "Drive Time Estimates", "Core Map 8 (Medevac)"],
        ),
        ReportSectionItem(
            section_id="sec_11_difficulties",
            title="11. Major Difficulties of the Blocks & Environmental Challenges",
            category="Field Analysis",
            detected_sources=["Sabkha Soft Ground Logs", "Dune Crests", "Field Tracks", "High Voltage Lines"],
        ),
        ReportSectionItem(
            section_id="sec_12_hazards",
            title="12. Hazards and Risk Identification (HIRA Matrix)",
            category="Health, Safety & Environment",
            detected_sources=["Aramco GDAD Risk Registry", "50m Pipeline Buffers", "Heat Stress Monitoring"],
        ),
        ReportSectionItem(
            section_id="sec_13_conclusion",
            title="13. Conclusion and Recommendations",
            category="Departmental Synthesis",
            detected_sources=["Total Area Acquisition Viability", "Directives for Field Execution"],
        ),
        ReportSectionItem(
            section_id="sec_14_photos",
            title="14. Field Scouting Photographs & Georeferenced Plates",
            category="Evidence & Photos",
            detected_sources=["Curated Photo Collection", "EXIF GPS Geotags", "Plate Captions"],
        ),
    ]

