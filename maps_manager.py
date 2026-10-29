"""
Maps Manager for ARGAS Scouting Report Generator
Supports core optional standard maps (1, 2, 3, 4, 5, 6, 8, 9)
and user-defined custom maps with section targets, captions, and descriptions.
"""

import os
import json
from typing import List, Dict, Optional


class MapFigureConfig:
    def __init__(self, key: str, default_title: str, target_section: str,
                 is_custom: bool = False, file_path: str = "",
                 description: str = "", enabled: bool = True):
        self.key = key                     # Unique key (e.g., 'map_1', 'custom_1')
        self.is_custom = is_custom         # True if user-added
        self.enabled = enabled             # Included in report
        self.file_path = file_path         # Path to image file
        self.title = default_title         # Caption/Figure label
        self.target_section = target_section # e.g., 'Section 1', 'Section 6', 'Section 11'
        self.description = description     # Detailed explanatory narrative

    def to_dict(self) -> Dict:
        return {
            'key': self.key,
            'is_custom': self.is_custom,
            'enabled': self.enabled,
            'file_path': self.file_path,
            'title': self.title,
            'target_section': self.target_section,
            'description': self.description
        }

    @classmethod
    def from_dict(cls, d: Dict) -> 'MapFigureConfig':
        return cls(
            key=d.get('key', ''),
            default_title=d.get('title', ''),
            target_section=d.get('target_section', 'Section 6'),
            is_custom=d.get('is_custom', False),
            file_path=d.get('file_path', ''),
            description=d.get('description', ''),
            enabled=d.get('enabled', True)
        )


REPORT_SECTION_CHOICES = [
    "Section 1: Location & Prospect Overview",
    "Section 3: Access to Prospect & Road Networks",
    "Section 4: Objectives of the Scouting",
    "Section 5: Communication Means",
    "Section 6: Terrain Description & Classification",
    "Section 7: Remoteness & Operational Area",
    "Section 8: Permitting Requirements & Third-Party Assets",
    "Section 9: Camps Organization & Staging Areas",
    "Section 10: Local Hospital Support & Medevac",
    "Section 11: Major Difficulties of the Blocks",
    "Section 12: Hazards and Risk Identification",
    "Section 13: Conclusion & Recommendations"
]


class MapsManager:
    """Manages the full suite of report maps (standard optional + custom)."""

    def __init__(self):
        self.maps: Dict[str, MapFigureConfig] = {}
        self.init_standard_maps()

    def init_standard_maps(self):
        """Initializes the core 8 optional maps."""
        standards = [
            MapFigureConfig('map_1', 'Figure 1: Regional Access and Prospect Location Map', 'Section 1: Location & Prospect Overview'),
            MapFigureConfig('map_2', 'Figure 2: Survey Prospect Boundary and Block Division Map', 'Section 1: Location & Prospect Overview'),
            MapFigureConfig('map_3', 'Figure 3: Prospect Topographic Elevation (DEM) Map', 'Section 6: Terrain Description & Classification'),
            MapFigureConfig('map_4', 'Figure 4: Ground Slope Gradient and Micro-Relief Map', 'Section 6: Terrain Description & Classification'),
            MapFigureConfig('map_5', 'Figure 5: Geomorphic Surface Terrain Classification Map', 'Section 6: Terrain Description & Classification'),
            MapFigureConfig('map_6', 'Figure 6: Operational Terrain Hazards & Sabkha Geofences', 'Section 11: Major Difficulties of the Blocks'),
            MapFigureConfig('map_8', 'Figure 8: Proposed Main Seismic Camp, Fly Camps & Water Points', 'Section 9: Camps Organization & Staging Areas'),
            MapFigureConfig('map_9', 'Figure 9: Emergency Medical Evacuation Routes & Hospital Distance Map', 'Section 10: Local Hospital Support & Medevac'),
        ]
        for m in standards:
            self.maps[m.key] = m

    def add_custom_map(self, title: str, file_path: str, target_section: str, description: str) -> str:
        """Adds a custom user map figure and returns its key."""
        custom_idx = len([k for k in self.maps if k.startswith('custom_')]) + 1
        key = f"custom_{custom_idx}"
        cfg = MapFigureConfig(
            key=key,
            default_title=title,
            target_section=target_section,
            is_custom=True,
            file_path=file_path,
            description=description,
            enabled=True
        )
        self.maps[key] = cfg
        return key

    def remove_map(self, key: str) -> bool:
        """Removes a custom map (standard maps are disabled rather than deleted)."""
        if key in self.maps:
            if self.maps[key].is_custom:
                del self.maps[key]
            else:
                self.maps[key].enabled = False
                self.maps[key].file_path = ""
            return True
        return False

    def get_active_maps(self) -> List[MapFigureConfig]:
        """Returns all enabled maps that have a valid file path."""
        active = []
        for m in self.maps.values():
            if m.enabled and m.file_path and os.path.exists(m.file_path):
                active.append(m)
        return active

    def get_maps_by_section(self) -> Dict[str, List[MapFigureConfig]]:
        """Groups active maps by target section."""
        by_sec: Dict[str, List[MapFigureConfig]] = {}
        for m in self.get_active_maps():
            sec = m.target_section.split(':')[0].strip()
            if sec not in by_sec:
                by_sec[sec] = []
            by_sec[sec].append(m)
        return by_sec

    def to_dict(self) -> Dict:
        return {k: m.to_dict() for k, m in self.maps.items()}

    def load_from_dict(self, d: Dict):
        self.maps.clear()
        self.init_standard_maps()
        for k, v in d.items():
            self.maps[k] = MapFigureConfig.from_dict(v)
