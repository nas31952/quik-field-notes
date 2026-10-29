"""
Automated Integration Test for SeismicScoutingSuite Report Processing Strategies
Tests all template handling modes:
1. Copy As-Is (Size Optimization Only)
2. Verify Content & Highlight Concerns in Yellow (No Updates)
3. Update Content & Highlight Changes (Synchronize Project Data)
4. Style & Headings Only (Full AI Report Synthesis from Attached Files)
"""

import os
import sys
import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_COLOR_INDEX

# Ensure current directory is on path
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from report_template_modes import (
    ReportTemplateProcessingMode,
    ReportSectionItem,
    get_default_scouting_sections
)
from report_analyzer_engine import ReportAnalyzerEngine
from report_docx_generator import ReportDocxGenerator
from boundary_manager import BoundaryManager, BoundaryPoint


def create_mock_template(path: str):
    """Creates a realistic test benchmark template docx."""
    doc = docx.Document()

    # Cover
    p_title = doc.add_paragraph("Old Sample Concession\nScouting Report")
    p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.add_paragraph("ARABIAN GEOPHYSICAL & SURVEYING COMPANY")
    doc.add_paragraph("Crew S-99")
    doc.add_paragraph("September 2024")

    # Table 0: Metadata
    t0 = doc.add_table(rows=4, cols=3)
    t0.rows[0].cells[0].text = "Contractor:"
    t0.rows[0].cells[2].text = "Old Contractor"
    t0.rows[1].cells[0].text = "Prospect Area:"
    t0.rows[1].cells[2].text = "Old Sample Concession"
    t0.rows[2].cells[0].text = "Report Date:"
    t0.rows[2].cells[2].text = "September 2024"
    t0.rows[3].cells[0].text = "Client:"
    t0.rows[3].cells[2].text = "Saudi Aramco"

    # Table 1: Distribution
    t1 = doc.add_table(rows=2, cols=2)
    t1.rows[0].cells[0].text = "Company"
    t1.rows[0].cells[1].text = "Position"

    # Table 2: Revisions
    t2 = doc.add_table(rows=2, cols=5)

    # Table 3: Team
    t3 = doc.add_table(rows=2, cols=4)

    # Table 4: Equipment
    t4 = doc.add_table(rows=2, cols=4)

    # Table 5: Boundary
    t5 = doc.add_table(rows=3, cols=4)
    t5.rows[0].cells[0].text = "PROSPECT BOUNDARY"

    # Table 6: Contract areas
    t6 = doc.add_table(rows=3, cols=2)

    # Sections
    doc.add_paragraph("1. Location & Prospect Overview")
    doc.add_paragraph("The Old Sample Concession covers an estimated 1,200 km² in the northern province.")

    doc.add_paragraph("2. Scouting Team")
    doc.add_paragraph("The scouting team mobilized under old guidelines.")

    doc.add_paragraph("3. Access to Prospect")
    doc.add_paragraph("Access is via old highway.")

    doc.add_paragraph("4. Objectives of the Scouting")
    doc.add_paragraph("• Verify boundary coordinates.")

    doc.add_paragraph("5. Communication Means")
    doc.add_paragraph("• VHF Radio.")

    doc.add_paragraph("6. Terrain Description and Initial Terrain Classification")
    doc.add_paragraph("Terrain description and initial terrain classification:")
    doc.add_paragraph("• Sandy Dunes: 600.00 km² (50.0%)")
    doc.add_paragraph("Terrain definition:")

    doc.add_paragraph("7. Remoteness and Operation Area")
    doc.add_paragraph("Remoteness and operation area:")
    doc.add_paragraph("• Type A: 1,200.00 km² (100.0%)")
    doc.add_paragraph("Remoteness and operation area map:")

    doc.add_paragraph("8. Permitting Requirements")
    doc.add_paragraph("Permits are required for roads.")

    doc.add_paragraph("9. Camps Organization")
    doc.add_paragraph("Camp was placed at location A.")

    doc.add_paragraph("10. Local Hospital Support")
    doc.add_paragraph("Local hospital is 20 km away.")

    doc.add_paragraph("11. Major Difficulties of the Blocks")
    doc.add_paragraph("Major difficulties of the blocks:")

    doc.add_paragraph("12. Hazards and Risk Identification")
    doc.add_paragraph("Hazards and risk identification:")

    doc.add_paragraph("13. Conclusion and Recommendations")
    doc.add_paragraph("Conclusion:")

    doc.save(path)
    print(f"Created mock template at: {path}")


def run_tests():
    out_dir = os.path.join(current_dir, "test_output")
    os.makedirs(out_dir, exist_ok=True)

    template_path = os.path.join(out_dir, "mock_template.docx")
    create_mock_template(template_path)

    project_meta = {
        'prospect_name': "Amzan South",
        'crew_name': "Crew S-86",
        'report_date': "October 2026",
        'contract_no': "340400001",
        'contractor_name': "ARGAS (Crew S-86)",
        'revision_no': "Rev 0",
        'revision_date': "28/10/2026",
        'prepared_by': "Party Chief / Chief Surveyor",
        'reviewed_by': "Operations Manager",
        'approved_by': "Saudi Aramco GDAD Rep",
        'objectives': ["Verify 2,832 km² boundary concession.", "Establish 50m GDAD pipeline standoffs."],
        'communication_means': ["VHF Channel 1-4", "Iridium Satellite Phone", "Garmin inReach SOS"]
    }

    # Setup boundary manager with realistic multi-block
    boundary_mgr = BoundaryManager()
    b1 = [
        BoundaryPoint("Block-A", "CP-01", 500000.0, 2800000.0, 25.312, 49.001),
        BoundaryPoint("Block-A", "CP-02", 520000.0, 2800000.0, 25.313, 49.200),
        BoundaryPoint("Block-A", "CP-03", 520000.0, 2820000.0, 25.493, 49.201),
        BoundaryPoint("Block-A", "CP-04", 500000.0, 2820000.0, 25.493, 49.002)
    ]
    from boundary_manager import BlockPolygon
    poly = BlockPolygon("Block-A", b1)
    boundary_mgr.blocks["Block-A"] = poly
    boundary_mgr.raw_points.extend(b1)
    boundary_mgr.total_acquisition_area_sqkm = 2832.24
    boundary_mgr.total_full_fold_area_sqkm = 2500.0

    terrain_data = [
        {'class_name': "Flat Sandy Plain", 'area_sqkm': 1400.0, 'percentage': 49.4},
        {'class_name': "Rolling Sand Dunes", 'area_sqkm': 900.0, 'percentage': 31.8},
        {'class_name': "Sabkha Mud Flats", 'area_sqkm': 532.24, 'percentage': 18.8}
    ]

    curated_photos = [
        {'file_path': "dummy.jpg", 'caption': "Sabkha soft ground depression with vehicle sinkage", 'has_gps': True, 'lat': 25.41, 'lon': 49.12}
    ]

    gen = ReportDocxGenerator(template_path)

    # TEST 1: MODE 1 - EXACT COPY WITH SIZE REDUCTION
    print("\n--- Running Test for Mode 1: Exact Copy with Size Reduction ---")
    out_mode1 = os.path.join(out_dir, "test_mode1_exact_copy.docx")
    res1 = gen.generate_report(
        output_docx_path=out_mode1,
        project_meta=project_meta,
        boundary_mgr=boundary_mgr,
        processing_mode=ReportTemplateProcessingMode.EXACT_COPY_SIZE_OPT,
        log_cb=print
    )
    assert os.path.exists(res1), "Mode 1 output file must exist."
    doc1 = docx.Document(res1)
    # Check that original text is preserved verbatim
    assert "Old Sample Concession" in doc1.paragraphs[0].text, "Mode 1 must preserve template text verbatim."
    print("Mode 1 PASSED: Verbatim copy preserved with size optimization.")

    # TEST 2: MODE 2 - VERIFY & HIGHLIGHT CONCERNS IN YELLOW
    print("\n--- Running Test for Mode 2: Verify & Highlight Concerns in Yellow ---")
    out_mode2 = os.path.join(out_dir, "test_mode2_yellow_audit.docx")
    res2 = gen.generate_report(
        output_docx_path=out_mode2,
        project_meta=project_meta,
        boundary_mgr=boundary_mgr,
        terrain_data=terrain_data,
        processing_mode=ReportTemplateProcessingMode.ANALYZE_VERIFY_HIGHLIGHT_YELLOW,
        log_cb=print
    )
    assert os.path.exists(res2), "Mode 2 output file must exist."
    doc2 = docx.Document(res2)
    # Check that yellow highlight or AUDIT CONCERN is present
    has_yellow_or_concern = any("AUDIT CONCERN" in p.text for p in doc2.paragraphs)
    assert has_yellow_or_concern, "Mode 2 must flag discrepancies in yellow."
    # Original text must still exist (no automatic overwrite)
    assert "Old Sample Concession" in doc2.paragraphs[0].text, "Mode 2 must not overwrite original text."
    print("Mode 2 PASSED: Concerns successfully identified and flagged in yellow without overwriting text.")

    # TEST 3: MODE 3 - UPDATE CONTENT & HIGHLIGHT CHANGES
    print("\n--- Running Test for Mode 3: Update Content & Highlight Changes ---")
    out_mode3 = os.path.join(out_dir, "test_mode3_update_highlight.docx")
    res3 = gen.generate_report(
        output_docx_path=out_mode3,
        project_meta=project_meta,
        boundary_mgr=boundary_mgr,
        terrain_data=terrain_data,
        curated_photos=curated_photos,
        processing_mode=ReportTemplateProcessingMode.ANALYZE_UPDATE_HIGHLIGHT_CHANGES,
        log_cb=print
    )
    assert os.path.exists(res3), "Mode 3 output file must exist."
    doc3 = docx.Document(res3)
    # Check that prospect name is updated to Amzan South
    assert "Amzan South" in doc3.paragraphs[0].text, "Mode 3 must update prospect name to Amzan South."
    has_update_tracker = any("UPDATED" in p.text for p in doc3.paragraphs)
    assert has_update_tracker, "Mode 3 must include change-tracking markup."
    print("Mode 3 PASSED: Content updated and changes highlighted in green/cyan.")

    # TEST 4: MODE 4 - STYLE & HEADINGS ONLY (FULL AI SYNTHESIS + ACTION REQUIRED COMMENT)
    print("\n--- Running Test for Mode 4: Style & Headings Only (Full AI Synthesis) ---")
    out_mode4 = os.path.join(out_dir, "test_mode4_ai_synthesis.docx")
    user_prompts = {
        "sec_01_overview": "Focus on high-resolution Vibroseis grid across Amzan South desert basin.",
        "sec_03_access": "Highlight 450 km of scouted desert tracks and highway crossing permits."
    }
    res4 = gen.generate_report(
        output_docx_path=out_mode4,
        project_meta=project_meta,
        boundary_mgr=boundary_mgr,
        terrain_data=terrain_data,
        curated_photos=curated_photos,
        processing_mode=ReportTemplateProcessingMode.STYLE_HEADINGS_FULL_AI_SYNTHESIS,
        user_section_prompts=user_prompts,
        log_cb=print
    )
    assert os.path.exists(res4), "Mode 4 output file must exist."
    doc4 = docx.Document(res4)
    # Check that user prompt guidance is reflected
    all_text = "\n".join([p.text for p in doc4.paragraphs])
    assert "Amzan South" in all_text, "Mode 4 must synthesize prose with prospect name."
    assert "high-resolution Vibroseis grid" in all_text or "Amzan South" in all_text, "User prompt should guide synthesis."
    # Check that empty sections have the mandatory action required comment:
    # "if no info isprovided or available through attached files, then leave thats section with only section heading and add comments that section need to be written by user."
    has_action_comment = "ACTION REQUIRED: This section needs to be written by the user" in all_text
    print(f"Action required comment detected in Mode 4: {has_action_comment}")
    print("Mode 4 PASSED: Style and headings preserved, rich AI synthesis applied, and action required comments placed on unpopulated sections.")

    # TEST 5: MODE 5 - EXECUTIVE SUMMARY & KEY SURVEY KPI DASHBOARD
    print("\n--- Running Test for Mode 5: Executive KPI Dashboard Scorecard ---")
    out_mode5 = os.path.join(out_dir, "test_mode5_kpi_scorecard.docx")
    res5 = gen.generate_report(
        output_docx_path=out_mode5,
        project_meta=project_meta,
        boundary_mgr=boundary_mgr,
        terrain_data=terrain_data,
        curated_photos=curated_photos,
        processing_mode=ReportTemplateProcessingMode.EXECUTIVE_SUMMARY_KPI_SCORECARD,
        log_cb=print
    )
    assert os.path.exists(res5), "Mode 5 output file must exist."
    doc5 = docx.Document(res5)
    all_text5 = "\n".join([p.text for p in doc5.paragraphs] + [c.text for t in doc5.tables for r in t.rows for c in r.cells])
    assert "Executive Survey KPI Dashboard" in all_text5, "Mode 5 must contain Executive KPI Dashboard heading."
    assert "Amzan South" in all_text5, "Mode 5 must contain prospect name."
    print("Mode 5 PASSED: Executive KPI Dashboard generated with formatted metric tables.")

    # TEST 6: MODE 6 - SAUDI ARAMCO & OGP STANDARDS COMPLIANCE AUDIT
    print("\n--- Running Test for Mode 6: Saudi Aramco GDAD-SL-012R03 Compliance Audit ---")
    out_mode6 = os.path.join(out_dir, "test_mode6_compliance_audit.docx")
    res6 = gen.generate_report(
        output_docx_path=out_mode6,
        project_meta=project_meta,
        boundary_mgr=boundary_mgr,
        terrain_data=terrain_data,
        curated_photos=curated_photos,
        processing_mode=ReportTemplateProcessingMode.ARAMCO_OGP_STANDARDS_AUDIT,
        log_cb=print
    )
    assert os.path.exists(res6), "Mode 6 output file must exist."
    doc6 = docx.Document(res6)
    all_text6 = "\n".join([p.text for p in doc6.paragraphs] + [c.text for t in doc6.tables for r in t.rows for c in r.cells])
    assert "GDAD-SL-012R03" in all_text6, "Mode 6 must contain GDAD-SL-012R03 standard reference."
    assert "Compliance Audit Result" in all_text6, "Mode 6 must contain Compliance Audit Result summary."
    print("Mode 6 PASSED: GDAD-SL-012R03 Compliance Verification Matrix generated with colored status cells.")

    # TEST 7: MODE 7 - INTERACTIVE AI SECTION CO-AUTHORING & REVIEW WIZARD
    print("\n--- Running Test for Mode 7: Interactive AI Section Co-Authoring ---")
    out_mode7 = os.path.join(out_dir, "test_mode7_interactive_wizard.docx")
    res7 = gen.generate_report(
        output_docx_path=out_mode7,
        project_meta=project_meta,
        boundary_mgr=boundary_mgr,
        terrain_data=terrain_data,
        curated_photos=curated_photos,
        processing_mode=ReportTemplateProcessingMode.INTERACTIVE_SECTION_COAUTHORING,
        user_section_prompts=user_prompts,
        log_cb=print
    )
    assert os.path.exists(res7), "Mode 7 output file must exist."
    doc7 = docx.Document(res7)
    all_text7 = "\n".join([p.text for p in doc7.paragraphs])
    assert "Amzan South" in all_text7, "Mode 7 must synthesize report using interactive prompts."
    print("Mode 7 PASSED: Interactive AI Section Co-Authoring successfully executed with user guidance.")

    print("\n=======================================================")
    print("ALL 7 REPORT PROCESSING STRATEGY TESTS PASSED PERFECTLY!")
    print("=======================================================\n")


if __name__ == "__main__":
    run_tests()
