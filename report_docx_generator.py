"""
Word Document Generator Engine for ARGAS Scouting Report Suite
Clones the benchmark LIDAM II template, updates all tables (0 to 6),
injects maps (standard optional + custom), inserts terrain pie chart,
updates body narratives, and appends photo plates with exact formatting.
"""

import os
import shutil
import re
from typing import Dict, List, Optional, Any
from PIL import Image

try:
    import docx
    from docx.shared import Inches, Pt, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.enum.table import WD_TABLE_ALIGNMENT
    from docx.oxml import OxmlElement, parse_xml
    from docx.oxml.ns import nsdecls, qn
except ImportError:
    docx = None

from boundary_manager import BoundaryManager
from maps_manager import MapsManager
from terrain_chart_generator import TerrainChartGenerator
from report_template_modes import (
    ReportTemplateProcessingMode,
    ReportSectionItem,
    MODE_METADATA,
    get_default_scouting_sections
)
from report_analyzer_engine import ReportAnalyzerEngine


class ReportDocxGenerator:
    """Generates a complete, publication-ready Saudi Aramco Scouting Report."""

    def __init__(self, template_path: str):
        self.template_path = template_path
        if not os.path.exists(template_path):
            raise FileNotFoundError(f"Template document not found: {template_path}")

    def generate_report(self,
                        output_docx_path: str,
                        project_meta: Dict,
                        boundary_mgr: Optional[BoundaryManager] = None,
                        maps_mgr: Optional[MapsManager] = None,
                        terrain_data: Optional[List[Dict]] = None,
                        pie_chart_path: Optional[str] = None,
                        terrain_map_path: Optional[str] = None,
                        aramco_map_path: Optional[str] = None,
                        aramco_pie_chart_path: Optional[str] = None,
                        aramco_data: Optional[List[Dict]] = None,
                        curated_photos: Optional[List[Dict]] = None,
                        include_non_geotagged: bool = True,
                        processing_mode: str = ReportTemplateProcessingMode.EXACT_COPY_SIZE_OPT,
                        user_section_prompts: Optional[Dict[str, str]] = None,
                        journal_mgr: Optional[Any] = None,
                        log_cb=print) -> str:
        """
        Executes document assembly according to the selected ReportTemplateProcessingMode:
        1. Exact Copy with Size Optimization Only (Default)
        2. Verify Content & Highlight Concerns in Yellow (No Updates)
        3. Update Content & Highlight Changes (Synchronize Project Data)
        4. Style & Headings Only (Full AI Report Synthesis from Attached Files)
        5. Executive Summary & Key Survey KPI Dashboard Only
        6. Saudi Aramco & OGP Standards Compliance Audit (GDAD-SL-012R03)
        7. Interactive AI Section Co-Authoring & Review Wizard
        """
        if not docx:
            raise ImportError("python-docx library is not installed.")

        # ----------------------------------------------------------------------
        # MODE 1: EXACT COPY WITH SIZE REDUCTION ONLY (DEFAULT)
        # ----------------------------------------------------------------------
        if processing_mode == ReportTemplateProcessingMode.EXACT_COPY_SIZE_OPT:
            log_cb("Strategy Mode 1: Copy Template As-Is (Size Reduction & Optimization Only).")
            log_cb(f"Cloning master template '{os.path.basename(self.template_path)}' verbatim...")
            os.makedirs(os.path.dirname(os.path.abspath(output_docx_path)), exist_ok=True)
            shutil.copy2(self.template_path, output_docx_path)

            log_cb("Applying non-destructive size reduction optimizations...")
            try:
                from scouting_photo_enhancer import optimize_docx_media_for_target_mb
                optimize_docx_media_for_target_mb(output_docx_path, target_mb=10.0, enforce_limit=True, log_cb=log_cb)
            except Exception as e:
                log_cb(f"Media optimization note: {e}")

            log_cb(f"Size-optimized verbatim report successfully generated: {output_docx_path}")
            return output_docx_path

        # ----------------------------------------------------------------------
        # MODE 2: ANALYZE, VERIFY & HIGHLIGHT CONCERNS IN YELLOW (NO UPDATES)
        # ----------------------------------------------------------------------
        if processing_mode == ReportTemplateProcessingMode.ANALYZE_VERIFY_HIGHLIGHT_YELLOW:
            log_cb("Strategy Mode 2: Verify Content & Highlight Concerns in Yellow (Read-Only QA Audit).")
            log_cb(f"Cloning master template '{os.path.basename(self.template_path)}'...")
            os.makedirs(os.path.dirname(os.path.abspath(output_docx_path)), exist_ok=True)
            shutil.copy2(self.template_path, output_docx_path)
            doc = docx.Document(output_docx_path)

            analyzer = ReportAnalyzerEngine()
            concerns = analyzer.verify_and_highlight_concerns(
                doc=doc,
                project_meta=project_meta,
                boundary_mgr=boundary_mgr,
                terrain_data=terrain_data,
                aramco_data=aramco_data,
                log_cb=log_cb
            )
            self._inject_powered_by_footer(doc)
            doc.save(output_docx_path)
            log_cb(f"Quality audit report generated with {len(concerns)} concern(s) highlighted in yellow: {output_docx_path}")
            return output_docx_path

        # ----------------------------------------------------------------------
        # MODE 5: EXECUTIVE SUMMARY & KEY SURVEY KPI DASHBOARD
        # ----------------------------------------------------------------------
        if processing_mode == ReportTemplateProcessingMode.EXECUTIVE_SUMMARY_KPI_SCORECARD:
            log_cb("Strategy Mode 5: Generating Executive Summary & KPI Scorecard Dashboard.")
            log_cb(f"Cloning master template '{os.path.basename(self.template_path)}'...")
            os.makedirs(os.path.dirname(os.path.abspath(output_docx_path)), exist_ok=True)
            shutil.copy2(self.template_path, output_docx_path)
            doc = docx.Document(output_docx_path)
            prospect_name = project_meta.get('prospect_name', 'Prospect Area')
            total_acq_area = boundary_mgr.total_acquisition_area_sqkm if boundary_mgr else 0.0

            self._update_cover_and_tables(doc, project_meta, boundary_mgr, terrain_data, aramco_data, log_cb)

            analyzer = ReportAnalyzerEngine()
            kpi_stats = analyzer.generate_executive_kpi_scorecard(
                doc=doc,
                project_meta=project_meta,
                boundary_mgr=boundary_mgr,
                terrain_data=terrain_data,
                aramco_data=aramco_data,
                log_cb=log_cb
            )

            self._inject_powered_by_footer(doc)
            doc.save(output_docx_path)
            log_cb(f"Executive KPI Scorecard report generated with {kpi_stats.get('kpi_count', 0)} KPI metrics: {output_docx_path}")
            return output_docx_path

        # ----------------------------------------------------------------------
        # MODE 6: SAUDI ARAMCO & OGP STANDARDS COMPLIANCE AUDIT (GDAD-SL-012R03)
        # ----------------------------------------------------------------------
        if processing_mode == ReportTemplateProcessingMode.ARAMCO_OGP_STANDARDS_AUDIT:
            log_cb("Strategy Mode 6: Running Saudi Aramco GDAD-SL-012R03 Standards Compliance Audit.")
            log_cb(f"Cloning master template '{os.path.basename(self.template_path)}'...")
            os.makedirs(os.path.dirname(os.path.abspath(output_docx_path)), exist_ok=True)
            shutil.copy2(self.template_path, output_docx_path)
            doc = docx.Document(output_docx_path)

            self._update_cover_and_tables(doc, project_meta, boundary_mgr, terrain_data, aramco_data, log_cb)

            analyzer = ReportAnalyzerEngine()
            audit_stats = analyzer.generate_compliance_matrix(
                doc=doc,
                project_meta=project_meta,
                boundary_mgr=boundary_mgr,
                terrain_data=terrain_data,
                aramco_data=aramco_data,
                log_cb=log_cb
            )

            self._inject_powered_by_footer(doc)
            doc.save(output_docx_path)
            passed = audit_stats.get('passed', 0)
            total = audit_stats.get('total', 8)
            log_cb(f"GDAD-SL-012R03 Compliance Audit complete — {passed}/{total} requirements met: {output_docx_path}")
            return output_docx_path

        # ----------------------------------------------------------------------
        # MODE 7: INTERACTIVE AI SECTION CO-AUTHORING & REVIEW WIZARD
        # (Falls through to Mode 4 synthesis with user_section_prompts already loaded)
        # ----------------------------------------------------------------------
        if processing_mode == ReportTemplateProcessingMode.INTERACTIVE_SECTION_COAUTHORING:
            log_cb("Strategy Mode 7: Interactive AI Section Co-Authoring Wizard — synthesizing with user guidance prompts.")
            processing_mode = ReportTemplateProcessingMode.STYLE_HEADINGS_FULL_AI_SYNTHESIS

        # ----------------------------------------------------------------------
        # MODE 4: STYLE & HEADINGS ONLY (FULL AI SYNTHESIS FROM ATTACHED FILES)
        # ----------------------------------------------------------------------
        if processing_mode == ReportTemplateProcessingMode.STYLE_HEADINGS_FULL_AI_SYNTHESIS:
            log_cb("Strategy Mode 4: Style & Headings Only (Full AI Report Synthesis from Attached Files).")
            log_cb(f"Cloning master template typography & styles: {os.path.basename(self.template_path)}...")
            os.makedirs(os.path.dirname(os.path.abspath(output_docx_path)), exist_ok=True)
            shutil.copy2(self.template_path, output_docx_path)
            doc = docx.Document(output_docx_path)
            prospect_name = project_meta.get('prospect_name', 'Prospect Area')
            total_acq_area = boundary_mgr.total_acquisition_area_sqkm if boundary_mgr else 0.0

            analyzer = ReportAnalyzerEngine()
            sections = analyzer.detect_sections_and_map_sources(
                template_path=self.template_path,
                project_meta=project_meta,
                boundary_mgr=boundary_mgr,
                terrain_data=terrain_data,
                aramco_data=aramco_data,
                maps_mgr=maps_mgr,
                curated_photos=curated_photos,
                user_section_prompts=user_section_prompts,
                journal_mgr=journal_mgr
            )

            # Update core titles and tables
            self._update_cover_and_tables(doc, project_meta, boundary_mgr, terrain_data, aramco_data, log_cb)

            # Synthesize all sections
            stats = analyzer.synthesize_full_report_from_files(
                doc=doc,
                sections=sections,
                project_meta=project_meta,
                boundary_mgr=boundary_mgr,
                terrain_data=terrain_data,
                aramco_data=aramco_data,
                curated_photos=curated_photos,
                log_cb=log_cb
            )

            # Inject active maps and charts
            if terrain_map_path and os.path.exists(terrain_map_path):
                self._update_section_6(doc, terrain_data or [], terrain_map_path, pie_chart_path, total_acq_area, prospect_name)
            if aramco_map_path and os.path.exists(aramco_map_path):
                self._update_section_7(doc, aramco_data, aramco_map_path, aramco_pie_chart_path, total_acq_area, project_meta)

            active_maps = maps_mgr.get_active_maps() if maps_mgr else []
            if active_maps:
                self._inject_maps(doc, active_maps)

            if curated_photos:
                self._append_photo_plates(doc, curated_photos, include_non_geotagged)

            self._inject_powered_by_footer(doc)
            doc.save(output_docx_path)
            log_cb(f"Full AI synthesized report complete ({stats['written_sections']} written, {stats['user_action_sections']} pending user action): {output_docx_path}")
            return output_docx_path

        # ----------------------------------------------------------------------
        # MODE 3 (AND DEFAULT ENHANCED GENERATION): UPDATE CONTENT & HIGHLIGHT CHANGES
        # ----------------------------------------------------------------------
        log_cb(f"Cloning master template: {os.path.basename(self.template_path)}...")
        os.makedirs(os.path.dirname(os.path.abspath(output_docx_path)), exist_ok=True)
        shutil.copy2(self.template_path, output_docx_path)

        doc = docx.Document(output_docx_path)
        prospect_name = project_meta.get('prospect_name', 'Prospect Area')
        crew_name = project_meta.get('crew_name', 'Crew S-86')
        report_date = project_meta.get('report_date', 'October 2026')
        total_acq_area = boundary_mgr.total_acquisition_area_sqkm if boundary_mgr else 0.0

        # Update cover and tables
        self._update_cover_and_tables(doc, project_meta, boundary_mgr, terrain_data, aramco_data, log_cb)

        # 8. Update Objectives & Communication Means Paragraphs
        log_cb("Updating Objectives and Communication sections...")
        self._update_objectives_and_comms(doc, project_meta)

        # 9. Update Section 6: Terrain Classification, Map & Pie Chart
        log_cb("Updating Section 6 (Terrain Description, Figures & Pie Chart)...")
        self._update_section_6(doc, terrain_data or [], terrain_map_path, pie_chart_path,
                               total_acq_area, prospect_name)

        # 10. Update Section 7: Remoteness, Aramco Area Types & Map & Table 6
        log_cb("Updating Section 7 (Remoteness, Aramco Contractual Areas & Map)...")
        self._update_section_7(doc, aramco_data, aramco_map_path, aramco_pie_chart_path,
                               total_acq_area, project_meta)

        # 11. Inject Active Maps (Core 1, 2, 3, 4, 6, 8, 9 + Custom Maps)
        active_maps = maps_mgr.get_active_maps() if maps_mgr else []
        if active_maps:
            log_cb(f"Injecting {len(active_maps)} active map figures with technical descriptions...")
            self._inject_maps(doc, active_maps)

        # 12. Update Sections 11, 12, 13 (Difficulties, Hazards Risk Matrix & Conclusion)
        log_cb("Enriching Section 11, Section 12 (HSE Matrix) & Section 13 (Conclusion)...")
        self._update_sections_11_12_13(doc, project_meta, terrain_data or [], boundary_mgr)

        # Apply Change Tracking Highlights if Mode 3 is selected
        if processing_mode == ReportTemplateProcessingMode.ANALYZE_UPDATE_HIGHLIGHT_CHANGES:
            log_cb("Strategy Mode 3: Applying change tracking highlights (Green / Cyan)...")
            analyzer = ReportAnalyzerEngine()
            updates = analyzer.update_and_highlight_changes(
                doc=doc,
                project_meta=project_meta,
                boundary_mgr=boundary_mgr,
                terrain_data=terrain_data,
                aramco_data=aramco_data,
                log_cb=log_cb
            )

        # 13. Append Curated Photo Plates (Geotagged First, Non-Geotagged at End)
        if curated_photos:
            log_cb(f"Formatting field photo plates (Include Non-Geotagged: {include_non_geotagged})...")
            self._append_photo_plates(doc, curated_photos, include_non_geotagged)

        # 14. Inject Powered By Title
        self._inject_powered_by_footer(doc)

        doc.save(output_docx_path)
        log_cb(f"Word report generation complete: {output_docx_path}")
        return output_docx_path

    def _update_cover_and_tables(self, doc, project_meta: Dict, boundary_mgr, terrain_data, aramco_data, log_cb=print):
        """Updates Title, Table 0, Table 1, Table 2, Table 3, Table 4, and Table 5."""
        prospect_name = project_meta.get('prospect_name', 'Prospect Area')
        crew_name = project_meta.get('crew_name', 'Crew S-86')
        report_date = project_meta.get('report_date', 'October 2026')

        # 1. Update Cover & Header Paragraphs
        log_cb("Updating document titles and metadata...")
        for p in doc.paragraphs[:25]:
            orig = p.text
            if "scouting report" in orig.lower() and len(orig.strip()) < 80:
                p.text = f"{prospect_name}\nScouting Report"
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            elif "arabian geophysical" in orig.lower():
                p.text = "ARABIAN GEOPHYSICAL & SURVEYING COMPANY"
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            elif "crew s-" in orig.lower():
                p.text = f"{crew_name}"
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER

        # 2. Update Table 0: Contractor & Prospect Metadata
        if len(doc.tables) > 0:
            t0 = doc.tables[0]
            log_cb("Updating Table 0 (Contractor & Area Information)...")
            for row in t0.rows:
                cells = row.cells
                if len(cells) >= 3:
                    lbl = cells[0].text.strip().lower()
                    if "contractor" in lbl:
                        cells[2].text = project_meta.get('contractor_name', f"ARGAS ({crew_name})")
                    elif "area" in lbl or "prospect" in lbl:
                        cells[2].text = f"{prospect_name}"
                    elif "date" in lbl:
                        cells[2].text = f"{report_date}"

        # 3. Update Table 1: Distribution List
        if len(doc.tables) > 1 and 'distribution_list' in project_meta:
            t1 = doc.tables[1]
            log_cb("Updating Table 1 (Distribution List)...")
            dist = project_meta['distribution_list']
            for idx, item in enumerate(dist):
                r_idx = idx + 1
                if r_idx < len(t1.rows):
                    row = t1.rows[r_idx]
                    row.cells[0].text = item.get('company', '')
                    row.cells[1].text = item.get('position', '')

        # 4. Update Table 2: Revision Control & Sign-offs
        if len(doc.tables) > 2:
            t2 = doc.tables[2]
            log_cb("Updating Table 2 (Revisions & Approvals)...")
            if len(t2.rows) >= 2:
                row = t2.rows[1]
                cells = row.cells
                if len(cells) >= 5:
                    cells[0].text = project_meta.get('revision_no', 'Rev 0')
                    cells[1].text = project_meta.get('revision_date', '26/10/2026')
                    cells[2].text = project_meta.get('prepared_by', 'Party Chief / Chief Surveyor')
                    cells[3].text = project_meta.get('reviewed_by', 'Operations Manager / QHSE Manager')
                    cells[4].text = project_meta.get('approved_by', 'Saudi Aramco GDAD Rep')

        # 5. Update Table 3: Scouting Team Roster
        if len(doc.tables) > 3 and 'scouting_team' in project_meta:
            t3 = doc.tables[3]
            log_cb("Updating Table 3 (Scouting Team Roster)...")
            team = project_meta['scouting_team']
            while len(t3.rows) > 1:
                tr = t3.rows[-1]._tr
                tr.getparent().remove(tr)
            for idx, member in enumerate(team, start=1):
                row = t3.add_row()
                cells = row.cells
                if len(cells) >= 4:
                    cells[0].text = str(idx)
                    if isinstance(member, dict):
                        cells[1].text = str(member.get('name', ''))
                        cells[2].text = str(member.get('position', ''))
                        cells[3].text = str(member.get('responsibility', ''))
                    elif isinstance(member, (list, tuple)):
                        cells[1].text = str(member[0]) if len(member) > 0 else ''
                        cells[2].text = str(member[1]) if len(member) > 1 else ''
                        cells[3].text = str(member[2]) if len(member) > 2 else ''

        # 6. Update Table 4: Equipment Roster
        if len(doc.tables) > 4 and 'scouting_equipment' in project_meta:
            t4 = doc.tables[4]
            log_cb("Updating Table 4 (Scouting Equipment)...")
            eq_list = project_meta['scouting_equipment']
            while len(t4.rows) > 1:
                tr = t4.rows[-1]._tr
                tr.getparent().remove(tr)
            for eq in eq_list:
                row = t4.add_row()
                cells = row.cells
                if len(cells) >= 4:
                    if isinstance(eq, dict):
                        cells[0].text = str(eq.get('item', ''))
                        cells[1].text = str(eq.get('type', ''))
                        cells[2].text = str(eq.get('quantity', '1'))
                        cells[3].text = str(eq.get('fleet_no', ''))
                    elif isinstance(eq, (list, tuple)):
                        cells[0].text = str(eq[0]) if len(eq) > 0 else ''
                        cells[1].text = str(eq[1]) if len(eq) > 1 else ''
                        cells[2].text = str(eq[2]) if len(eq) > 2 else '1'
                        cells[3].text = str(eq[3]) if len(eq) > 3 else ''

        # 7. Update Table 5: Multi-Block Boundary Coordinates & Areas
        if len(doc.tables) > 5 and boundary_mgr and boundary_mgr.blocks:
            log_cb("Formatting Table 5 (Multi-Block Boundary Coordinates)...")
            self._update_table_5(doc.tables[5], boundary_mgr, prospect_name)

    def _update_table_5(self, table, boundary_mgr: BoundaryManager, prospect_name: str):
        """Formats Table 5 for single or multi-block coordinate listings."""
        # Row 0: Title banner
        table.rows[0].cells[0].text = f"{prospect_name.upper()} 3D Prospect Information"

        # Check total points needed
        total_pts = sum(len(b.points) for b in boundary_mgr.blocks.values())
        header_rows = 2 # Title + Column headers

        # Ensure table has enough rows
        needed_rows = header_rows + total_pts + (len(boundary_mgr.blocks) * 2) + 4
        while len(table.rows) < needed_rows:
            table.add_row()

        curr_r = 2
        for b_name, poly in boundary_mgr.blocks.items():
            # Block Subheader
            row = table.rows[curr_r]
            row.cells[0].text = f"Concession Block: {b_name} (Points: {len(poly.points)})"
            curr_r += 1

            for p in poly.points:
                if curr_r < len(table.rows):
                    r = table.rows[curr_r]
                    if len(r.cells) >= 4:
                        r.cells[0].text = p.point_id
                        r.cells[1].text = f"{p.easting:,.2f}"
                        r.cells[2].text = f"{p.northing:,.2f}"
                        if p.latitude is not None and p.longitude is not None:
                            r.cells[3].text = f"{p.latitude:.6f}° N, {p.longitude:.6f}° E"
                        else:
                            r.cells[3].text = p.notes or "-"
                    curr_r += 1

            # Perimeter & Area summary for block
            if curr_r < len(table.rows):
                r = table.rows[curr_r]
                r.cells[0].text = f"{b_name} Perimeter:"
                r.cells[1].text = f"{poly.perimeter_km:,.2f} km"
                r.cells[2].text = f"{b_name} Area:"
                r.cells[3].text = f"{poly.area_sqkm:,.2f} km²"
                curr_r += 1

        # Grand Totals
        if curr_r < len(table.rows):
            r = table.rows[curr_r]
            r.cells[0].text = "Full Fold Total Area:"
            r.cells[1].text = f"{boundary_mgr.total_full_fold_area_sqkm:,.2f} km²"
            r.cells[2].text = "Acquisition Total Area:"
            r.cells[3].text = f"{boundary_mgr.total_acquisition_area_sqkm:,.2f} km²"

    def _update_section_6(self, doc, terrain_data: List[Dict], terrain_map_path: Optional[str],
                           pie_chart_path: Optional[str], total_area: float, prospect_name: str):
        """Updates Section 6: geomorphic class listing, terrain map image, and pie chart."""
        if not terrain_data:
            return

        # 1. Update terrain percentage bullet list
        start_idx = -1
        end_idx = -1
        for i, p in enumerate(doc.paragraphs):
            txt = p.text.strip().lower()
            if "terrain description and initial terrain classification" in txt:
                start_idx = i
            elif start_idx != -1 and "terrain definition:" in txt:
                end_idx = i
                break

        if start_idx != -1 and end_idx != -1:
            # Check intro line
            if start_idx + 1 < len(doc.paragraphs):
                doc.paragraphs[start_idx + 1].text = (
                    f"During the field scouting, {len(terrain_data)} distinct geomorphic terrain classes "
                    f"covering a total surface area of {total_area:,.2f} km² were identified and classified as follows:"
                )
            # Update or replace bullet items
            bullet_paras = doc.paragraphs[start_idx + 2:end_idx]
            for idx, item in enumerate(terrain_data):
                line_str = f"• {item['class_name']}: {item['area_sqkm']:,.2f} km² ({item['percentage']:.1f}%)"
                if idx < len(bullet_paras):
                    bullet_paras[idx].text = line_str
                else:
                    # Insert new paragraph before end_idx
                    np = doc.paragraphs[end_idx].insert_paragraph_before(line_str)
            # Clear any extra leftover bullet paragraphs
            if len(bullet_paras) > len(terrain_data):
                for p_extra in bullet_paras[len(terrain_data):]:
                    p_extra.text = ""

        # 2. Replace Terrain Map (Figure 5)
        if terrain_map_path and os.path.exists(terrain_map_path):
            for i, p in enumerate(doc.paragraphs):
                txt = p.text.strip().lower()
                if "initial terrain classification map" in txt or "figure 5" in txt:
                    # Paragraph before or containing graphic
                    target_p = None
                    if i > 0 and len(doc.paragraphs[i - 1].runs) > 0 and 'graphic' in doc.paragraphs[i - 1].runs[0]._r.xml:
                        target_p = doc.paragraphs[i - 1]
                    else:
                        target_p = p.insert_paragraph_before()

                    target_p.text = ""
                    target_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    r = target_p.add_run()
                    r.add_picture(terrain_map_path, width=Inches(6.4))
                    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    p.text = f"Figure 5: Initial Terrain Classification Map — {prospect_name}"
                    break

        # 3. Inject Pie Chart (with identical colors!)
        if pie_chart_path and os.path.exists(pie_chart_path):
            self._inject_pie_chart(doc, pie_chart_path, terrain_data, total_area)

    def _update_section_7(self, doc, aramco_data: Optional[List[Dict]], aramco_map_path: Optional[str],
                           aramco_pie_chart_path: Optional[str],
                           total_area: float, project_meta: Dict):
        """Updates Section 7: Remoteness, Saudi Aramco Contractual Areas listing, map, and Table 6."""
        prospect_name = project_meta.get('prospect_name', 'Prospect Area')
        nearest_city = project_meta.get('nearest_city', 'Regional Supply Hub')
        distance_km = project_meta.get('base_distance_km', '120')
        zone = project_meta.get('remoteness_zone', 'Zone R0 (Standard Desert Concession)')

        # 1. Update Section 7 narrative and distribution list
        start_idx = -1
        end_idx = -1
        for i, p in enumerate(doc.paragraphs):
            txt = p.text.strip().lower()
            if "remoteness and operation area" in txt and not "map" in txt:
                start_idx = i
            elif start_idx != -1 and "remoteness and operation area map" in txt:
                end_idx = i
                break

        if start_idx != -1 and aramco_data:
            # Update intro
            if start_idx + 1 < len(doc.paragraphs):
                doc.paragraphs[start_idx + 1].text = (
                    f"The distribution of {prospect_name} by operational area and remoteness ({zone}) "
                    f"classification (Originating from {nearest_city}, approx. {distance_km} km) is as follows:"
                )

            # Bullet paragraphs
            if end_idx != -1:
                active_types = [c for c in aramco_data if c['area_sqkm'] > 0]
                bullet_paras = doc.paragraphs[start_idx + 2:end_idx]
                for idx, item in enumerate(active_types):
                    line_str = f"• {item['name']}: {item['area_sqkm']:,.2f} km² ({item['percentage']:.1f}%)"
                    if idx < len(bullet_paras):
                        bullet_paras[idx].text = line_str
                    else:
                        doc.paragraphs[end_idx].insert_paragraph_before(line_str)
                if len(bullet_paras) > len(active_types):
                    for p_extra in bullet_paras[len(active_types):]:
                        p_extra.text = ""

        # 2. Replace Aramco Contractual Area Map (Figure 7.1)
        if aramco_map_path and os.path.exists(aramco_map_path):
            for i, p in enumerate(doc.paragraphs):
                txt = p.text.strip().lower()
                if "remoteness and operation area map" in txt or "figure 7" in txt:
                    target_p = None
                    if i > 0 and len(doc.paragraphs[i - 1].runs) > 0 and 'graphic' in doc.paragraphs[i - 1].runs[0]._r.xml:
                        target_p = doc.paragraphs[i - 1]
                    else:
                        target_p = p.insert_paragraph_before()

                    target_p.text = ""
                    target_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    r = target_p.add_run()
                    r.add_picture(aramco_map_path, width=Inches(6.4))
                    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    p.text = f"Figure 7.1: Saudi Aramco Contractual Operational Area Classification Map — {prospect_name}"
                    break

        # 3. Inject Aramco Operational Area Pie Chart (Figure 7.2)
        if aramco_pie_chart_path and os.path.exists(aramco_pie_chart_path):
            # Locate position after Figure 7.1 or before Table 6
            target_p = None
            for i, p in enumerate(doc.paragraphs):
                txt = p.text.strip().lower()
                if "figure 7.1" in txt or "figure 7" in txt:
                    target_p = p.insert_paragraph_before()
                    break

            if not target_p and len(doc.paragraphs) > 0:
                target_p = doc.paragraphs[-1].insert_paragraph_before()

            if target_p:
                target_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                r = target_p.add_run()
                r.add_picture(aramco_pie_chart_path, width=Inches(5.6))
                cap_p = target_p.insert_paragraph_before()
                cap_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                cap_p.text = f"Figure 7.2: Saudi Aramco Contractual Operational Areas Breakdown — {prospect_name}"

        # 4. Update Table 6
        if len(doc.tables) > 6 and aramco_data:
            t6 = doc.tables[6]
            for row in t6.rows:
                cells = row.cells
                if len(cells) >= 2:
                    txt_0 = cells[0].text.strip().upper()
                    matched = False
                    for item in aramco_data:
                        cls_c = item.get('class_code', '').upper()
                        t_key = item.get('type_key', f"TYPE {cls_c}").upper()
                        if (cls_c and f"CLASS {cls_c}" in txt_0) or (t_key and t_key in txt_0) or (cls_c and f"TYPE {cls_c}" in txt_0):
                            matched = True
                            if item['area_sqkm'] > 0:
                                cells[1].text = (
                                    f"Active Concession Area: {item['area_sqkm']:,.2f} km² ({item['percentage']:.1f}%)\n"
                                    f"Remoteness: {item.get('remoteness', 'R0')}\n"
                                    f"{item['description']}\n[Contract Payment: {item['payment_factor']}]"
                                )
                            else:
                                cells[1].text = f"Non-active in this concession (0.00 km²).\n{item['description']}"
                            break
                    if not matched and len(cells) >= 2 and not cells[1].text.strip():
                        cells[1].text = "0.00 km² (0.0%) — Standard contractual provision."


    def _update_objectives_and_comms(self, doc, meta: Dict):
        """Updates bulleted objectives and communication paragraphs."""
        objectives = meta.get('objectives', [])
        comms = meta.get('communication_means', [])

        in_obj = False
        in_comms = False

        for p in doc.paragraphs:
            txt = p.text.strip().lower()
            if "objectives of the scouting" in txt:
                in_obj = True
                in_comms = False
                continue
            elif "communication means" in txt:
                in_obj = False
                in_comms = True
                continue
            elif "terrain description" in txt:
                in_obj = False
                in_comms = False
                continue

            if in_obj and p.text.strip().startswith(('•', '-', '1.', '2.')):
                if objectives:
                    p.text = f"• {objectives.pop(0)}"

            if in_comms and p.text.strip().startswith(('•', '-', '1.', '2.')):
                if comms:
                    p.text = f"• {comms.pop(0)}"

    def _inject_pie_chart(self, doc, pie_path: str, terrain_data: List[Dict], total_area: float):
        """Finds Section 6 heading and injects narrative + pie chart image."""
        target_idx = -1
        for i, p in enumerate(doc.paragraphs):
            if "terrain definition:" in p.text.strip().lower():
                target_idx = i
                break

        if target_idx != -1:
            chart_p = doc.paragraphs[target_idx].insert_paragraph_before()
            chart_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = chart_p.add_run()
            run.add_picture(pie_path, width=Inches(6.2))

            cap_p = doc.paragraphs[target_idx].insert_paragraph_before()
            cap_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            crun = cap_p.add_run("Figure 5.1: Geomorphic Surface Terrain Classification Breakdown")
            crun.font.size = Pt(9.5)
            crun.font.bold = True
            crun.font.color.rgb = RGBColor(0x1F, 0x49, 0x7D)

    def _inject_maps(self, doc, active_maps: List):
        """Inserts active maps and custom maps with descriptions into their sections."""
        for m in active_maps:
            if not os.path.exists(m.file_path):
                continue

            # Skip map_5 and map_7 here if already injected in dedicated sections
            if m.key in ['map_5', 'map_7']:
                continue

            target_sec_num = m.target_section.split(':')[0].replace('Section', '').strip()
            found_p = None
            for p in doc.paragraphs:
                ptxt = p.text.strip()
                if ptxt.startswith(f"{target_sec_num}.") or ptxt.startswith(f"{target_sec_num} "):
                    found_p = p
                    break

            if found_p:
                map_p = found_p.insert_paragraph_before()
                map_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                run = map_p.add_run()
                try:
                    run.add_picture(m.file_path, width=Inches(6.4))
                except Exception:
                    pass

                cap_p = found_p.insert_paragraph_before()
                cap_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                crun = cap_p.add_run(f"{m.title}")
                crun.font.size = Pt(9.5)
                crun.font.bold = True
                crun.font.color.rgb = RGBColor(0x1F, 0x49, 0x7D)

                if m.description:
                    desc_p = found_p.insert_paragraph_before()
                    drun = desc_p.add_run(f"{m.description}")
                    drun.font.size = Pt(10)
                    drun.font.italic = True

    def _append_photo_plates(self, doc, curated_photos: List[Dict], include_non_geotagged: bool = True):
        """
        Appends photo plates table partitioned into:
        1. Certified Geotagged Field Photographs (placed first with GPS coordinates & metadata)
        2. Supplemental Non-Geotagged Field Photographs (appended at the end under a distinct heading)
        Excluded/Rejected photos are omitted.
        """
        active_photos = [p for p in curated_photos if not p.get('is_rejected', False)]
        if not active_photos:
            return

        geotagged = [p for p in active_photos if p.get('has_gps', False)]
        non_geotagged = [p for p in active_photos if not p.get('has_gps', False)]

        doc.add_page_break()
        heading = doc.add_paragraph("14. Field Scouting Photographs & Georeferenced Plates")
        heading.style = 'Heading 1'

        intro = doc.add_paragraph(
            f"A total of {len(active_photos)} ground-truth field photographs were captured during the reconnaissance "
            f"to document surface trafficability, infrastructure crossings, and environmental obstacles. "
            f"All georeferenced coordinates are referenced to WGS 84 datum."
        )

        plate_counter = 1

        # 1. Geotagged Photos Table
        if geotagged:
            table = doc.add_table(rows=0, cols=2)
            table.alignment = WD_TABLE_ALIGNMENT.CENTER
            for i in range(0, len(geotagged), 2):
                row_imgs = table.add_row()
                row_caps = table.add_row()

                # Left photo
                p1 = geotagged[i]
                self._insert_photo_into_cell(row_imgs.cells[0], row_caps.cells[0], p1, plate_counter)
                plate_counter += 1

                # Right photo
                if i + 1 < len(geotagged):
                    p2 = geotagged[i + 1]
                    self._insert_photo_into_cell(row_imgs.cells[1], row_caps.cells[1], p2, plate_counter)
                    plate_counter += 1

        # 2. Non-Geotagged Photos (if selected)
        if include_non_geotagged and non_geotagged:
            doc.add_paragraph()
            subheading = doc.add_paragraph("14.2 Supplemental Field Photographs (Non-Geotagged)")
            subheading.style = 'Heading 2'
            callout = doc.add_paragraph(
                "Notice: The following reconnaissance photographs lack embedded EXIF GPS tags but provide "
                "valuable qualitative context of access tracks, village approaches, and general terrain conditions."
            )
            callout.runs[0].font.italic = True
            callout.runs[0].font.size = Pt(9.5)

            table_ng = doc.add_table(rows=0, cols=2)
            table_ng.alignment = WD_TABLE_ALIGNMENT.CENTER
            for i in range(0, len(non_geotagged), 2):
                row_imgs = table_ng.add_row()
                row_caps = table_ng.add_row()

                p1 = non_geotagged[i]
                self._insert_photo_into_cell(row_imgs.cells[0], row_caps.cells[0], p1, plate_counter)
                plate_counter += 1

                if i + 1 < len(non_geotagged):
                    p2 = non_geotagged[i + 1]
                    self._insert_photo_into_cell(row_imgs.cells[1], row_caps.cells[1], p2, plate_counter)
                    plate_counter += 1

    def _insert_photo_into_cell(self, img_cell, cap_cell, photo_info: Dict, fig_no: int):
        """Embeds single photo and formatted caption into table cell."""
        p_path = photo_info.get('file_path', '')
        if os.path.exists(p_path):
            p = img_cell.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = p.add_run()
            try:
                run.add_picture(p_path, width=Inches(3.1))
            except Exception:
                pass

        cp = cap_cell.paragraphs[0]
        cp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        caption_text = photo_info.get('caption', photo_info.get('description', 'Field scouting photograph'))

        # Add GPS badge if available
        gps_txt = ""
        if photo_info.get('has_gps'):
            lat = photo_info.get('lat')
            lon = photo_info.get('lon')
            if lat is not None and lon is not None:
                gps_txt = f"\n[GPS: {lat:.6f}° N, {lon:.6f}° E]"

        crun = cp.add_run(f"Plate {fig_no}: {caption_text}{gps_txt}")
        crun.font.size = Pt(8.5)
        crun.font.bold = True

    def _inject_powered_by_footer(self, doc):
        """Injects 'Powered by Nasrullah Khan' into document cover/footer."""
        # 1. Cover page subtitle
        if len(doc.paragraphs) > 4:
            p_sub = doc.paragraphs[4]
            run = p_sub.add_run("\nPowered by Nasrullah Khan")
            run.font.size = Pt(9.5)
            run.font.italic = True
            run.font.color.rgb = RGBColor(0x02, 0x84, 0xC7)

        # 2. Section footer
        try:
            for s in doc.sections:
                footer = s.footer
                if footer and len(footer.paragraphs) > 0:
                    fp = footer.paragraphs[0]
                    if "nasrullah" not in fp.text.lower():
                        frun = fp.add_run("  |  Powered by Nasrullah Khan")
                        frun.font.size = Pt(8)
                        frun.font.italic = True
                        frun.font.color.rgb = RGBColor(0x94, 0xA3, 0xB8)
        except Exception:
            pass

    def _update_sections_11_12_13(self, doc, meta: Dict, terrain_data: List[Dict], boundary_mgr: Optional[BoundaryManager] = None):
        """
        Enriches Section 11, Section 12, and Section 13 with comprehensive technical
        specifications, the Saudi Aramco HSE Risk Matrix, and departmental conclusion.
        """
        prospect = meta.get('prospect_name', 'Prospect Area')
        total_area = (boundary_mgr.total_acquisition_area_sqkm if boundary_mgr else 0.0) or 2832.24

        # Locate Section 11, 12, 13
        p_sec11 = None
        p_sec12 = None
        p_sec13 = None

        for p in doc.paragraphs:
            txt = p.text.strip().lower()
            if "major difficulties of the blocks" in txt:
                p_sec11 = p
            elif "hazards and risk identification" in txt:
                p_sec12 = p
            elif "conclusion" in txt and len(txt) < 30:
                p_sec13 = p

        # Enrich Section 11 if found
        if p_sec11:
            p_desc = p_sec11.insert_paragraph_before()
            p_desc.text = (
                f"Detailed field scouting across the {prospect} exploration area identified major operational and "
                f"geomorphic impediments requiring strict adherence to Saudi Aramco GDAD standard operating procedures. "
                f"These challenges encompass soft coastal and inland sabkhas, rugged escarpments, sand dikaka formations, "
                f"active aggregate quarries, highway corridors, and high-pressure oil/gas pipeline infrastructure."
            )

        # Enrich Section 12 if found
        if p_sec12:
            p_hse = p_sec12.insert_paragraph_before()
            p_hse.text = (
                f"A comprehensive Hazard Identification and Risk Assessment (HIRA) was conducted for all planned seismic "
                f"operations in {prospect}. In accordance with Saudi Aramco GDAD-SL-012 guidelines, all identified risks "
                f"must be managed through engineering controls, specialized low-ground-pressure vehicles, active IVMS tracking, "
                f"geofenced exclusion zones, and certified emergency medical evacuation readiness."
            )

        # Enrich Section 13 if found
        if p_sec13:
            p_c1 = p_sec13.insert_paragraph_before()
            p_c1.text = (
                f"13.1 Executive Summary & Survey Viability: Field scouting confirmed that the {prospect} survey area "
                f"(Total Acquisition Surface: {total_area:,.2f} km²) is fully viable for high-resolution 3D seismic acquisition. "
                f"While significant surface obstacles exist, all operational constraints can be mitigated through the tailored "
                f"technical recommendations formulated in this scouting report."
            )
            p_c2 = p_sec13.insert_paragraph_before()
            p_c2.text = (
                "13.2 Key Department Directives:\n"
                "• Survey & Geomatics: Deploy high-precision RTK GNSS control networks tied to Saudi Aramco monuments. Pre-load all sabkha no-go boundaries and pipeline buffers as active digital geofences.\n"
                "• Vibrator Operations: Deploy heavy-drive vibrators with low-pressure sand tires. Maintain dynamic penetrometer probing 48 hours in advance across all transitional sabkha corridors.\n"
                "• Permitting & Third-Party: Secure written crossing permits for major highways and establish 50m GDAD standoff buffers from high-pressure pipelines.\n"
                "• QHSE & Medevac: Maintain 24/7 Journey Management tracking, implement TWL heat stress monitoring, and confirm dedicated primary and secondary hospital medevac routes."
            )
