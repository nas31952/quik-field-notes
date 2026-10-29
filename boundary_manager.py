"""
Boundary Manager for ARGAS Scouting Report Generator
Handles multi-block prospect coordinates ingestion, geometric calculations,
coordinate transformations, and automated generation of Table 5 (Prospect Information).
"""

import os
import csv
import math
from typing import List, Dict, Tuple, Optional


class BoundaryPoint:
    def __init__(self, block_name: str, point_id: str, easting: float, northing: float,
                 latitude: Optional[float] = None, longitude: Optional[float] = None,
                 notes: str = ""):
        self.block_name = str(block_name).strip()
        self.point_id = str(point_id).strip()
        self.easting = float(easting)
        self.northing = float(northing)
        self.latitude = float(latitude) if latitude is not None else None
        self.longitude = float(longitude) if longitude is not None else None
        self.notes = str(notes).strip()


class BlockPolygon:
    def __init__(self, block_name: str, points: List[BoundaryPoint]):
        self.block_name = block_name
        self.points = points
        self.perimeter_km = 0.0
        self.area_sqkm = 0.0
        self.calculate_geometry()

    def calculate_geometry(self):
        """Computes polygon perimeter (km) and area (sqkm) using Shoelace formula."""
        n = len(self.points)
        if n < 3:
            self.perimeter_km = 0.0
            self.area_sqkm = 0.0
            return

        # Perimeter
        total_dist_m = 0.0
        for i in range(n):
            p1 = self.points[i]
            p2 = self.points[(i + 1) % n]
            dx = p2.easting - p1.easting
            dy = p2.northing - p1.northing
            total_dist_m += math.hypot(dx, dy)
        self.perimeter_km = round(total_dist_m / 1000.0, 2)

        # Area (Shoelace formula)
        area_m2 = 0.0
        for i in range(n):
            p1 = self.points[i]
            p2 = self.points[(i + 1) % n]
            area_m2 += (p1.easting * p2.northing) - (p2.easting * p1.northing)
        self.area_sqkm = round(abs(area_m2) / 2.0 / 1_000_000.0, 2)


class BoundaryManager:
    """Manages multi-block prospect coordinates."""

    def __init__(self):
        self.blocks: Dict[str, BlockPolygon] = {}
        self.raw_points: List[BoundaryPoint] = []
        self.total_acquisition_area_sqkm = 0.0
        self.total_full_fold_area_sqkm = 0.0

    def parse_coordinate_file(self, file_path: str) -> Tuple[bool, str]:
        """
        Parses a boundary coordinate file (CSV or tab-delimited).
        Expected columns (case-insensitive):
        Block_Name, Point_ID, Easting, Northing, [Latitude], [Longitude], [Notes]
        """
        if not os.path.exists(file_path):
            return False, f"File does not exist: {file_path}"

        self.blocks.clear()
        self.raw_points.clear()

        points_by_block: Dict[str, List[BoundaryPoint]] = {}

        try:
            with open(file_path, 'r', encoding='utf-8-sig', errors='replace') as f:
                # Detect delimiter
                sample = f.read(4096)
                f.seek(0)
                delim = ',' if ',' in sample else ('\t' if '\t' in sample else ';')
                reader = csv.reader(f, delimiter=delim)

                header = next(reader, None)
                if not header:
                    return False, "File is empty."

                # Map column indices
                col_map = {}
                for idx, col in enumerate(header):
                    c = col.strip().lower().replace(' ', '_').replace('-', '_')
                    if c in ('block', 'block_name', 'block_id', 'prospect'):
                        col_map['block'] = idx
                    elif c in ('point', 'point_id', 'pt', 'corner', 'name'):
                        col_map['point'] = idx
                    elif c in ('easting', 'east', 'x', 'utm_x'):
                        col_map['easting'] = idx
                    elif c in ('northing', 'north', 'y', 'utm_y'):
                        col_map['northing'] = idx
                    elif c in ('lat', 'latitude'):
                        col_map['lat'] = idx
                    elif c in ('lon', 'long', 'longitude'):
                        col_map['lon'] = idx
                    elif c in ('notes', 'remark', 'remarks', 'desc'):
                        col_map['notes'] = idx

                # Fallback if no header matching
                if 'easting' not in col_map or 'northing' not in col_map:
                    # Assume: Block, Point, Easting, Northing, Lat, Lon
                    col_map = {'block': 0, 'point': 1, 'easting': 2, 'northing': 3, 'lat': 4, 'lon': 5}

                for row_idx, row in enumerate(reader, start=2):
                    if not row or not any(row):
                        continue
                    try:
                        b_name = row[col_map['block']].strip() if 'block' in col_map and col_map['block'] < len(row) else "Block-1"
                        if not b_name:
                            b_name = "Block-1"
                        pt_id = row[col_map['point']].strip() if 'point' in col_map and col_map['point'] < len(row) else f"P{row_idx:02d}"
                        east = float(row[col_map['easting']].strip().replace(',', ''))
                        north = float(row[col_map['northing']].strip().replace(',', ''))

                        lat = None
                        if 'lat' in col_map and col_map['lat'] < len(row):
                            v = row[col_map['lat']].strip()
                            if v:
                                lat = float(v)

                        lon = None
                        if 'lon' in col_map and col_map['lon'] < len(row):
                            v = row[col_map['lon']].strip()
                            if v:
                                lon = float(v)

                        note = row[col_map['notes']].strip() if 'notes' in col_map and col_map['notes'] < len(row) else ""

                        pt = BoundaryPoint(b_name, pt_id, east, north, lat, lon, note)
                        self.raw_points.append(pt)

                        if b_name not in points_by_block:
                            points_by_block[b_name] = []
                        points_by_block[b_name].append(pt)

                    except Exception as ex:
                        continue

            if not points_by_block:
                return False, "No valid coordinate rows could be parsed."

            # Construct BlockPolygons
            total_area = 0.0
            for b_name, pts in points_by_block.items():
                poly = BlockPolygon(b_name, pts)
                self.blocks[b_name] = poly
                total_area += poly.area_sqkm

            self.total_acquisition_area_sqkm = round(total_area, 2)
            self.total_full_fold_area_sqkm = round(total_area, 2)

            msg = f"Successfully loaded {len(self.raw_points)} points across {len(self.blocks)} blocks. Total Area: {self.total_acquisition_area_sqkm:,.2f} km²."
            return True, msg

        except Exception as e:
            return False, f"Error parsing coordinate file: {str(e)}"

    def get_summary_dict(self) -> Dict:
        """Returns structured geometry summary for report generation."""
        summary = {
            'num_blocks': len(self.blocks),
            'total_acquisition_area_sqkm': self.total_acquisition_area_sqkm,
            'total_full_fold_area_sqkm': self.total_full_fold_area_sqkm,
            'blocks': []
        }
        for b_name, poly in self.blocks.items():
            summary['blocks'].append({
                'name': b_name,
                'point_count': len(poly.points),
                'perimeter_km': poly.perimeter_km,
                'area_sqkm': poly.area_sqkm,
                'points': [
                    {
                        'id': p.point_id,
                        'easting': p.easting,
                        'northing': p.northing,
                        'latitude': p.latitude,
                        'longitude': p.longitude,
                        'notes': p.notes
                    }
                    for p in poly.points
                ]
            })
        return summary

    def generate_sample_csv(self, target_path: str):
        """Generates a sample template CSV showing the required multi-block format."""
        header = ["Block_Name", "Point_ID", "Easting", "Northing", "Latitude", "Longitude", "Notes"]
        sample_rows = [
            ["Block-1", "P01", "712543.20", "2987654.10", "26.987654", "49.123456", "NW Corner"],
            ["Block-1", "P02", "735412.80", "2987654.10", "26.987654", "49.354123", "NE Corner"],
            ["Block-1", "P03", "735412.80", "2954321.00", "26.685412", "49.354123", "SE Corner"],
            ["Block-1", "P04", "712543.20", "2954321.00", "26.685412", "49.123456", "SW Corner"],
            ["Block-2", "P01", "695432.10", "2950123.40", "26.645321", "48.954321", "Corner 1"],
            ["Block-2", "P02", "710234.50", "2950123.40", "26.645321", "49.102345", "Corner 2"],
            ["Block-2", "P03", "710234.50", "2920456.70", "26.375412", "49.102345", "Corner 3"],
            ["Block-2", "P04", "695432.10", "2920456.70", "26.375412", "48.954321", "Corner 4"],
        ]
        os.makedirs(os.path.dirname(os.path.abspath(target_path)), exist_ok=True)
        with open(target_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(header)
            writer.writerows(sample_rows)
