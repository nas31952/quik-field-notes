"""
Scouting Package Manager for ARGAS Seismic Scouting Suite
Handles exporting and importing standardized field scouting packages (*.scoutpkg / *.zip).
Allows field scouts using the mobile app (or standalone scout units) to seamlessly export
georeferenced photos, GPS tracks, waypoints, and timestamped journal thoughts as a single file,
and automatically ingests and categorizes all contents into the desktop SeismicScoutingSuite.
"""

import os
import json
import zipfile
import shutil
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple

from scouting_journal_manager import ScoutingJournalManager, JournalEntry


class ScoutingPackageManager:
    """Exports and imports portable *.scoutpkg field bundles."""

    PACKAGE_VERSION = "2.0"

    @classmethod
    def export_package(cls,
                       output_pkg_path: str,
                       project_id: str,
                       crew_name: str = "Crew S-86",
                       scout_name: str = "Field Scout",
                       journal_manager: Optional[ScoutingJournalManager] = None,
                       photo_list: Optional[List[Dict[str, Any]]] = None,
                       waypoints: Optional[List[Dict[str, Any]]] = None,
                       track_file_path: Optional[str] = None,
                       log_cb=print) -> str:
        """
        Creates a standalone *.scoutpkg (zip format) bundling all field data.
        """
        if not output_pkg_path.lower().endswith(('.scoutpkg', '.zip')):
            output_pkg_path += ".scoutpkg"

        os.makedirs(os.path.dirname(os.path.abspath(output_pkg_path)), exist_ok=True)
        log_cb(f"Exporting scouting package to: {output_pkg_path}...")

        photos = photo_list or []
        wps = waypoints or []
        j_entries = journal_manager.entries if journal_manager else []

        manifest = {
            "package_version": cls.PACKAGE_VERSION,
            "project_id": project_id,
            "crew_name": crew_name,
            "scout_name": scout_name,
            "export_timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "summary": {
                "photo_count": len(photos),
                "waypoint_count": len(wps),
                "journal_count": len(j_entries),
                "has_track": bool(track_file_path and os.path.exists(track_file_path))
            }
        }

        with zipfile.ZipFile(output_pkg_path, "w", zipfile.ZIP_DEFLATED) as zf:
            # 1. Manifest
            zf.writestr("manifest.json", json.dumps(manifest, indent=2, ensure_ascii=False))

            # 2. Journal entries
            j_data = {
                "project_id": project_id,
                "entries": [e.to_dict() for e in j_entries]
            }
            zf.writestr("journal.json", json.dumps(j_data, indent=2, ensure_ascii=False))

            # 3. Waypoints (JSON and standard GPX format)
            zf.writestr("waypoints.json", json.dumps(wps, indent=2, ensure_ascii=False))
            gpx_wps_content = cls._generate_waypoints_gpx(wps, project_id)
            zf.writestr("waypoints.gpx", gpx_wps_content)

            # 4. GPS Track file
            if track_file_path and os.path.exists(track_file_path):
                zf.write(track_file_path, arcname="track.gpx")

            # 5. Photos and Photo Metadata sidecar
            photo_metadata = []
            for p in photos:
                src_path = p.get('file_path', '')
                fname = p.get('filename', os.path.basename(src_path))
                if src_path and os.path.exists(src_path):
                    arc_photo_name = f"photos/{fname}"
                    zf.write(src_path, arcname=arc_photo_name)
                    photo_metadata.append({
                        "filename": fname,
                        "lat": p.get('lat'),
                        "lon": p.get('lon'),
                        "elevation": p.get('elevation'),
                        "has_gps": p.get('has_gps', False),
                        "caption": p.get('caption', ''),
                        "note": p.get('note', ''),
                        "category": p.get('category', 'General'),
                        "is_rejected": p.get('is_rejected', False)
                    })

            zf.writestr("photos.json", json.dumps(photo_metadata, indent=2, ensure_ascii=False))

        log_cb(f"Package successfully created ({len(photos)} photos, {len(wps)} waypoints, {len(j_entries)} journal thoughts).")
        return output_pkg_path

    @classmethod
    def import_package(cls,
                       pkg_path: str,
                       target_photos_dir: str,
                       journal_manager: Optional[ScoutingJournalManager] = None,
                       log_cb=print) -> Dict[str, Any]:
        """
        Unpacks and integrates a *.scoutpkg file:
        - Extracts photos to target_photos_dir
        - Ingests journal entries into journal_manager
        - Ingests waypoints and track files
        Returns dictionary of imported data ready for UI binding.
        """
        if not os.path.exists(pkg_path):
            raise FileNotFoundError(f"Package file not found: {pkg_path}")

        os.makedirs(target_photos_dir, exist_ok=True)
        log_cb(f"Reading scouting package: {os.path.basename(pkg_path)}...")

        imported_photos = []
        imported_waypoints = []
        imported_journal_entries = []
        track_dest_path = None
        manifest = {}

        with zipfile.ZipFile(pkg_path, "r") as zf:
            namelist = zf.namelist()

            # 1. Read manifest
            if "manifest.json" in namelist:
                try:
                    manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
                    log_cb(f"Package metadata: Project '{manifest.get('project_id')}', Crew '{manifest.get('crew_name')}'")
                except Exception as e:
                    log_cb(f"Manifest parse warning: {e}")

            project_id = manifest.get("project_id", "Imported_Scout")

            # 2. Extract photos
            photos_meta_dict = {}
            if "photos.json" in namelist:
                try:
                    raw_meta = json.loads(zf.read("photos.json").decode("utf-8"))
                    for pm in raw_meta:
                        photos_meta_dict[pm.get("filename")] = pm
                except Exception:
                    pass

            for item in namelist:
                if item.startswith("photos/") and not item.endswith("/"):
                    fname = os.path.basename(item)
                    dest_path = os.path.join(target_photos_dir, fname)
                    with zf.open(item) as src, open(dest_path, "wb") as dst:
                        shutil.copyfileobj(src, dst)

                    meta = photos_meta_dict.get(fname, {})
                    imported_photos.append({
                        "file_path": dest_path,
                        "filename": fname,
                        "lat": meta.get("lat"),
                        "lon": meta.get("lon"),
                        "elevation": meta.get("elevation"),
                        "has_gps": meta.get("has_gps", (meta.get("lat") is not None and meta.get("lon") is not None)),
                        "caption": meta.get("caption", ""),
                        "note": meta.get("note", ""),
                        "category": meta.get("category", "General"),
                        "is_rejected": meta.get("is_rejected", False)
                    })

            log_cb(f"Extracted {len(imported_photos)} georeferenced photos to: {target_photos_dir}")

            # 3. Extract GPS Track
            if "track.gpx" in namelist:
                track_dest_path = os.path.join(target_photos_dir, f"{project_id}_scout_track.gpx")
                with zf.open("track.gpx") as src, open(track_dest_path, "wb") as dst:
                    shutil.copyfileobj(src, dst)
                log_cb(f"Extracted GPS track log to: {track_dest_path}")

            # 4. Extract Waypoints
            if "waypoints.json" in namelist:
                try:
                    imported_waypoints = json.loads(zf.read("waypoints.json").decode("utf-8"))
                    log_cb(f"Loaded {len(imported_waypoints)} waypoints.")
                except Exception as e:
                    log_cb(f"Waypoints load warning: {e}")

            # 5. Extract and Ingest Journal Entries
            if "journal.json" in namelist and journal_manager:
                try:
                    j_raw = json.loads(zf.read("journal.json").decode("utf-8"))
                    entries_list = j_raw.get("entries", [])
                    journal_manager.load_project(project_id)
                    for item in entries_list:
                        entry = JournalEntry.from_dict(item)
                        # Re-categorize if needed to ensure alignment with active taxonomy
                        if not entry.category_name or entry.section_id not in journal_manager.SECTION_TAXONOMY:
                            sec_id, cat_name, conf = journal_manager.categorize_thought(entry.text)
                            entry.section_id = sec_id
                            entry.category_name = cat_name
                            entry.confidence = conf
                        journal_manager.entries.append(entry)
                        imported_journal_entries.append(entry)

                    journal_manager.save_project()
                    log_cb(f"Ingested {len(imported_journal_entries)} daily field thoughts into project journal '{project_id}'.")
                except Exception as e:
                    log_cb(f"Journal ingest warning: {e}")

        return {
            "project_id": manifest.get("project_id", "Imported_Scout"),
            "crew_name": manifest.get("crew_name", "Crew S-86"),
            "scout_name": manifest.get("scout_name", "Field Scout"),
            "photos": imported_photos,
            "waypoints": imported_waypoints,
            "journal_entries": imported_journal_entries,
            "track_path": track_dest_path,
            "manifest": manifest
        }

    @staticmethod
    def _generate_waypoints_gpx(waypoints: List[Dict[str, Any]], project_id: str) -> str:
        """Generates standard GPX 1.1 XML string for waypoints."""
        xml_lines = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<gpx version="1.1" creator="ARGAS Seismic Scouting Suite" xmlns="http://www.topografix.com/GPX/1/1">'
        ]
        for wp in waypoints:
            lat = wp.get('lat')
            lon = wp.get('lon')
            if lat is not None and lon is not None:
                name = wp.get('name', 'WP')
                note = wp.get('note', '')
                ele = wp.get('elevation', 0.0)
                xml_lines.append(f'  <wpt lat="{lat}" lon="{lon}">')
                xml_lines.append(f'    <name>{name}</name>')
                xml_lines.append(f'    <desc>{note}</desc>')
                xml_lines.append(f'    <ele>{ele}</ele>')
                xml_lines.append('  </wpt>')
        xml_lines.append('</gpx>')
        return "\n".join(xml_lines)

