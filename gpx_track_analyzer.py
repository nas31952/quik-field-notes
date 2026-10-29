"""
GPX and KML Track Analyzer for ARGAS Scouting Suite
Extracts scouting dates, duration, total kilometers scouted,
and trip timing directly from field GPS track files.
"""

import os
import math
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import List, Dict, Tuple, Set


class GpxTrackAnalyzer:
    """Analyzes GPX/KML track logs to determine operational dates and metrics."""

    @staticmethod
    def parse_track_file(file_path: str) -> Dict:
        """
        Parses GPX or KML track file and returns operational metrics:
        - dates: sorted list of unique scouting dates (YYYY-MM-DD)
        - total_distance_km: total kilometers traveled
        - point_count: total GPS fixes recorded
        - start_time, end_time: datetime of first and last fix
        - bounding_box: [min_lat, min_lon, max_lat, max_lon]
        """
        if not os.path.exists(file_path):
            return {'error': f"File not found: {file_path}"}

        ext = os.path.splitext(file_path)[1].lower()
        if ext == '.gpx':
            return GpxTrackAnalyzer._parse_gpx(file_path)
        elif ext in ('.kml', '.kmz'):
            return GpxTrackAnalyzer._parse_kml(file_path)
        else:
            return {'error': f"Unsupported track format: {ext}"}

    @staticmethod
    def _parse_gpx(file_path: str) -> Dict:
        points = []
        unique_dates: Set[str] = set()

        try:
            tree = ET.parse(file_path)
            root = tree.getroot()

            # Handle XML namespace
            ns = ""
            if root.tag.startswith('{'):
                ns = root.tag.split('}')[0] + '}'

            for trkpt in root.iter(f"{ns}trkpt"):
                lat = float(trkpt.attrib.get('lat', 0.0))
                lon = float(trkpt.attrib.get('lon', 0.0))
                time_elem = trkpt.find(f"{ns}time")

                pt_time = None
                if time_elem is not None and time_elem.text:
                    t_str = time_elem.text.strip()
                    try:
                        # Standard ISO format: 2026-08-09T07:15:30Z
                        clean_str = t_str.replace('Z', '+00:00')
                        pt_time = datetime.fromisoformat(clean_str)
                        unique_dates.add(pt_time.strftime('%Y-%m-%d'))
                    except Exception:
                        pass

                points.append((lat, lon, pt_time))

            if not points:
                # Check for waypoints (wpt) if no trackpoints
                for wpt in root.iter(f"{ns}wpt"):
                    lat = float(wpt.attrib.get('lat', 0.0))
                    lon = float(wpt.attrib.get('lon', 0.0))
                    time_elem = wpt.find(f"{ns}time")
                    pt_time = None
                    if time_elem is not None and time_elem.text:
                        try:
                            clean_str = time_elem.text.strip().replace('Z', '+00:00')
                            pt_time = datetime.fromisoformat(clean_str)
                            unique_dates.add(pt_time.strftime('%Y-%m-%d'))
                        except Exception:
                            pass
                    points.append((lat, lon, pt_time))

            if not points:
                return {'error': "No GPS track points found in GPX."}

            # Distance calculation (Haversine)
            total_dist_km = 0.0
            min_lat = min(p[0] for p in points)
            max_lat = max(p[0] for p in points)
            min_lon = min(p[1] for p in points)
            max_lon = max(p[1] for p in points)

            for i in range(len(points) - 1):
                lat1, lon1, _ = points[i]
                lat2, lon2, _ = points[i + 1]
                total_dist_km += GpxTrackAnalyzer.haversine_distance(lat1, lon1, lat2, lon2)

            sorted_dates = sorted(list(unique_dates))
            timed_pts = [p for p in points if p[2] is not None]

            start_t = timed_pts[0][2].strftime('%Y-%m-%d %H:%M') if timed_pts else None
            end_t = timed_pts[-1][2].strftime('%Y-%m-%d %H:%M') if timed_pts else None

            return {
                'success': True,
                'format': 'GPX',
                'point_count': len(points),
                'total_distance_km': round(total_dist_km, 2),
                'unique_dates': sorted_dates,
                'start_date': sorted_dates[0] if sorted_dates else None,
                'end_date': sorted_dates[-1] if sorted_dates else None,
                'scouting_days_count': len(sorted_dates),
                'start_time': start_t,
                'end_time': end_t,
                'bbox': [round(min_lat, 6), round(min_lon, 6), round(max_lat, 6), round(max_lon, 6)]
            }

        except Exception as e:
            return {'error': f"Failed to parse GPX: {str(e)}"}

    @staticmethod
    def _parse_kml(file_path: str) -> Dict:
        points = []
        try:
            tree = ET.parse(file_path)
            root = tree.getroot()
            ns = ""
            if root.tag.startswith('{'):
                ns = root.tag.split('}')[0] + '}'

            for coord_elem in root.iter(f"{ns}coordinates"):
                raw_text = coord_elem.text or ""
                for token in raw_text.strip().split():
                    parts = token.split(',')
                    if len(parts) >= 2:
                        lon = float(parts[0])
                        lat = float(parts[1])
                        points.append((lat, lon, None))

            if not points:
                return {'error': "No coordinates found in KML."}

            total_dist_km = 0.0
            for i in range(len(points) - 1):
                lat1, lon1, _ = points[i]
                lat2, lon2, _ = points[i + 1]
                total_dist_km += GpxTrackAnalyzer.haversine_distance(lat1, lon1, lat2, lon2)

            min_lat = min(p[0] for p in points)
            max_lat = max(p[0] for p in points)
            min_lon = min(p[1] for p in points)
            max_lon = max(p[1] for p in points)

            return {
                'success': True,
                'format': 'KML',
                'point_count': len(points),
                'total_distance_km': round(total_dist_km, 2),
                'unique_dates': [],
                'start_date': None,
                'end_date': None,
                'scouting_days_count': 0,
                'start_time': None,
                'end_time': None,
                'bbox': [round(min_lat, 6), round(min_lon, 6), round(max_lat, 6), round(max_lon, 6)]
            }
        except Exception as e:
            return {'error': f"Failed to parse KML: {str(e)}"}

    @staticmethod
    def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Returns distance in km between two lat/lon pairs."""
        r = 6371.0
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = (math.sin(dlat / 2.0) ** 2 +
             math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
             math.sin(dlon / 2.0) ** 2)
        c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
        return r * c
