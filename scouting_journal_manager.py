"""
Scouting Journal & Daily Field Thoughts Manager for ARGAS Seismic Scouting Suite
Allows field scouts to continuously record rough thoughts, voice dictation notes,
and observations throughout the day. Automatically timestamps entries, categorizes
them into the 14 standard Saudi Aramco report sections using semantic keyword matching
and AI assessment, and synthesizes accumulated notes into rich section guidance prompts.
"""

import os
import json
import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any


class JournalEntry:
    """Represents a single timestamped field observation or rough thought."""
    def __init__(self, entry_id: str, timestamp: str, text: str,
                 section_id: str = "sec_01_overview",
                 category_name: str = "Overview",
                 confidence: float = 0.5,
                 lat: Optional[float] = None,
                 lon: Optional[float] = None,
                 source_type: str = "manual_text",
                 tags: Optional[List[str]] = None):
        self.entry_id = entry_id
        self.timestamp = timestamp
        self.text = text
        self.section_id = section_id
        self.category_name = category_name
        self.confidence = confidence
        self.lat = lat
        self.lon = lon
        self.source_type = source_type # 'manual_text', 'speech_to_text', 'mobile_sync', 'photo_note'
        self.tags = tags or []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "timestamp": self.timestamp,
            "text": self.text,
            "section_id": self.section_id,
            "category_name": self.category_name,
            "confidence": self.confidence,
            "lat": self.lat,
            "lon": self.lon,
            "source_type": self.source_type,
            "tags": self.tags
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "JournalEntry":
        return cls(
            entry_id=d.get("entry_id", ""),
            timestamp=d.get("timestamp", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            text=d.get("text", ""),
            section_id=d.get("section_id", "sec_01_overview"),
            category_name=d.get("category_name", "Overview"),
            confidence=float(d.get("confidence", 0.5)),
            lat=d.get("lat"),
            lon=d.get("lon"),
            source_type=d.get("source_type", "manual_text"),
            tags=d.get("tags", [])
        )


class ScoutingJournalManager:
    """
    Manages persistent daily scouting journal entries per project,
    categorizes rough observations, and synthesizes them into report prompts.
    """

    # Section mapping taxonomy matching the 14 Saudi Aramco scouting sections
    SECTION_TAXONOMY: Dict[str, Dict[str, Any]] = {
        "sec_01_overview": {
            "name": "1. Location & Prospect Overview",
            "keywords": ["location", "prospect", "boundary", "area", "utm", "datum", "ain el abd", "concession",
                         "coordinates", "limits", "block", "size", "perimeter", "eastern province", "geodetic"],
            "weight": 1.0
        },
        "sec_02_team": {
            "name": "2. Scouting Team & Organization",
            "keywords": ["team", "crew", "surveyor", "party chief", "driver", "mechanic", "personnel", "roster",
                         "organization", "fleet", "equipment", "vibrator", "dozer", "toyota", "land cruiser", "pickup"],
            "weight": 1.0
        },
        "sec_03_access": {
            "name": "3. Access to Prospect & Main Highways",
            "keywords": ["access", "highway", "road", "route", "asphalt", "track", "graded", "gravel track",
                         "drive", "transit", "gate", "checkpoint", "tire", "deflation", "psi", "crossing"],
            "weight": 1.0
        },
        "sec_04_objectives": {
            "name": "4. Objectives of the Scouting",
            "keywords": ["objective", "goal", "target", "purpose", "scope", "mission", "reconnaissance",
                         "directives", "verification", "preliminary", "requirement"],
            "weight": 1.0
        },
        "sec_05_comms": {
            "name": "5. Communication Means & Emergency Contact",
            "keywords": ["communication", "radio", "vhf", "repeater", "satellite", "thuraya", "inmarsat", "iridium",
                         "phone", "mobile", "coverage", "signal", "dead zone", "sos", "emergency contact", "ivms"],
            "weight": 1.1
        },
        "sec_06_terrain": {
            "name": "6. Terrain Description & Classification",
            "keywords": ["terrain", "geomorphology", "surface", "sand", "dune", "dunes", "rolling sand", "dikaka",
                         "sabkha", "subkha", "escarpment", "jebel", "rocky", "wadi", "depression", "mud", "soil"],
            "weight": 1.1
        },
        "sec_07_remoteness": {
            "name": "7. Remoteness and Operation Area Types",
            "keywords": ["remoteness", "remote", "area type", "contractual", "distance", "fuel", "water supply",
                         "staging", "isolated", "fly camp", "commute", "travel time"],
            "weight": 1.0
        },
        "sec_08_permitting": {
            "name": "8. Permitting Requirements & Clearances",
            "keywords": ["permit", "clearance", "permission", "aramco", "ministry", "police", "border guard",
                         "security", "pipeline crossing", "easement", "right of way", "gate pass", "approval"],
            "weight": 1.2
        },
        "sec_09_camps": {
            "name": "9. Camps Organization & Logistics",
            "keywords": ["camp", "base camp", "fly camp", "campsite", "accommodation", "water well", "generator",
                         "electric", "catering", "waste", "sewage", "staging area", "workshop", "trailer"],
            "weight": 1.0
        },
        "sec_10_hospitals": {
            "name": "10. Hospital Support & Medevac Logistics",
            "keywords": ["hospital", "clinic", "ambulance", "paramedic", "doctor", "medical", "medevac",
                         "trauma", "evacuation", "helipad", "lz", "emergency room", "health center", "first aid"],
            "weight": 1.3
        },
        "sec_11_difficulties": {
            "name": "11. Major Difficulties & Obstacles",
            "keywords": ["difficulty", "difficulties", "obstacle", "problem", "stuck", "soft sand", "treacherous",
                         "steep", "high dune", "pipeline cluster", "power line", "fence", "military", "restricted"],
            "weight": 1.1
        },
        "sec_12_hazards": {
            "name": "12. Hazards & Risk Assessment (HIRA)",
            "keywords": ["hazard", "risk", "hira", "hse", "safety", "heat", "heat stroke", "dehydration",
                         "storm", "shamal", "dust", "fog", "snake", "scorpion", "wildlife", "high voltage", "uxo"],
            "weight": 1.2
        },
        "sec_13_conclusion": {
            "name": "13. Conclusion & Recommendations",
            "keywords": ["conclusion", "recommendation", "viable", "feasibility", "feasible", "proceed",
                         "verdict", "caution", "mitigation", "summary", "operational advice"],
            "weight": 1.0
        },
        "sec_14_photos": {
            "name": "14. Field Photographs & Plates",
            "keywords": ["photo", "photograph", "camera", "picture", "plate", "image", "visual", "shot"],
            "weight": 0.8
        }
    }

    def __init__(self, storage_dir: Optional[str] = None, project_id: Optional[str] = None):
        if storage_dir is None:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            self.storage_dir = os.path.join(base_dir, "scouting_journals")
        else:
            self.storage_dir = storage_dir

        os.makedirs(self.storage_dir, exist_ok=True)
        self.current_project_id = project_id or "Default_Scout"
        self.entries: List[JournalEntry] = []
        self.trip_metadata: Dict[str, Any] = {
            "trip_id": "",
            "start_date": "",
            "scout_name": "",
            "crew": "Crew S-86",
            "general_notes": ""
        }
        if project_id:
            self.load_project(project_id)

    def _get_project_file_path(self, project_id: str) -> str:
        safe_id = re.sub(r'[^a-zA-Z0-9_\-]', '_', project_id) or "Default_Scout"
        return os.path.join(self.storage_dir, f"{safe_id}_journal.json")

    def load_project(self, project_id: str) -> bool:
        """Loads journal entries and metadata for the specified project."""
        self.current_project_id = project_id.strip() or "Default_Scout"
        file_path = self._get_project_file_path(self.current_project_id)

        self.entries.clear()
        if os.path.exists(file_path):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.trip_metadata = data.get("trip_metadata", {})
                    raw_entries = data.get("entries", [])
                    for r in raw_entries:
                        self.entries.append(JournalEntry.from_dict(r))
                return True
            except Exception as e:
                print(f"Error loading journal for {project_id}: {e}")
                return False
        else:
            # Initialize empty project journal
            self.trip_metadata = {
                "trip_id": f"TRIP_{datetime.now().strftime('%Y%m%d')}",
                "start_date": datetime.now().strftime("%Y-%m-%d"),
                "scout_name": "Field Scout",
                "crew": "Crew S-86",
                "general_notes": f"Scouting journal for {project_id}"
            }
            return False

    def save_project(self) -> bool:
        """Saves current journal entries and trip metadata to disk."""
        file_path = self._get_project_file_path(self.current_project_id)
        try:
            data = {
                "project_id": self.current_project_id,
                "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "trip_metadata": self.trip_metadata,
                "entry_count": len(self.entries),
                "entries": [e.to_dict() for e in self.entries]
            }
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"Error saving journal for {self.current_project_id}: {e}")
            return False

    def categorize_thought(self, text: str) -> Tuple[str, str, float]:
        """
        Classifies rough field text, bullet points, or speech-to-text dictation
        into one of the 14 standard Saudi Aramco report sections.
        Returns: (section_id, category_name, confidence)
        """
        clean_text = text.lower()
        best_section_id = "sec_01_overview"
        best_score = 0.0

        for sec_id, info in self.SECTION_TAXONOMY.items():
            score = 0.0
            weight = info["weight"]
            for kw in info["keywords"]:
                # Whole word or partial match
                if re.search(r'\b' + re.escape(kw) + r'\b', clean_text):
                    score += 1.5 * weight
                elif kw in clean_text:
                    score += 0.8 * weight

            if score > best_score:
                best_score = score
                best_section_id = sec_id

        # Calculate normalized confidence
        conf = min(0.95, max(0.40, best_score / 4.0)) if best_score > 0 else 0.35
        cat_name = self.SECTION_TAXONOMY[best_section_id]["name"]
        return best_section_id, cat_name, round(conf, 2)

    def add_entry(self, text: str,
                  section_id: Optional[str] = None,
                  lat: Optional[float] = None,
                  lon: Optional[float] = None,
                  source_type: str = "manual_text",
                  timestamp: Optional[str] = None) -> JournalEntry:
        """Adds a field thought, auto-categorizing it if section_id is not specified."""
        clean_text = text.strip()
        ts = timestamp or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry_id = f"JRN_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{len(self.entries)+1}"

        if not section_id or section_id not in self.SECTION_TAXONOMY:
            sec_id, cat_name, conf = self.categorize_thought(clean_text)
        else:
            sec_id = section_id
            cat_name = self.SECTION_TAXONOMY[sec_id]["name"]
            conf = 0.90

        entry = JournalEntry(
            entry_id=entry_id,
            timestamp=ts,
            text=clean_text,
            section_id=sec_id,
            category_name=cat_name,
            confidence=conf,
            lat=lat,
            lon=lon,
            source_type=source_type
        )

        self.entries.append(entry)
        self.save_project()
        return entry

    def delete_entry(self, entry_id: str) -> bool:
        """Removes an entry by its ID."""
        initial_len = len(self.entries)
        self.entries = [e for e in self.entries if e.entry_id != entry_id]
        if len(self.entries) < initial_len:
            self.save_project()
            return True
        return False

    def update_entry(self, entry_id: str, new_text: str, new_section_id: str) -> bool:
        """Updates text and/or category of an existing entry."""
        for e in self.entries:
            if e.entry_id == entry_id:
                e.text = new_text.strip()
                e.section_id = new_section_id
                e.category_name = self.SECTION_TAXONOMY.get(new_section_id, {}).get("name", "Custom")
                self.save_project()
                return True
        return False

    def get_entries_by_section(self, section_id: str) -> List[JournalEntry]:
        """Returns all entries assigned to a specific section."""
        return [e for e in self.entries if e.section_id == section_id]

    def synthesize_section_prompts(self) -> Dict[str, str]:
        """
        Aggregates all daily field thoughts chronologically per section,
        formatting them into polished, structured guidance prompts ready to pre-fill
        the Section Prompts Dialog and feed into AI report generation.
        """
        prompts: Dict[str, str] = {}

        for sec_id, info in self.SECTION_TAXONOMY.items():
            sec_entries = self.get_entries_by_section(sec_id)
            if not sec_entries:
                continue

            sec_title = info["name"]
            lines = [f"Field Scouting Observations for {sec_title}:"]

            for idx, entry in enumerate(sec_entries, start=1):
                gps_str = f" [GPS: {entry.lat:.5f}°N, {entry.lon:.5f}°E]" if (entry.lat and entry.lon) else ""
                lines.append(f"• ({entry.timestamp}){gps_str} {entry.text}")

            prompts[sec_id] = "\n".join(lines)

        return prompts

    def get_summary_stats(self) -> Dict[str, Any]:
        """Returns statistical overview of recorded thoughts across sections."""
        stats = {
            "total_entries": len(self.entries),
            "by_section": {},
            "first_entry_time": self.entries[0].timestamp if self.entries else "N/A",
            "latest_entry_time": self.entries[-1].timestamp if self.entries else "N/A"
        }
        for sec_id in self.SECTION_TAXONOMY:
            count = sum(1 for e in self.entries if e.section_id == sec_id)
            if count > 0:
                stats["by_section"][sec_id] = count
        return stats

