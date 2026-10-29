"""
Unit test for ScoutingJournalManager and ScoutingPackageManager
"""

import os
import shutil
import tempfile
from scouting_journal_manager import ScoutingJournalManager
from scouting_package_manager import ScoutingPackageManager


def run_journal_tests():
    temp_dir = tempfile.mkdtemp(prefix="test_scout_jrn_")
    try:
        jm = ScoutingJournalManager(storage_dir=temp_dir)
        jm.load_project("Test_Amzan_South")

        # 1. Test auto-categorization
        t1 = "Main asphalt road stops at km 45, then soft sabkha track begins. Deflate tire to 15 PSI."
        e1 = jm.add_entry(t1, lat=24.12345, lon=50.54321)
        assert e1.section_id == "sec_03_access", f"Expected sec_03_access, got {e1.section_id}"
        print(f"Thought 1 categorized as: {e1.category_name} (conf: {e1.confidence}) - PASS")

        t2 = "Nearest emergency hospital is Abqaiq Health Center, approx 45 minutes drive away. Ambulance route scouted."
        e2 = jm.add_entry(t2, lat=24.13000, lon=50.55000)
        assert e2.section_id == "sec_10_hospitals", f"Expected sec_10_hospitals, got {e2.section_id}"
        print(f"Thought 2 categorized as: {e2.category_name} (conf: {e2.confidence}) - PASS")

        t3 = "Must obtain written security clearance from border guard and Aramco pipeline department for swath 12."
        e3 = jm.add_entry(t3)
        assert e3.section_id == "sec_08_permitting", f"Expected sec_08_permitting, got {e3.section_id}"
        print(f"Thought 3 categorized as: {e3.category_name} (conf: {e3.confidence}) - PASS")

        t4 = "Extreme heat stress observed around 1 PM (>47C ambient), risk of dehydration for geophone crew."
        e4 = jm.add_entry(t4)
        assert e4.section_id == "sec_12_hazards", f"Expected sec_12_hazards, got {e4.section_id}"
        print(f"Thought 4 categorized as: {e4.category_name} (conf: {e4.confidence}) - PASS")

        # 2. Test prompt synthesis
        prompts = jm.synthesize_section_prompts()
        assert "sec_03_access" in prompts
        assert "sec_10_hospitals" in prompts
        assert "sec_08_permitting" in prompts
        assert "sec_12_hazards" in prompts
        print(f"Prompts synthesized for {len(prompts)} sections - PASS")
        print("Sample Access Prompt:\n", prompts["sec_03_access"][:160])

        # 3. Test packaging export
        pkg_out = os.path.join(temp_dir, "test_field_package.scoutpkg")
        fake_photos = [
            {"file_path": "", "filename": "sample_photo.jpg", "lat": 24.12, "lon": 50.54, "has_gps": True, "note": "Sabkha margin"}
        ]
        # Create a real dummy photo file
        dummy_img = os.path.join(temp_dir, "sample_photo.jpg")
        with open(dummy_img, "wb") as f:
            f.write(b"\xFF\xD8\xFF\xE0\x00\x10JFIF" + b"\x00" * 100)
        fake_photos[0]["file_path"] = dummy_img

        fake_wps = [
            {"name": "WP001", "lat": 24.123, "lon": 50.543, "elevation": 12.0, "note": "Sabkha Gate Entry"}
        ]

        pkg_path = ScoutingPackageManager.export_package(
            output_pkg_path=pkg_out,
            project_id="Test_Amzan_South",
            crew_name="Crew S-86",
            scout_name="Nasrullah Khan",
            journal_manager=jm,
            photo_list=fake_photos,
            waypoints=fake_wps
        )
        assert os.path.exists(pkg_path), "Package file must be created"
        print(f"Package created: {pkg_path} (size: {os.path.getsize(pkg_path)} bytes) - PASS")

        # 4. Test packaging import
        unpack_photos_dir = os.path.join(temp_dir, "unpacked_photos")
        jm_new = ScoutingJournalManager(storage_dir=temp_dir)
        import_res = ScoutingPackageManager.import_package(
            pkg_path=pkg_path,
            target_photos_dir=unpack_photos_dir,
            journal_manager=jm_new
        )

        assert len(import_res["photos"]) == 1, "Imported photo count mismatch"
        assert len(import_res["waypoints"]) == 1, "Imported waypoint count mismatch"
        assert len(import_res["journal_entries"]) == 4, "Imported journal entries count mismatch"
        print(f"Package successfully imported and integrated into new journal ({len(import_res['journal_entries'])} entries) - PASS")

        print("\n=======================================================")
        print("ALL JOURNAL AND PACKAGE TESTS PASSED 100%!")
        print("=======================================================")

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    run_journal_tests()

