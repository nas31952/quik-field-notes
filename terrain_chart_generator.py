"""
Terrain GIS Analyzer & Pie Chart Generator for ARGAS Scouting Suite (Section 6)
Computes geomorphic surface terrain class areas and percentages, generates high-DPI
pie charts for reports, and generates publication-grade spatial GIS terrain maps
strictly matching the official ARGAS report template styling.
Strictly separated from Saudi Aramco contractual operational areas (Section 7).
"""

import os
import math
from typing import Dict, List, Tuple, Optional
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as MplPolygon, Rectangle, FancyBboxPatch
from matplotlib.collections import PatchCollection

try:
    import shapefile
except ImportError:
    shapefile = None


# Pure Geomorphic Surface Terrain Descriptors & Template-Matched Colors (Section 6)
# Colors calibrated directly from official ARGAS Scouting Report template maps
GEOMORPHIC_TERRAIN_DESCRIPTORS = {
    'gravel sand': (
        'Gravel Sand Plains',
        'Firm gravel-sand surface, high vibrator transit speed, optimal vibroseis coupling, excellent 4x4 vehicle trafficability.',
        '#D97706'  # Warm golden amber
    ),
    'sand': (
        'Rolling Sand Sheets',
        'Undulating sand sheets and low sand accumulations; moderate vehicle access; reduced tire pressure required.',
        '#FEF9C3'  # Soft pale cream
    ),
    'gravel and jebels': (
        'Escarpments & Jebels',
        'Rugged rocky ridges, jebels and steep escarpments; requires pre-scouted detour bypasses, climbing line crews, or heli-access.',
        '#C0392B'  # Rich terracotta rust
    ),
    'subkha': (
        'Subkha / Sabkha Flats',
        'Low-lying salt flats with shallow water table and fragile crust; severe sinkage risk; mandatory probing and designated bypass tracks.',
        '#38BDF8'  # Vibrant sky blue
    ),
    'sand dikaka': (
        'Sand and Dikaka',
        'Vegetated sand hummocks with scrub roots; undulating rough ride; line clearing and reduced transit speeds required.',
        '#A3E635'  # Fresh light sage green
    ),
    'subkha and sand': (
        'Subkha & Sand Transitional',
        'Transitional soft sand overlying saturated sabkha crust; variable load-bearing capacity; bypass tracks mandatory for vibrators.',
        '#F4D03F'  # Warm buff yellow
    ),
    'gravel and sand dunes': (
        'Sand and Dunes',
        'Complex dune ridges with exposed gravel bases; steep slip faces; requires scouted dune crossings and low-pressure sand tires.',
        '#FB923C'  # Peach / warm orange
    ),
    'man made object': (
        'Oil & Gas Field Corridor',
        'Active oil/gas pipelines, overhead high-voltage power lines, and graded highways; strict 50m GDAD standoff offset buffers.',
        '#EC4899'  # Vibrant magenta / hot pink
    ),
    'farm': (
        'Agriculture Farms',
        'Enclosed date palm groves, fenced cultivation, and irrigation networks; landowner permits and source skip-point rules apply.',
        '#22C55E'  # Bright emerald green
    ),
    'farms': (
        'Agriculture Farms',
        'Enclosed date palm groves, fenced cultivation, and irrigation networks; landowner permits and source skip-point rules apply.',
        '#22C55E'
    ),
    'village': (
        'Rural Settlements & Urban',
        'Populated villages, residential compounds, and schools; mandatory 100m GDAD standoff buffer and community relations liaison.',
        '#EF4444'  # Bright red
    ),
    'gravel': (
        'Gravel Plains & Regs',
        'Hard-packed desert pavement (reg); fast vehicle mobility, excellent vibrator baseplate seating, optimal production rates.',
        '#64748B'  # Slate gray-blue
    ),
    'dunes': (
        'Active Sand Dunes',
        'Active mobile barchan and transverse sand dunes; requires specialized sand tires, GPS navigation, and safety flag poles.',
        '#F59E0B'
    ),
    'quarry': (
        'Quarries & Excavations',
        'Active aggregate borrow pits and excavation cuts; perimeter safety berms and detour lines required.',
        '#475569'
    )
}

DISTINCT_COLORS = [
    '#D97706', '#FEF9C3', '#C0392B', '#38BDF8', '#A3E635',
    '#F4D03F', '#FB923C', '#EC4899', '#22C55E', '#EF4444',
    '#64748B', '#F59E0B', '#3B82F6', '#8B5CF6', '#14B8A6'
]


class TerrainChartGenerator:
    """Calculates geomorphic terrain category statistics and generates publication-grade maps and pie charts."""

    @staticmethod
    def get_shapefile_fields(shp_path: str) -> List[str]:
        """Returns the list of field names in the shapefile DBF."""
        if not shapefile or not os.path.exists(shp_path):
            return []
        try:
            sf = shapefile.Reader(shp_path)
            return [f[0] for f in sf.fields[1:]]
        except Exception:
            return []

    @staticmethod
    def _compute_ring_area_km2(points: List[Tuple[float, float]]) -> float:
        """Calculates area of a single ring in square kilometers using Shoelace formula."""
        n = len(points)
        if n < 3:
            return 0.0

        p0 = points[0]
        is_utm = abs(p0[0]) > 1000.0 or abs(p0[1]) > 1000.0

        if is_utm:
            area_m2 = 0.0
            for i in range(n):
                p1 = points[i]
                p2 = points[(i + 1) % n]
                area_m2 += (p1[0] * p2[1]) - (p2[0] * p1[1])
            return abs(area_m2) / 2.0 / 1_000_000.0
        else:
            mean_lat = sum(p[1] for p in points) / n
            lat_m = 111132.92
            lon_m = 111412.84 * math.cos(math.radians(mean_lat))
            area_m2 = 0.0
            for i in range(n):
                p1 = (points[i][0] * lon_m, points[i][1] * lat_m)
                p2 = (points[(i + 1) % n][0] * lon_m, points[(i + 1) % n][1] * lat_m)
                area_m2 += (p1[0] * p2[1]) - (p2[0] * p1[1])
            return abs(area_m2) / 2.0 / 1_000_000.0

    @staticmethod
    def _compute_shape_area_km2(shape) -> float:
        """Calculates total area of a multi-part shape."""
        pts = shape.points
        parts = list(shape.parts) + [len(pts)]
        tot_area = 0.0
        for p_idx in range(len(parts) - 1):
            ring = pts[parts[p_idx]:parts[p_idx + 1]]
            tot_area += TerrainChartGenerator._compute_ring_area_km2(ring)
        return tot_area

    @staticmethod
    def analyze_shapefile(shp_path: str, user_class_field: Optional[str] = None) -> Dict:
        """
        Reads terrain polygon shapefile and calculates:
        - Geomorphic class areas (km²) using polygon geometry Shoelace formula or DBF attribute
        - Class percentages (%)
        - Total area (km²)
        - Surface characteristics and trafficability notes
        """
        if not shapefile:
            return {'error': "pyshp (shapefile) library is not installed."}

        if not os.path.exists(shp_path):
            return {'error': f"Shapefile not found: {shp_path}"}

        try:
            sf = shapefile.Reader(shp_path)
            field_names = [f[0] for f in sf.fields[1:]]
            field_names_lower = [f.lower() for f in field_names]

            # 1. Identify descriptor / classification field
            class_field_idx = None
            if user_class_field and user_class_field in field_names:
                class_field_idx = field_names.index(user_class_field)
            else:
                priority_candidates = ['descriptor', 'description', 'desc', 'class_name', 'class', 'terrain', 'category', 'type', 'name', 'cover', 'comments']
                for cand in priority_candidates:
                    for idx, fn in enumerate(field_names_lower):
                        if cand == fn or cand in fn:
                            class_field_idx = idx
                            break
                    if class_field_idx is not None:
                        break

            # 2. Check if a pre-computed area field exists in DBF
            area_field_idx = None
            for cand in ['area_km2', 'areakm2', 'area_sqkm', 'shape_area', 'area']:
                for idx, fn in enumerate(field_names_lower):
                    if cand == fn or cand in fn:
                        area_field_idx = idx
                        break
                if area_field_idx is not None:
                    break

            records = sf.records()
            shapes = sf.shapes()

            class_areas: Dict[str, float] = {}

            for shape, r in zip(shapes, records):
                cname = "General Terrain"
                if class_field_idx is not None and class_field_idx < len(r):
                    val = str(r[class_field_idx]).strip()
                    if val and val.lower() != 'none':
                        cname = val

                area_km2 = 0.0
                if area_field_idx is not None:
                    try:
                        v = float(r[area_field_idx])
                        if v > 100_000:
                            v /= 1_000_000.0
                        area_km2 = v
                    except Exception:
                        area_km2 = TerrainChartGenerator._compute_shape_area_km2(shape)
                else:
                    area_km2 = TerrainChartGenerator._compute_shape_area_km2(shape)

                if area_km2 > 0:
                    class_areas[cname] = class_areas.get(cname, 0.0) + area_km2

            if not class_areas:
                return {'error': "No valid polygon geometry or terrain classes found in shapefile."}

            total_area = sum(class_areas.values())
            if total_area <= 0:
                total_area = 1.0

            # Sort descending by area
            sorted_classes = sorted(class_areas.items(), key=lambda x: x[1], reverse=True)

            results = []
            for idx, (cname, area) in enumerate(sorted_classes):
                pct = (area / total_area) * 100.0
                norm_key = cname.lower().strip()
                meta = GEOMORPHIC_TERRAIN_DESCRIPTORS.get(
                    norm_key,
                    (cname, "Natural desert surface with variable trafficability and rolling topography.", DISTINCT_COLORS[idx % len(DISTINCT_COLORS)])
                )
                results.append({
                    'class_name': meta[0],
                    'raw_name': cname,
                    'area_sqkm': round(area, 2),
                    'percentage': round(pct, 1),
                    'trafficability': meta[1],
                    'color': meta[2]
                })

            return {
                'success': True,
                'detected_field': field_names[class_field_idx] if class_field_idx is not None else "Geometry",
                'all_fields': field_names,
                'total_area_sqkm': round(total_area, 2),
                'terrain_classes': results
            }

        except Exception as e:
            return {'error': f"Failed to analyze shapefile: {str(e)}"}

    @staticmethod
    def generate_pie_chart(terrain_data: List[Dict], output_path: str, prospect_name: str = "Prospect Area") -> str:
        """Generates a 300 DPI high-resolution standalone pie chart saved as PNG."""
        labels = []
        sizes = []
        colors = []

        for idx, item in enumerate(terrain_data):
            labels.append(f"{item['class_name']}\n({item['percentage']}%)")
            sizes.append(item['area_sqkm'])
            colors.append(item.get('color', DISTINCT_COLORS[idx % len(DISTINCT_COLORS)]))

        plt.figure(figsize=(9.5, 6.2), dpi=300)
        plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')

        wedges, texts, autotexts = plt.pie(
            sizes,
            labels=labels,
            colors=colors,
            autopct='%1.1f%%',
            pctdistance=0.78,
            startangle=140,
            textprops={'fontsize': 8.5, 'weight': 'bold'},
            wedgeprops={'edgecolor': 'white', 'linewidth': 1.5, 'antialiased': True}
        )

        for autotext in autotexts:
            autotext.set_color('#1E293B')
            autotext.set_fontsize(7.5)

        plt.title(f"Figure 5.1: Geomorphic Terrain Classification Breakdown — {prospect_name}", fontsize=12, weight='bold', pad=15)
        plt.tight_layout()

        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()

        return output_path

    @staticmethod
    def generate_section6_narrative(terrain_data: List[Dict], total_area: float) -> str:
        """Synthesizes rich technical geomorphic narrative text for Section 6."""
        lines = [
            f"The survey area encompasses a total calculated geomorphic surface of {total_area:,.2f} km². "
            f"Detailed spatial analysis of satellite multispectral imagery, ground-truth scouting tracks, "
            f"and shapefile geomorphic boundaries identified {len(terrain_data)} distinct terrain classes requiring tailored operational methodologies:"
        ]
        for t in terrain_data:
            lines.append(
                f"• {t['class_name']} ({t['area_sqkm']:,.2f} km² / {t['percentage']:.1f}%): "
                f"{t['trafficability']}"
            )
        lines.append(
            "\nVibrator operations, receiver line deployment, and detours must strictly comply with the specific "
            "hazard mitigations detailed in Section 11 and Section 12."
        )
        return "\n".join(lines)

    @staticmethod
    def generate_terrain_map(shp_path: str, output_path: str, prospect_name: str = "Prospect Area",
                             user_field: Optional[str] = None, crew_name: str = "Crew S-86",
                             author: str = "Nasrullah Khan", date_str: str = "October 2026") -> str:
        """
        Generates a 300 DPI publication-grade spatial GIS map matching the official ARGAS report template.
        Crucially:
        1. Polygons are sorted in descending order by area so large background polygons draw first,
           and smaller polygons (farms, villages, pipelines, dunes) draw on top with ZERO occlusion.
        2. All unique categories are rendered with vibrant, template-matched colors and thin dark outlines.
        3. Dedicated layout panel for the Legend (cream box with black border) and Inset Pie Chart
           (white box with black border) ensures NO map features are hidden or covered.
        4. Official ARGAS Header with logo and Crew designation, North Arrow, Metric Scale Bar,
           and standard Cartographic Sheet Footer with 'Powered by Nasrullah Khan'.
        """
        if not shapefile or not os.path.exists(shp_path):
            raise FileNotFoundError(f"Shapefile not found or pyshp missing: {shp_path}")

        analysis = TerrainChartGenerator.analyze_shapefile(shp_path, user_class_field=user_field)
        if 'error' in analysis:
            raise ValueError(analysis['error'])

        class_colors = {}
        for item in analysis['terrain_classes']:
            class_colors[item['raw_name'].lower().strip()] = item.get('color', '#94A3B8')
            class_colors[item['class_name'].lower().strip()] = item.get('color', '#94A3B8')

        sf = shapefile.Reader(shp_path)
        records = sf.records()
        shapes = sf.shapes()
        field_names = [f[0].lower() for f in sf.fields[1:]]

        # Identify class field
        class_idx = 1
        detected = analysis.get('detected_field', '').lower()
        if user_field and user_field.lower() in field_names:
            class_idx = field_names.index(user_field.lower())
        elif detected and detected in field_names:
            class_idx = field_names.index(detected)
        else:
            for cand in ['descriptor', 'description', 'desc', 'class_name', 'class', 'terrain', 'category', 'type']:
                if cand in field_names:
                    class_idx = field_names.index(cand)
                    break

        polygon_features = []
        all_x, all_y = [], []

        for s, r in zip(shapes, records):
            raw_val = str(r[class_idx]).strip() if class_idx < len(r) else "General Terrain"
            color = class_colors.get(raw_val.lower(), '#94A3B8')
            pts = s.points
            if not pts:
                continue

            for p in pts:
                all_x.append(p[0])
                all_y.append(p[1])

            parts = list(s.parts) + [len(pts)]
            shape_area = TerrainChartGenerator._compute_shape_area_km2(s)

            rings = []
            for p_idx in range(len(parts) - 1):
                ring = pts[parts[p_idx]:parts[p_idx + 1]]
                if len(ring) >= 3:
                    rings.append(ring)

            if rings:
                polygon_features.append({
                    'area': shape_area,
                    'color': color,
                    'raw_val': raw_val,
                    'rings': rings
                })

        # CRUCIAL: Sort descending by area so largest polygons draw at the back,
        # and all small polygons (farms, villages, pipelines, dunes) draw on top!
        polygon_features.sort(key=lambda x: x['area'], reverse=True)

        min_x, max_x = min(all_x), max(all_x)
        min_y, max_y = min(all_y), max(all_y)
        dx = max_x - min_x
        dy = max_y - min_y

        total_area = analysis['total_area_sqkm']
        terrain_classes = analysis['terrain_classes']

        # Setup 12.0 x 14.5 inch Figure at 300 DPI
        fig = plt.figure(figsize=(12, 14.5), dpi=300, facecolor='#FFFFFF')

        # Double Neatlines
        fig.patches.append(Rectangle((0.015, 0.015), 0.97, 0.97, facecolor='none', edgecolor='#CBD5E1', lw=1.2, transform=fig.transFigure, zorder=100))
        fig.patches.append(Rectangle((0.025, 0.025), 0.95, 0.95, facecolor='none', edgecolor='#0F172A', lw=1.8, transform=fig.transFigure, zorder=101))

        # Top Header Area
        # Red ARGAS Logo
        fig.patches.append(FancyBboxPatch((0.038, 0.938), 0.13, 0.028, boxstyle="round,pad=0.003,rounding_size=0.005",
                                         facecolor='#E60000', edgecolor='#CC0000', lw=1, transform=fig.transFigure, zorder=105))
        fig.text(0.103, 0.952, "ARGAS", fontsize=14, fontweight='black', color='#FFFFFF', ha='center', va='center', zorder=106)

        # Crew indicator on right
        fig.text(0.960, 0.952, f"{crew_name}", fontsize=14, fontweight='bold', color='#E60000', ha='right', va='center', zorder=106)

        # Center Title Banner Box
        fig.patches.append(FancyBboxPatch((0.21, 0.936), 0.58, 0.032, boxstyle="round,pad=0.004,rounding_size=0.008",
                                         facecolor='#FFFFCC', edgecolor='#000000', lw=1.2, transform=fig.transFigure, zorder=105))
        fig.text(0.50, 0.952, f"S86 Crew {prospect_name.upper()} - Initial Terrain Classification Map",
                 fontsize=11.5, fontweight='bold', color='#0F172A', ha='center', va='center', zorder=106)

        # Main Map Axis (Left side: 64% width, completely unobstructed)
        ax_map = fig.add_axes([0.035, 0.065, 0.64, 0.855], zorder=1)

        patches = []
        colors = []
        for feat in polygon_features:
            c = feat['color']
            for ring in feat['rings']:
                patches.append(MplPolygon(ring, closed=True))
                colors.append(c)

        pcoll = PatchCollection(patches, facecolors=colors, edgecolors='#1E293B', linewidths=0.45, alpha=0.96, zorder=2)
        ax_map.add_collection(pcoll)

        margin_x = dx * 0.025
        margin_y = dy * 0.025
        ax_map.set_xlim(min_x - margin_x, max_x + margin_x)
        ax_map.set_ylim(min_y - margin_y, max_y + margin_y)
        ax_map.set_aspect('equal')
        ax_map.set_xticks([])
        ax_map.set_yticks([])
        for spine in ax_map.spines.values():
            spine.set_color('#0F172A')
            spine.set_linewidth(1.5)

        # North Arrow in Map Axis (Top-Right)
        ax_map.annotate('N', xy=(min_x + dx * 0.93, max_y + dy * 0.01), xytext=(min_x + dx * 0.93, max_y - dy * 0.06),
                        arrowprops=dict(facecolor='#000000', edgecolor='#000000', width=2.5, headwidth=9),
                        ha='center', va='bottom', fontsize=11, fontweight='bold', color='#000000', zorder=10)

        # Metric Scale Bar inside Map Axis (Bottom Center)
        sb_cx = min_x + dx * 0.50
        sb_cy = min_y + dy * 0.03
        scale_km = 20 if dx > 30000 else (10 if dx > 15000 else 5)
        scale_m = scale_km * 1000
        seg4 = scale_m / 4.0
        sb_h = dy * 0.012

        ax_map.add_patch(Rectangle((sb_cx - scale_m / 2, sb_cy), seg4, sb_h, facecolor='#000000', edgecolor='#000000', zorder=10))
        ax_map.add_patch(Rectangle((sb_cx - scale_m / 2 + seg4, sb_cy), seg4, sb_h, facecolor='#FFFFFF', edgecolor='#000000', zorder=10))
        ax_map.add_patch(Rectangle((sb_cx - scale_m / 2 + seg4 * 2, sb_cy), seg4, sb_h, facecolor='#000000', edgecolor='#000000', zorder=10))
        ax_map.add_patch(Rectangle((sb_cx - scale_m / 2 + seg4 * 3, sb_cy), seg4, sb_h, facecolor='#FFFFFF', edgecolor='#000000', zorder=10))

        ax_map.text(sb_cx - scale_m / 2, sb_cy + sb_h * 1.6, "0", fontsize=7.5, fontweight='bold', ha='center', zorder=11)
        ax_map.text(sb_cx - scale_m / 2 + seg4, sb_cy + sb_h * 1.6, f"{scale_km // 4}", fontsize=7.5, fontweight='bold', ha='center', zorder=11)
        ax_map.text(sb_cx - scale_m / 2 + seg4 * 2, sb_cy + sb_h * 1.6, f"{scale_km // 2}", fontsize=7.5, fontweight='bold', ha='center', zorder=11)
        ax_map.text(sb_cx + scale_m / 2, sb_cy + sb_h * 1.6, f"{scale_km} Km", fontsize=7.5, fontweight='bold', ha='center', zorder=11)

        # Right Side Panel: Legend Box (Upper) + Inset Pie Chart Box (Lower)
        # 1. Legend Box: [0.695, 0.495, 0.27, 0.425]
        ax_leg = fig.add_axes([0.695, 0.495, 0.27, 0.425], facecolor='#FFFFE6', zorder=10)
        for spine in ax_leg.spines.values():
            spine.set_color('#000000')
            spine.set_linewidth(1.2)
        ax_leg.set_xticks([])
        ax_leg.set_yticks([])

        ax_leg.text(0.50, 0.93, "Legend", fontsize=11.5, fontweight='bold', ha='center', va='center', color='#000000')
        ax_leg.plot([0.06, 0.94], [0.87, 0.87], color='#CBD5E1', lw=0.8)

        # Boundary entry
        ax_leg.plot([0.06, 0.18], [0.82, 0.82], color='#000000', lw=2.5)
        ax_leg.plot([0.06, 0.06], [0.80, 0.84], color='#000000', lw=2.5)
        ax_leg.plot([0.18, 0.18], [0.80, 0.84], color='#000000', lw=2.5)
        ax_leg.text(0.22, 0.82, f"{prospect_name.title()}", fontsize=9, fontweight='bold', va='center', color='#000000')

        leg_y = 0.74
        item_step = 0.72 / max(len(terrain_classes), 1)

        for item in terrain_classes:
            c = item.get('color', '#94A3B8')
            cname = item['class_name']
            rect = Rectangle((0.06, leg_y - 0.016), 0.11, 0.032, facecolor=c, edgecolor='#000000', lw=0.8)
            ax_leg.add_patch(rect)
            ax_leg.text(0.21, leg_y, f"{cname}", fontsize=8.0, fontweight='bold', va='center', color='#000000')
            leg_y -= item_step

        # 2. Inset Pie Chart Box: [0.695, 0.065, 0.27, 0.415]
        ax_pie_box = fig.add_axes([0.695, 0.065, 0.27, 0.415], facecolor='#FFFFFF', zorder=10)
        for spine in ax_pie_box.spines.values():
            spine.set_color('#000000')
            spine.set_linewidth(1.2)
        ax_pie_box.set_xticks([])
        ax_pie_box.set_yticks([])

        ax_pie_box.text(0.50, 0.94, "Terrain Breakdown (%)", fontsize=10.5, fontweight='bold', ha='center', va='center', color='#0F172A')

        pie_sizes = [d['area_sqkm'] for d in terrain_classes]
        pie_colors = [d['color'] for d in terrain_classes]

        ax_pie = fig.add_axes([0.705, 0.08, 0.25, 0.35], zorder=15)
        wedges, texts, autotexts = ax_pie.pie(
            pie_sizes,
            autopct=lambda p: f'{p:.1f}%' if p >= 3.5 else '',
            colors=pie_colors,
            startangle=130,
            pctdistance=0.75,
            textprops={'fontsize': 7.0, 'weight': 'bold', 'color': '#0F172A'},
            wedgeprops={'edgecolor': '#000000', 'linewidth': 0.8, 'antialiased': True}
        )

        ax_pie_box.text(0.50, 0.04, f"Total Surface Area: {total_area:,.2f} km²", fontsize=8.5, fontweight='bold', ha='center', color='#0F172A')

        # Bottom Cartographic Footer Bar
        fig.text(0.038, 0.038, f"Document Name: Terrain_Class Map_{prospect_name.replace(' ', '_')}", fontsize=8.5, color='#475569', va='center', zorder=100)

        fig.patches.append(FancyBboxPatch((0.42, 0.029), 0.18, 0.018, boxstyle="round,pad=0.002,rounding_size=0.004",
                                         facecolor='#FFA500', edgecolor='#CC8400', lw=0.8, transform=fig.transFigure, zorder=105))
        fig.text(0.51, 0.038, "ARGAS Classification: Internal Use", fontsize=7.5, fontweight='bold', color='#000000', ha='center', va='center', zorder=106)

        fig.text(0.960, 0.045, "S86 GIS Unit - Survey Department", fontsize=7.5, fontweight='bold', color='#64748B', ha='right', va='center', zorder=100)
        fig.text(0.960, 0.032, f"Date: {date_str}   CGS : WGS 84   Author : {author}", fontsize=7.0, color='#64748B', ha='right', va='center', zorder=100)
        fig.text(0.960, 0.018, "ARGAS S-86 Preliminary Scouting Suite | Powered by Nasrullah Khan", fontsize=6.8, color='#94A3B8', ha='right', style='italic', zorder=100)

        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        plt.savefig(output_path, dpi=300, facecolor='#FFFFFF', bbox_inches='tight')
        plt.close()

        return output_path
