"""
ARGAS Seismic Scouting Suite - Interactive Photo GIS Map & Photo Review Module
Provides dual-pane photo curation interface with live interactive GIS map,
scouting route visualization, waypoint inspection, photo location black dots,
current photo highlighted bullseye target, smooth mouse wheel/button zoom & pan,
photo jump-to-number navigation, and multi-provider map styles (Google Satellite,
ESRI World Imagery, Google Road, OpenStreetMap, Local Terrain GIS, Dark Tactical).

ENHANCED WITH:
1. Native & Header Maximize / Minimize / Restore buttons.
2. Optional Terrain overlay on base maps with an interactive Transparency Slider (0% - 100%).
3. Terrain category filtering dialog (enable/disable specific classes e.g. Sabkha, Dunes, Escarpments).
4. Photo visibility filtering: All Photos vs Within Map Extent vs On Active Terrain Features.
5. High-performance map caching engine: overzooming parent-tile fallback (prevents black tiles),
   project-specific cache folder, cache stats display, custom cache dir selector, and exit cache cleanup prompt.
"""

import os
import sys
import math
import time
import io
import re
import threading
import queue
import tempfile
import hashlib
from typing import List, Dict, Tuple, Optional, Any

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from PIL import Image, ImageTk, ImageDraw

try:
    import shapefile
except ImportError:
    shapefile = None

try:
    import requests
except ImportError:
    requests = None


def get_app_dir() -> str:
    """Returns directory of executable or script."""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


# ==============================================================================
# GEODETIC & TILE PROJECTION UTILITIES
# ==============================================================================

def latlon_to_world_px(lat: float, lon: float, zoom: int) -> Tuple[float, float]:
    """Converts WGS84 Lat/Lon to global Web Mercator pixel coordinates at given zoom."""
    lat_clamped = max(-85.05112878, min(85.05112878, lat))
    lat_rad = math.radians(lat_clamped)
    n = 2.0 ** zoom
    x = (lon + 180.0) / 360.0 * 256.0 * n
    y = (1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * 256.0 * n
    return x, y


def world_px_to_latlon(x: float, y: float, zoom: int) -> Tuple[float, float]:
    """Converts global Web Mercator pixel coordinates to WGS84 Lat/Lon."""
    n = 2.0 ** zoom
    lon = x / (256.0 * n) * 360.0 - 180.0
    lat_rad = math.atan(math.sinh(math.pi * (1.0 - 2.0 * y / (256.0 * n))))
    lat = math.degrees(lat_rad)
    return lat, lon


def utm_to_latlon_wgs84(easting: float, northing: float, zone: int = 39, northern: bool = True) -> Tuple[float, float]:
    """Transforms UTM Coordinates (WGS84 / Ain el Abd approx) to Latitude / Longitude."""
    a = 6378137.0
    f = 1 / 298.257223563
    e = math.sqrt(2 * f - f * f)
    k0 = 0.9996

    x = easting - 500000.0
    y = northing if northern else northing - 10000000.0

    m = y / k0
    mu = m / (a * (1.0 - e * e / 4.0 - 3.0 * e ** 4 / 64.0 - 5.0 * e ** 6 / 256.0))

    e1 = (1.0 - math.sqrt(1.0 - e * e)) / (1.0 + math.sqrt(1.0 - e * e))
    j1 = 3.0 * e1 / 2.0 - 27.0 * e1 ** 3 / 32.0
    j2 = 21.0 * e1 ** 2 / 16.0 - 55.0 * e1 ** 4 / 32.0
    j3 = 151.0 * e1 ** 3 / 96.0
    j4 = 1097.0 * e1 ** 4 / 512.0

    fp = mu + j1 * math.sin(2.0 * mu) + j2 * math.sin(4.0 * mu) + j3 * math.sin(6.0 * mu) + j4 * math.sin(8.0 * mu)

    c1 = (e * e / (1.0 - e * e)) * math.cos(fp) ** 2
    t1 = math.tan(fp) ** 2
    r1 = a * (1.0 - e * e) / ((1.0 - e * e * math.sin(fp) ** 2) ** 1.5)
    n1 = a / math.sqrt(1.0 - e * e * math.sin(fp) ** 2)
    d = x / (n1 * k0)

    phi1 = fp
    lat = phi1 - (n1 * math.tan(phi1) / r1) * (
        d * d / 2.0 -
        (5.0 + 3.0 * t1 + 10.0 * c1 - 4.0 * c1 * c1 - 9.0 * (e * e / (1.0 - e * e))) * d ** 4 / 24.0 +
        (61.0 + 90.0 * t1 + 298.0 * c1 + 45.0 * t1 ** 2 - 252.0 * (e * e / (1.0 - e * e)) - 3.0 * c1 * c1) * d ** 6 / 720.0
    )
    lon0 = math.radians((zone - 1) * 6 - 180 + 3)
    lon = lon0 + (
        d - (1.0 + 2.0 * t1 + c1) * d ** 3 / 6.0 +
        (5.0 - 2.0 * c1 + 28.0 * t1 - 3.0 * c1 ** 2 + 8.0 * (e * e / (1.0 - e * e)) + 24.0 * t1 ** 2) * d ** 5 / 120.0
    ) / math.cos(phi1)
    return math.degrees(lat), math.degrees(lon)


def point_in_polygon(lat: float, lon: float, ring: List[Tuple[float, float]], bbox: Optional[Tuple[float, float, float, float]] = None) -> bool:
    """Ray-casting point in polygon test with bounding box pre-filter."""
    if bbox:
        min_lat, max_lat, min_lon, max_lon = bbox
        if lat < min_lat or lat > max_lat or lon < min_lon or lon > max_lon:
            return False

    n = len(ring)
    if n < 3:
        return False
    inside = False
    p1_lat, p1_lon = ring[0]
    for i in range(1, n + 1):
        p2_lat, p2_lon = ring[i % n]
        if min(p1_lat, p2_lat) < lat <= max(p1_lat, p2_lat):
            if lon <= max(p1_lon, p2_lon):
                if p1_lat != p2_lat:
                    xinters = (lat - p1_lat) * (p2_lon - p1_lon) / (p2_lat - p1_lat) + p1_lon
                if p1_lon == p2_lon or lon <= xinters:
                    inside = not inside
        p1_lat, p1_lon = p2_lat, p2_lon
    return inside


# ==============================================================================
# TILE MANAGER (PROJECT CACHE & HIGH-SPEED DOWNLOAD ENGINE)
# ==============================================================================

TILE_SERVERS = {
    "Google Satellite": "https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}",
    "Google Hybrid": "https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}",
    "Google Terrain": "https://mt1.google.com/vt/lyrs=p&x={x}&y={y}&z={z}",
    "Google Road": "https://mt1.google.com/vt/lyrs=m&x={x}&y={y}&z={z}",
    "ESRI World Imagery": "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    "OpenStreetMap": "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
    "Local Terrain GIS Map": None,
    "Dark Tactical GIS": None
}


class TileCacheManager:
    """
    Manages project-specific disk caching, fallback overzooming, and threaded
    background downloading of online map tiles.
    """
    def __init__(self, project_name: str = "Default", custom_dir: Optional[str] = None):
        self.project_name = project_name
        self.cache_dir = self._resolve_cache_dir(project_name, custom_dir)
        os.makedirs(self.cache_dir, exist_ok=True)
        self.mem_cache: Dict[str, Image.Image] = {}
        self.download_queue = queue.Queue()
        self.failed_keys = set()
        self.num_workers = 6  # Optimized for higher concurrency in slow networks
        self.lock = threading.Lock()
        for _ in range(self.num_workers):
            t = threading.Thread(target=self._worker_loop, daemon=True)
            t.start()

    def _resolve_cache_dir(self, project_name: str, custom_dir: Optional[str] = None) -> str:
        if custom_dir and os.path.isdir(custom_dir):
            return custom_dir
        safe_proj = re.sub(r'[^a-zA-Z0-9_\-]', '_', project_name) or "Default"
        app_d = get_app_dir()
        proj_dir = os.path.join(app_d, "map_cache", safe_proj)
        try:
            os.makedirs(proj_dir, exist_ok=True)
            return proj_dir
        except Exception:
            fallback = os.path.join(tempfile.gettempdir(), "arg_scout_map_cache", safe_proj)
            os.makedirs(fallback, exist_ok=True)
            return fallback

    def set_project(self, project_name: str, custom_dir: Optional[str] = None):
        with self.lock:
            self.project_name = project_name
            self.cache_dir = self._resolve_cache_dir(project_name, custom_dir)
            self.mem_cache.clear()
            self.failed_keys.clear()

    def set_cache_dir(self, new_dir: str):
        with self.lock:
            if new_dir and os.path.isdir(new_dir):
                self.cache_dir = new_dir
                self.mem_cache.clear()
                self.failed_keys.clear()

    def get_cache_stats(self) -> Tuple[float, int, str]:
        """Returns (size_mb, tile_count, cache_dir_path)."""
        total_bytes = 0
        count = 0
        if os.path.exists(self.cache_dir):
            try:
                for entry in os.scandir(self.cache_dir):
                    if entry.is_file() and entry.name.lower().endswith('.png'):
                        total_bytes += entry.stat().st_size
                        count += 1
            except Exception:
                pass
        return round(total_bytes / (1024 * 1024), 2), count, self.cache_dir

    def clear_cache(self) -> int:
        """Deletes all cached tiles for current project. Returns deleted count."""
        deleted = 0
        with self.lock:
            self.mem_cache.clear()
            self.failed_keys.clear()
            if os.path.exists(self.cache_dir):
                for entry in os.scandir(self.cache_dir):
                    if entry.is_file() and entry.name.lower().endswith('.png'):
                        try:
                            os.remove(entry.path)
                            deleted += 1
                        except Exception:
                            pass
        return deleted

    def get_tile(self, provider: str, z: int, x: int, y: int, callback=None) -> Optional[Image.Image]:
        url_template = TILE_SERVERS.get(provider)
        if not url_template:
            return None

        key = f"{provider}_{z}_{x}_{y}"
        if key in self.mem_cache:
            return self.mem_cache[key]

        # Check local disk cache
        safe_provider = "".join(c for c in provider if c.isalnum())
        disk_path = os.path.join(self.cache_dir, f"{safe_provider}_{z}_{x}_{y}.png")
        if os.path.exists(disk_path):
            try:
                im = Image.open(disk_path).convert("RGB")
                self.mem_cache[key] = im
                return im
            except Exception:
                pass

        # Queue for async download if not failed
        if key not in self.failed_keys:
            url = url_template.format(z=z, x=x, y=y)
            self.download_queue.put((key, url, disk_path, callback))

        # FALLBACK OVERZOOMING (Parent Tile Fallback)
        # If the exact tile is still downloading, fetch parent tile at z-1, crop the quadrant and scale up 2x
        # This prevents black tiles on slow network zoom!
        if z > 1:
            pz = z - 1
            px = x // 2
            py = y // 2
            parent_key = f"{provider}_{pz}_{px}_{py}"
            parent_im = self.mem_cache.get(parent_key)
            if not parent_im:
                parent_disk = os.path.join(self.cache_dir, f"{safe_provider}_{pz}_{px}_{py}.png")
                if os.path.exists(parent_disk):
                    try:
                        parent_im = Image.open(parent_disk).convert("RGB")
                        self.mem_cache[parent_key] = parent_im
                    except Exception:
                        parent_im = None
            if parent_im:
                qx = x % 2
                qy = y % 2
                crop_box = (qx * 128, qy * 128, (qx + 1) * 128, (qy + 1) * 128)
                try:
                    fallback_im = parent_im.crop(crop_box).resize((256, 256), Image.BILINEAR)
                    return fallback_im
                except Exception:
                    pass

        return None

    def _worker_loop(self):
        headers = {"User-Agent": "ARGAS-Scouting-Suite/2.0 (Geomatics Inspection)"}
        while True:
            try:
                key, url, disk_path, callback = self.download_queue.get()
                if key in self.failed_keys or key in self.mem_cache:
                    self.download_queue.task_done()
                    continue

                if not requests:
                    self.failed_keys.add(key)
                    self.download_queue.task_done()
                    continue

                resp = requests.get(url, headers=headers, timeout=6)
                if resp.status_code == 200 and len(resp.content) > 500:
                    im = Image.open(io.BytesIO(resp.content)).convert("RGB")
                    self.mem_cache[key] = im
                    try:
                        with open(disk_path, "wb") as f:
                            f.write(resp.content)
                    except Exception:
                        pass
                    if callback:
                        callback()
                else:
                    self.failed_keys.add(key)
                self.download_queue.task_done()
            except Exception:
                self.failed_keys.add(key)
                self.download_queue.task_done()


# Global tile cache instance
tile_manager = TileCacheManager()


# ==============================================================================
# TERRAIN CATEGORY FILTER DIALOG
# ==============================================================================

class TerrainCategoryFilterDialog(tk.Toplevel):
    """Dialog allowing user to enable or disable individual terrain classification categories."""
    def __init__(self, parent, categories: List[str], enabled_dict: Dict[str, bool], on_change_cb):
        super().__init__(parent)
        self.title("Filter Terrain Categories & Geomorphic Features")
        self.geometry("420x460")
        self.minsize(360, 380)
        self.configure(bg="#0F172A")
        self.transient(parent)
        self.grab_set()

        self.categories = categories
        self.enabled_dict = enabled_dict
        self.on_change_cb = on_change_cb
        self.vars: Dict[str, tk.BooleanVar] = {}

        container = ttk.Frame(self, padding=12)
        container.pack(fill="both", expand=True)

        ttk.Label(container, text="Select Visible Terrain Overlay Categories:",
                  font=("Segoe UI", 10, "bold"), foreground="#38BDF8").pack(anchor="w", pady=(0, 6))

        # Quick actions
        btn_box = ttk.Frame(container)
        btn_box.pack(fill="x", pady=(0, 8))
        ttk.Button(btn_box, text="✔ Select All", command=self.select_all).pack(side="left", padx=(0, 6))
        ttk.Button(btn_box, text="✖ Deselect All", command=self.deselect_all).pack(side="left")

        # Scrollable checklist
        scroll_frame = ttk.Frame(container)
        scroll_frame.pack(fill="both", expand=True)

        canvas = tk.Canvas(scroll_frame, bg="#1E293B", highlightthickness=1, highlightbackground="#334155")
        sb = ttk.Scrollbar(scroll_frame, orient="vertical", command=canvas.yview)
        inner = ttk.Frame(canvas)

        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=sb.set)

        canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        for cat in sorted(self.categories):
            v = tk.BooleanVar(value=self.enabled_dict.get(cat, True))
            self.vars[cat] = v
            chk = ttk.Checkbutton(inner, text=cat, variable=v, command=self.apply_changes)
            chk.pack(anchor="w", padx=8, pady=4)

        bot = ttk.Frame(container)
        bot.pack(fill="x", pady=(10, 0))
        ttk.Button(bot, text="Done & Apply", command=self.destroy).pack(side="right")

    def select_all(self):
        for v in self.vars.values():
            v.set(True)
        self.apply_changes()

    def deselect_all(self):
        for v in self.vars.values():
            v.set(False)
        self.apply_changes()

    def apply_changes(self):
        for cat, v in self.vars.items():
            self.enabled_dict[cat] = v.get()
        if self.on_change_cb:
            self.on_change_cb()


# ==============================================================================
# INTERACTIVE SLIPPY GIS MAP CANVAS
# ==============================================================================

class InteractiveScoutMap(ttk.Frame):
    """
    High-performance GIS interactive map canvas for field scouting:
    - Renders routes, waypoints, boundary polygons, and terrain shapefile vectors.
    - Transparent terrain overlay with interactive opacity slider bar (0% - 100%).
    - Category-level terrain filtering.
    - Photo visibility filtering: All vs Within Map View vs On Active Terrain Features.
    - Slippy tile background with overzooming parent-tile fallback for slow networks.
    - Project-specific tile cache monitoring and directory management.
    """
    def __init__(self, parent, on_photo_selected=None, on_visible_photos_changed=None):
        super().__init__(parent)
        self.on_photo_selected = on_photo_selected
        self.on_visible_photos_changed = on_visible_photos_changed

        # Map state
        self.center_lat = 24.50
        self.center_lon = 50.70
        self.zoom = 12
        self.min_zoom = 7
        self.max_zoom = 18

        self.map_mode = tk.StringVar(value="Google Satellite")

        # Layer datasets
        self.photos: List[Dict] = []
        self.current_idx: int = 0
        self.track_points: List[Tuple[float, float]] = []
        self.waypoints: List[Dict] = []
        self.terrain_polygons: List[Dict] = []
        self.available_categories: List[str] = []
        self.enabled_categories: Dict[str, bool] = {}
        self.boundary_polygons: List[List[Tuple[float, float]]] = []

        # Terrain layer overlay controls
        self.show_terrain_var = tk.BooleanVar(value=True)
        self.terrain_alpha_var = tk.DoubleVar(value=55.0)

        # Photo visibility filter mode
        self.photo_filter_mode = tk.StringVar(value="All Photos")
        self.visible_photo_indices: List[int] = []

        # Pan drag state
        self.is_dragging = False
        self.drag_start_x = 0
        self.drag_start_y = 0
        self.drag_start_center_wx = 0.0
        self.drag_start_center_wy = 0.0

        # Canvas tile image reference holder to prevent garbage collection
        self.tile_photo_images = []

        self.build_ui()

    def build_ui(self):
        # 1. Top Control Toolbar - Row 1
        tb1 = ttk.Frame(self, padding=(4, 2))
        tb1.pack(fill="x", pady=(0, 2))

        ttk.Label(tb1, text="Map View:", font=("Segoe UI", 9, "bold"), foreground="#38BDF8").pack(side="left", padx=(0, 4))
        mode_cb = ttk.Combobox(tb1, textvariable=self.map_mode,
                                values=list(TILE_SERVERS.keys()),
                                width=19, state="readonly")
        mode_cb.pack(side="left", padx=(0, 6))
        mode_cb.bind("<<ComboboxSelected>>", lambda e: self.redraw())

        ttk.Button(tb1, text="+ Zoom In", width=9, command=self.zoom_in).pack(side="left", padx=(0, 3))
        ttk.Button(tb1, text="- Zoom Out", width=9, command=self.zoom_out).pack(side="left", padx=(0, 3))
        ttk.Button(tb1, text="[o] Center Photo", command=self.pan_to_current_photo).pack(side="left", padx=(0, 3))
        ttk.Button(tb1, text="Fit All", command=self.fit_extent).pack(side="left", padx=(0, 4))

        # Layer toggles
        self.show_track_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(tb1, text="Route", variable=self.show_track_var, command=self.redraw).pack(side="left", padx=(2, 2))
        self.show_wp_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(tb1, text="Waypoints", variable=self.show_wp_var, command=self.redraw).pack(side="left", padx=(2, 2))
        ttk.Checkbutton(tb1, text="Overlay Terrain", variable=self.show_terrain_var, command=self.redraw).pack(side="left", padx=(2, 2))

        # 2. Top Control Toolbar - Row 2 (Terrain Opacity Slider, Category Filter & Photo Filter)
        tb2 = ttk.Frame(self, padding=(4, 2))
        tb2.pack(fill="x", pady=(0, 4))

        ttk.Label(tb2, text="Terrain Opacity:").pack(side="left", padx=(0, 4))
        self.alpha_scale = ttk.Scale(tb2, from_=0.0, to=100.0, orient="horizontal",
                                     variable=self.terrain_alpha_var, length=110,
                                     command=self._on_alpha_slider_changed)
        self.alpha_scale.pack(side="left", padx=(0, 4))
        self.lbl_alpha_val = ttk.Label(tb2, text=f"{int(self.terrain_alpha_var.get())}%", width=4)
        self.lbl_alpha_val.pack(side="left", padx=(0, 6))

        ttk.Button(tb2, text="🏷 Filter Categories...", command=self.open_category_filter).pack(side="left", padx=(0, 8))

        # Photo Filter selector
        ttk.Label(tb2, text="Photo Filter:", font=("Segoe UI", 9, "bold"), foreground="#38BDF8").pack(side="left", padx=(0, 4))
        photo_filter_cb = ttk.Combobox(tb2, textvariable=self.photo_filter_mode,
                                       values=["All Photos", "Within Visible Map View", "On Active Terrain Features"],
                                       width=24, state="readonly")
        photo_filter_cb.pack(side="left", padx=(0, 6))
        photo_filter_cb.bind("<<ComboboxSelected>>", lambda e: self.redraw())

        self.lbl_photo_count = ttk.Label(tb2, text="Photos: 0/0", font=("Segoe UI", 8, "bold"), foreground="#10B981")
        self.lbl_photo_count.pack(side="left")

        # 3. Main Map Canvas
        self.canvas = tk.Canvas(self, bg="#0A0F1D", highlightthickness=1, highlightbackground="#334155")
        self.canvas.pack(fill="both", expand=True)

        # 4. Bottom Status & Cache Management Bar
        sb = ttk.Frame(self, padding=(4, 2))
        sb.pack(fill="x", pady=(2, 0))

        self.status_lbl = ttk.Label(sb, text="Ready | Click photo black dot to select | Drag to pan | Mouse wheel to zoom",
                                    font=("Segoe UI", 8), foreground="#94A3B8")
        self.status_lbl.pack(side="left", fill="x", expand=True)

        # Cache indicators and controls
        self.cache_lbl = ttk.Label(sb, text="💾 Cache: 0.0 MB (0 tiles)", font=("Segoe UI", 8), foreground="#38BDF8")
        self.cache_lbl.pack(side="right", padx=(6, 2))

        ttk.Button(sb, text="📁 Cache Dir...", command=self.select_cache_directory).pack(side="right", padx=(2, 2))
        ttk.Button(sb, text="🧹 Clear Cache", command=self.clear_cache_prompt).pack(side="right", padx=(2, 2))
        ttk.Button(sb, text="🔄 Refresh Map", command=self.refresh_map_tiles).pack(side="right", padx=(2, 2))

        self.coords_lbl = ttk.Label(sb, text="", font=("Segoe UI", 8, "bold"), foreground="#38BDF8")
        self.coords_lbl.pack(side="right", padx=(8, 8))

        # Canvas event bindings
        self.canvas.bind("<Configure>", lambda e: self.redraw())
        self.canvas.bind("<ButtonPress-1>", self._on_mouse_down)
        self.canvas.bind("<B1-Motion>", self._on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_mouse_up)
        self.canvas.bind("<Motion>", self._on_mouse_move)

        # Mouse wheel zoom bindings for Windows and Linux/X11
        self.canvas.bind("<MouseWheel>", self._on_mouse_wheel)
        self.canvas.bind("<Button-4>", lambda e: self.zoom_in())
        self.canvas.bind("<Button-5>", lambda e: self.zoom_out())

        self.update_cache_status()

    def _on_alpha_slider_changed(self, val):
        self.lbl_alpha_val.configure(text=f"{int(float(val))}%")
        self.redraw()

    def open_category_filter(self):
        """Opens popup dialog to check/uncheck individual geomorphic categories."""
        if not self.available_categories:
            messagebox.showinfo("No Terrain Loaded", "No terrain shapefile with categories is currently loaded.", parent=self)
            return
        TerrainCategoryFilterDialog(self, self.available_categories, self.enabled_categories, on_change_cb=self.redraw)

    def select_cache_directory(self):
        """Allows user to select a custom disk cache directory for the project."""
        curr = tile_manager.cache_dir
        chosen = filedialog.askdirectory(title="Select Map Tile Cache Directory", initialdir=curr, parent=self)
        if chosen:
            tile_manager.set_cache_dir(chosen)
            self.update_cache_status()
            self.redraw()
            messagebox.showinfo("Cache Directory Updated", f"Active map tile cache location set to:\n{chosen}", parent=self)

    def clear_cache_prompt(self):
        """Clears cached map tiles after user confirmation."""
        size_mb, count, path = tile_manager.get_cache_stats()
        msg = f"Are you sure you want to delete {count} cached map tiles ({size_mb} MB) in:\n{path}\n\nTiles will be re-downloaded when viewed."
        ans = messagebox.askyesno("Clear Map Cache", msg, parent=self)
        if ans:
            del_count = tile_manager.clear_cache()
            self.update_cache_status()
            self.redraw()
            messagebox.showinfo("Cache Cleared", f"Deleted {del_count} cached map tiles.", parent=self)

    def refresh_map_tiles(self):
        """Clears memory cache and redownloads visible tiles."""
        tile_manager.mem_cache.clear()
        tile_manager.failed_keys.clear()
        self.redraw()

    def update_cache_status(self):
        """Updates cache size and tile count label."""
        size_mb, count, path = tile_manager.get_cache_stats()
        self.cache_lbl.configure(text=f"💾 Cache: {size_mb} MB ({count} tiles)")

    # --------------------------------------------------------------------------
    # DATA INGESTION
    # --------------------------------------------------------------------------
    def set_data(self, photos: List[Dict], current_idx: int = 0,
                 track_points: Optional[List[Tuple[float, float]]] = None,
                 waypoints: Optional[List[Dict]] = None,
                 terrain_shp: str = "",
                 boundary_polygons: Optional[List[List[Tuple[float, float]]]] = None,
                 project_name: str = "Default"):
        """Populates the GIS layers and associates the project cache."""
        self.photos = photos or []
        self.current_idx = max(0, min(current_idx, len(self.photos) - 1)) if self.photos else 0
        self.track_points = track_points or []
        self.waypoints = waypoints or []
        self.boundary_polygons = boundary_polygons or []

        # Configure project cache
        if project_name:
            tile_manager.set_project(project_name)
            self.update_cache_status()

        # Load terrain polygons if shapefile provided
        if terrain_shp and os.path.exists(terrain_shp) and shapefile:
            self._load_terrain_polygons(terrain_shp)

        # Fit extent initially or center on current photo
        if self.photos and self.photos[self.current_idx].get('has_gps'):
            p = self.photos[self.current_idx]
            self.center_lat = p['lat']
            self.center_lon = p['lon']
            self.zoom = 13
        else:
            self.fit_extent(silent=True)

        self.redraw()

    def set_current_photo_idx(self, idx: int, auto_pan: bool = True):
        """Updates the highlighted photo and automatically pans the map."""
        if not self.photos:
            return
        self.current_idx = max(0, min(idx, len(self.photos) - 1))

        p = self.photos[self.current_idx]
        has_gps = p.get('has_gps', False)

        if has_gps and auto_pan:
            self.center_lat = p['lat']
            self.center_lon = p['lon']

        self.redraw()

        if has_gps:
            self.status_lbl.configure(text=f"Active Photo #{self.current_idx + 1}: {p.get('filename')} (Lat: {p.get('lat'):.5f}°, Lon: {p.get('lon'):.5f}°)")
        else:
            self.status_lbl.configure(text=f"Active Photo #{self.current_idx + 1}: {p.get('filename')} — Non-Geotagged (No EXIF GPS)")

    def _load_terrain_polygons(self, shp_path: str):
        """Loads and converts UTM terrain polygons into WGS84 Lat/Lon for map display."""
        self.terrain_polygons.clear()
        categories_found = set()
        try:
            sf = shapefile.Reader(shp_path)
            field_names = [f[0].lower() for f in sf.fields[1:]]
            desc_idx = field_names.index('descriptor') if 'descriptor' in field_names else 1

            class_colors = {
                'gravel sand': '#D4A373',
                'rolling sand': '#F4A261',
                'sand': '#F4A261',
                'sand dikaka': '#E9C46A',
                'escarpment': '#6C757D',
                'jebel': '#6C757D',
                'gravel and jebels': '#6C757D',
                'subkha': '#E29578',
                'sabkha': '#E29578',
                'subkha and sand': '#DDA15E',
                'farm': '#2A9D8F',
                'village': '#E63946',
                'man made': '#7209B7',
                'gravel': '#BC6C25'
            }

            for s, r in zip(sf.shapes(), sf.records()):
                desc = str(r[desc_idx]).strip() if desc_idx < len(r) else "General"
                desc_lower = desc.lower()
                cat_title = desc.title()
                categories_found.add(cat_title)

                color = '#A8DADC'
                for k, col in class_colors.items():
                    if k in desc_lower:
                        color = col
                        break

                pts = s.points
                if not pts:
                    continue

                parts = list(s.parts) + [len(pts)]
                for p_idx in range(len(parts) - 1):
                    ring_utm = pts[parts[p_idx]:parts[p_idx + 1]]
                    if len(ring_utm) >= 3:
                        ring_ll = []
                        min_lat, max_lat = 999.0, -999.0
                        min_lon, max_lon = 999.0, -999.0
                        for pt in ring_utm:
                            if -180.0 <= pt[0] <= 180.0 and -90.0 <= pt[1] <= 90.0:
                                lat, lon = pt[1], pt[0]
                            else:
                                lat, lon = utm_to_latlon_wgs84(pt[0], pt[1])
                            ring_ll.append((lat, lon))
                            min_lat = min(min_lat, lat)
                            max_lat = max(max_lat, lat)
                            min_lon = min(min_lon, lon)
                            max_lon = max(max_lon, lon)

                        if ring_ll:
                            self.terrain_polygons.append({
                                'ring': ring_ll,
                                'color': color,
                                'desc': desc,
                                'category': cat_title,
                                'bbox': (min_lat, max_lat, min_lon, max_lon)
                            })

            self.available_categories = sorted(list(categories_found))
            self.enabled_categories = {c: True for c in self.available_categories}
        except Exception as e:
            print(f"Warning: Failed to load terrain shapefile for interactive map: {e}")

    # --------------------------------------------------------------------------
    # COORDINATE CONVERSIONS
    # --------------------------------------------------------------------------
    def latlon_to_screen(self, lat: float, lon: float) -> Tuple[float, float]:
        """Maps WGS84 (lat, lon) to canvas (screen_x, screen_y)."""
        w = self.canvas.winfo_width() or 600
        h = self.canvas.winfo_height() or 500
        center_wx, center_wy = latlon_to_world_px(self.center_lat, self.center_lon, self.zoom)
        wx, wy = latlon_to_world_px(lat, lon, self.zoom)
        sx = w / 2.0 + (wx - center_wx)
        sy = h / 2.0 + (wy - center_wy)
        return sx, sy

    def screen_to_latlon(self, sx: float, sy: float) -> Tuple[float, float]:
        """Maps canvas (screen_x, screen_y) to WGS84 (lat, lon)."""
        w = self.canvas.winfo_width() or 600
        h = self.canvas.winfo_height() or 500
        center_wx, center_wy = latlon_to_world_px(self.center_lat, self.center_lon, self.zoom)
        wx = center_wx + (sx - w / 2.0)
        wy = center_wy + (sy - h / 2.0)
        return world_px_to_latlon(wx, wy, self.zoom)

    # --------------------------------------------------------------------------
    # MAP NAVIGATION CONTROLS
    # --------------------------------------------------------------------------
    def zoom_in(self):
        if self.zoom < self.max_zoom:
            self.zoom += 1
            self.redraw()

    def zoom_out(self):
        if self.zoom > self.min_zoom:
            self.zoom -= 1
            self.redraw()

    def pan_to_current_photo(self):
        if not self.photos:
            return
        p = self.photos[self.current_idx]
        if p.get('has_gps'):
            self.center_lat = p['lat']
            self.center_lon = p['lon']
            self.redraw()
        else:
            self.status_lbl.configure(text=f"Photo #{self.current_idx + 1} has no GPS coordinates.")

    def fit_extent(self, silent: bool = False):
        """Calculates bounding box of all photos, tracks, and boundaries and centers map."""
        lats = []
        lons = []

        for p in self.photos:
            if p.get('has_gps'):
                lats.append(p['lat'])
                lons.append(p['lon'])

        for lat, lon in self.track_points:
            lats.append(lat)
            lons.append(lon)

        for poly in self.boundary_polygons:
            for lat, lon in poly:
                lats.append(lat)
                lons.append(lon)

        if not lats:
            if not silent:
                self.status_lbl.configure(text="No spatial coordinates found to fit.")
            return

        min_lat, max_lat = min(lats), max(lats)
        min_lon, max_lon = min(lons), max(lons)

        self.center_lat = (min_lat + max_lat) / 2.0
        self.center_lon = (min_lon + max_lon) / 2.0

        w = self.canvas.winfo_width() or 600
        h = self.canvas.winfo_height() or 500

        for z in range(self.max_zoom, self.min_zoom - 1, -1):
            x1, y1 = latlon_to_world_px(min_lat, min_lon, z)
            x2, y2 = latlon_to_world_px(max_lat, max_lon, z)
            span_x = abs(x2 - x1)
            span_y = abs(y2 - y1)
            if span_x < (w - 60) and span_y < (h - 60):
                self.zoom = z
                break
        else:
            self.zoom = self.min_zoom

        self.redraw()

    # --------------------------------------------------------------------------
    # MOUSE EVENT HANDLERS
    # --------------------------------------------------------------------------
    def _on_mouse_down(self, event):
        self.is_dragging = True
        self.drag_start_x = event.x
        self.drag_start_y = event.y
        self.drag_start_center_wx, self.drag_start_center_wy = latlon_to_world_px(self.center_lat, self.center_lon, self.zoom)

    def _on_mouse_drag(self, event):
        if not self.is_dragging:
            return
        dx = event.x - self.drag_start_x
        dy = event.y - self.drag_start_y
        new_wx = self.drag_start_center_wx - dx
        new_wy = self.drag_start_center_wy - dy
        self.center_lat, self.center_lon = world_px_to_latlon(new_wx, new_wy, self.zoom)
        self.redraw()

    def _on_mouse_up(self, event):
        self.is_dragging = False

    def _on_mouse_move(self, event):
        lat, lon = self.screen_to_latlon(event.x, event.y)
        self.coords_lbl.configure(text=f"Lat: {lat:.5f}° N, Lon: {lon:.5f}° E | Zoom: {self.zoom}")

    def _on_mouse_wheel(self, event):
        """Zooms centered near mouse cursor."""
        if event.delta > 0:
            if self.zoom < self.max_zoom:
                self.zoom += 1
                self.redraw()
        elif event.delta < 0:
            if self.zoom > self.min_zoom:
                self.zoom -= 1
                self.redraw()

    # --------------------------------------------------------------------------
    # CANVAS RENDERING ENGINE
    # --------------------------------------------------------------------------
    def redraw(self):
        self.canvas.delete("all")
        self.tile_photo_images.clear()

        w = self.canvas.winfo_width() or 600
        h = self.canvas.winfo_height() or 500
        if w < 10 or h < 10:
            return

        mode = self.map_mode.get()

        # 1. Background Tiles (Satellite, Hybrid, Terrain, Road, OSM)
        if mode in ("Google Satellite", "Google Hybrid", "Google Terrain", "Google Road", "ESRI World Imagery", "OpenStreetMap"):
            self._render_tiles(w, h, mode)
        elif mode == "Dark Tactical GIS":
            self.canvas.create_rectangle(0, 0, w, h, fill="#0B132B", outline="")
            self._render_tactical_grid(w, h)
        else:
            self.canvas.create_rectangle(0, 0, w, h, fill="#1C2541", outline="")

        # 2. Local Terrain Shapefile Polygons (With Opacity and Category Filtering)
        if self.show_terrain_var.get() and self.terrain_polygons and self.terrain_alpha_var.get() > 0:
            self._render_terrain_polygons()

        # 3. Prospect Boundaries
        if self.boundary_polygons:
            self._render_boundaries()

        # 4. Scouted Route (GPX Tracks)
        if self.show_track_var.get() and self.track_points:
            self._render_tracks()

        # 5. Field Observation Waypoints
        if self.show_wp_var.get() and self.waypoints:
            self._render_waypoints()

        # 6. Photos (Filtered by Visibility/Category criteria)
        self._render_photos(w, h)

        # 7. Current Photo Highlight (Glowing Bullseye Marker)
        self._render_current_photo_target()

        # 8. Scale & North Arrow Overlay
        self._render_map_adornments(w, h)

        self.update_cache_status()

    def _render_tiles(self, w: int, h: int, provider: str):
        """Fetches and displays Web Mercator slippy tiles covering the canvas view."""
        c_wx, c_wy = latlon_to_world_px(self.center_lat, self.center_lon, self.zoom)
        top_left_wx = c_wx - w / 2.0
        top_left_wy = c_wy - h / 2.0

        start_tx = int(top_left_wx // 256)
        end_tx = int((top_left_wx + w) // 256) + 1
        start_ty = int(top_left_wy // 256)
        end_ty = int((top_left_wy + h) // 256) + 1

        n_tiles = 2 ** self.zoom
        for tx in range(start_tx, end_tx):
            wrap_tx = tx % n_tiles
            for ty in range(start_ty, end_ty):
                if 0 <= ty < n_tiles:
                    tile_im = tile_manager.get_tile(provider, self.zoom, wrap_tx, ty, callback=self._on_tile_downloaded)
                    pos_x = tx * 256 - top_left_wx
                    pos_y = ty * 256 - top_left_wy
                    if tile_im:
                        tk_im = ImageTk.PhotoImage(tile_im)
                        self.tile_photo_images.append(tk_im)
                        self.canvas.create_image(pos_x, pos_y, image=tk_im, anchor="nw")
                    else:
                        self.canvas.create_rectangle(pos_x, pos_y, pos_x + 256, pos_y + 256,
                                                    fill="#111827", outline="#1F2937")

    def _on_tile_downloaded(self):
        """Thread-safe callback when a tile finishes downloading."""
        self.after(60, self.redraw)

    def _render_tactical_grid(self, w: int, h: int):
        grid_step = 60
        for gx in range(0, w, grid_step):
            self.canvas.create_line(gx, 0, gx, h, fill="#1E293B", width=1)
        for gy in range(0, h, grid_step):
            self.canvas.create_line(0, gy, w, gy, fill="#1E293B", width=1)

    def _render_terrain_polygons(self):
        """Renders geomorphic surface terrain classification polygons with opacity."""
        alpha = self.terrain_alpha_var.get()
        if alpha <= 0:
            return

        # Select stippling pattern based on transparency slider
        if alpha <= 15:
            stipple_pattern = "gray12"
        elif alpha <= 35:
            stipple_pattern = "gray25"
        elif alpha <= 65:
            stipple_pattern = "gray50"
        elif alpha <= 85:
            stipple_pattern = "gray75"
        else:
            stipple_pattern = ""  # 100% solid

        for poly in self.terrain_polygons:
            cat = poly.get('category', poly.get('desc', 'General'))
            if not self.enabled_categories.get(cat, True):
                continue

            pts = poly.get('ring', [])
            if len(pts) < 3:
                continue
            coords = []
            for lat, lon in pts:
                sx, sy = self.latlon_to_screen(lat, lon)
                coords.extend([sx, sy])

            c = poly.get('color', '#A8DADC')
            self.canvas.create_polygon(coords, fill=c, outline="#1E293B", width=1, stipple=stipple_pattern)

    def _render_boundaries(self):
        """Renders prospect acquisition boundaries."""
        for poly in self.boundary_polygons:
            if len(poly) < 3:
                continue
            coords = []
            for lat, lon in poly:
                sx, sy = self.latlon_to_screen(lat, lon)
                coords.extend([sx, sy])
            self.canvas.create_polygon(coords, fill="", outline="#FFFFFF", width=2.5)

    def _render_tracks(self):
        """Renders the scouted route polyline."""
        if len(self.track_points) < 2:
            return
        coords = []
        for lat, lon in self.track_points:
            sx, sy = self.latlon_to_screen(lat, lon)
            coords.extend([sx, sy])
        self.canvas.create_line(coords, fill="#0F172A", width=4.5)
        self.canvas.create_line(coords, fill="#00E5FF", width=2.5)

    def _render_waypoints(self):
        """Renders waypoint symbols with diamond markers and labels."""
        for wp in self.waypoints:
            lat = wp.get('lat')
            lon = wp.get('lon')
            if lat is None or lon is None:
                continue
            sx, sy = self.latlon_to_screen(lat, lon)
            d = 5.0
            self.canvas.create_polygon([sx, sy - d, sx + d, sy, sx, sy + d, sx - d, sy],
                                       fill="#F59E0B", outline="#000000", width=1.5)
            name = str(wp.get('name', ''))
            if name:
                self.canvas.create_text(sx + 7, sy - 7, text=name, anchor="w",
                                        font=("Segoe UI", 7, "bold"), fill="#F59E0B")

    def _is_photo_visible_under_filter(self, p: Dict, sx: float, sy: float, w: int, h: int) -> bool:
        """Evaluates whether photo matches the active filter criteria."""
        mode = self.photo_filter_mode.get()
        if mode == "All Photos":
            return True

        if mode == "Within Visible Map View":
            return (0 <= sx <= w and 0 <= sy <= h)

        if mode == "On Active Terrain Features":
            lat = p.get('lat')
            lon = p.get('lon')
            if lat is None or lon is None:
                return False
            for poly in self.terrain_polygons:
                cat = poly.get('category', poly.get('desc', 'General'))
                if not self.enabled_categories.get(cat, True):
                    continue
                if point_in_polygon(lat, lon, poly['ring'], poly.get('bbox')):
                    return True
            return False

        return True

    def _render_photos(self, w: int, h: int):
        """Renders photo markers taking into account active visibility filter."""
        visible_indices = []

        for idx, p in enumerate(self.photos):
            if not p.get('has_gps'):
                continue
            lat = p.get('lat')
            lon = p.get('lon')
            if lat is None or lon is None:
                continue

            sx, sy = self.latlon_to_screen(lat, lon)

            # Check filter
            if not self._is_photo_visible_under_filter(p, sx, sy, w, h):
                continue

            visible_indices.append(idx)
            r = 4.5

            # 1. White outer halo for high contrast on all terrains/satellite
            self.canvas.create_oval(sx - r - 1.5, sy - r - 1.5, sx + r + 1.5, sy + r + 1.5,
                                    fill="#FFFFFF", outline="")

            # 2. Solid Black Dot Symbol (clickable)
            dot = self.canvas.create_oval(sx - r, sy - r, sx + r, sy + r,
                                          fill="#000000", outline="#334155", width=1,
                                          tags=("photo_dot", f"photo_{idx}"))

            self.canvas.tag_bind(dot, "<Button-1>", lambda e, p_idx=idx: self._handle_photo_dot_click(p_idx))

        self.visible_photo_indices = visible_indices
        self.lbl_photo_count.configure(text=f"Photos: {len(visible_indices)}/{len(self.photos)}")

        # Notify parent dialog of visible photos
        if self.on_visible_photos_changed:
            self.on_visible_photos_changed(visible_indices)

    def _handle_photo_dot_click(self, photo_idx: int):
        """Handles user clicking directly on a photo black dot on the map."""
        if self.on_photo_selected:
            self.on_photo_selected(photo_idx)
        else:
            self.set_current_photo_idx(photo_idx, auto_pan=False)

    def _render_current_photo_target(self):
        """Renders glowing bullseye target and callout on active photo."""
        if not self.photos or not (0 <= self.current_idx < len(self.photos)):
            return

        p = self.photos[self.current_idx]
        if not p.get('has_gps'):
            return

        lat = p.get('lat')
        lon = p.get('lon')
        if lat is None or lon is None:
            return

        sx, sy = self.latlon_to_screen(lat, lon)

        # 1. Pulsing Outer Target Rings (Vibrant Red & Cyan Bullseye)
        self.canvas.create_oval(sx - 16, sy - 16, sx + 16, sy + 16, outline="#FF0055", width=2.5)
        self.canvas.create_oval(sx - 11, sy - 11, sx + 11, sy + 11, outline="#00FFFF", width=1.8)

        # 2. Crosshair indicators
        self.canvas.create_line(sx - 20, sy, sx - 16, sy, fill="#FF0055", width=2)
        self.canvas.create_line(sx + 16, sy, sx + 20, sy, fill="#FF0055", width=2)
        self.canvas.create_line(sx, sy - 20, sx, sy - 16, fill="#FF0055", width=2)
        self.canvas.create_line(sx, sy + 16, sx, sy + 20, fill="#FF0055", width=2)

        # 3. Center Target Dot
        self.canvas.create_oval(sx - 4.5, sy - 4.5, sx + 4.5, sy + 4.5, fill="#FF0055", outline="#FFFFFF", width=1.5)

        # 4. Floating Badge Label
        fname = p.get('filename', f"Photo #{self.current_idx + 1}")
        lbl_text = f"● #{self.current_idx + 1}: {fname}"
        self.canvas.create_rectangle(sx + 14, sy - 22, sx + 14 + len(lbl_text) * 6.5, sy - 4,
                                    fill="#0F172A", outline="#38BDF8", width=1.2)
        self.canvas.create_text(sx + 18, sy - 13, text=lbl_text, anchor="w",
                                font=("Segoe UI", 8, "bold"), fill="#38BDF8")

    def _render_map_adornments(self, w: int, h: int):
        """Draws North Arrow and Metric Scale Bar."""
        # 1. North Arrow (Top-Right)
        nx, ny = w - 40, 45
        self.canvas.create_line(nx, ny + 16, nx, ny - 16, arrow="last", arrowshape=(8, 10, 3.5),
                                fill="#000000", width=3)
        self.canvas.create_line(nx, ny + 16, nx, ny - 16, arrow="last", arrowshape=(8, 10, 3.5),
                                fill="#38BDF8", width=1.8)
        self.canvas.create_text(nx, ny - 24, text="N", font=("Segoe UI", 9, "bold"), fill="#38BDF8")

        # 2. Metric Scale Bar (Bottom-Left)
        m_per_px = 156543.03392 * math.cos(math.radians(self.center_lat)) / (2 ** self.zoom)
        target_bar_px = 100
        ground_m = target_bar_px * m_per_px

        if ground_m >= 5000:
            scale_km = round(ground_m / 5000) * 5
            scale_txt = f"{scale_km} km"
            bar_px = (scale_km * 1000) / m_per_px
        elif ground_m >= 1000:
            scale_km = round(ground_m / 1000)
            scale_txt = f"{scale_km} km"
            bar_px = (scale_km * 1000) / m_per_px
        else:
            scale_m = max(50, round(ground_m / 100) * 100)
            scale_txt = f"{scale_m} m"
            bar_px = scale_m / m_per_px

        bx, by = 25, h - 25
        self.canvas.create_line(bx, by, bx + bar_px, by, fill="#0F172A", width=4)
        self.canvas.create_line(bx, by, bx + bar_px, by, fill="#38BDF8", width=2.5)
        self.canvas.create_line(bx, by - 4, bx, by + 4, fill="#38BDF8", width=2)
        self.canvas.create_line(bx + bar_px, by - 4, bx + bar_px, by + 4, fill="#38BDF8", width=2)
        self.canvas.create_text(bx + bar_px / 2.0, by - 8, text=scale_txt, font=("Segoe UI", 8, "bold"), fill="#FFFFFF")


# ==============================================================================
# DUAL-PANE PHOTO REVIEW & GIS MAP MODAL DIALOG
# ==============================================================================

class PhotoReviewDialog(tk.Toplevel):
    """
    Advanced Dual-Pane Photo Review Dialog:
    - Left Pane: Large photo preview, metadata, field note editor, caption editor, jump-to-photo.
    - Right Pane: Live Interactive GIS Map showing routes, waypoints, photo black dots, and highlighted target.
    - Full keyboard navigation: Up/Down/Left/Right arrows, mouse wheel scrolling, Enter to jump.
    - Window management: Native Windows Minimize/Maximize buttons + Top ribbon control buttons.
    """
    def __init__(self, parent, photo_list: List[Dict], ai_assistant=None,
                 track_file: str = "", waypoints: Optional[List[Dict]] = None,
                 terrain_shp: str = "", boundary_mgr=None, initial_idx: int = 0,
                 project_name: str = "Default"):
        super().__init__(parent)
        self.title("Field Scouting Photos & Interactive GIS Map Inspector — Powered by Nasrullah Khan")
        self.geometry("1400x840")
        self.minsize(1080, 640)
        self.configure(bg="#0A0F1D")
        
        # NOTE: Omitting self.transient(parent) ensures Windows renders native Minimize and Maximize buttons!
        self.grab_set()

        self.photos = photo_list
        self.ai = ai_assistant
        self.current_idx = initial_idx if (photo_list and 0 <= initial_idx < len(photo_list)) else 0
        self.track_file = track_file
        self.waypoints = waypoints or []
        self.terrain_shp = terrain_shp
        self.boundary_mgr = boundary_mgr
        self.project_name = project_name

        self.is_maximized = False
        self.visible_indices: List[int] = list(range(len(self.photos)))

        # Parse track points from GPX/KML if available
        self.track_points = []
        if self.track_file and os.path.exists(self.track_file):
            self._parse_track_points()

        # Extract boundary polygons if available
        self.boundary_polygons = []
        if self.boundary_mgr and hasattr(self.boundary_mgr, 'blocks'):
            for b in self.boundary_mgr.blocks:
                pts = [(p.latitude, p.longitude) for p in b.points if p.latitude is not None and p.longitude is not None]
                if len(pts) >= 3:
                    self.boundary_polygons.append(pts)

        self.build_ui()
        self.show_current_photo()

        # Set up keyboard shortcuts
        self.bind("<Up>", lambda e: self.prev_photo())
        self.bind("<Down>", lambda e: self.next_photo())
        self.bind("<Left>", lambda e: self.prev_photo())
        self.bind("<Right>", lambda e: self.next_photo())
        self.bind("<F11>", lambda e: self.toggle_maximize())

        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def toggle_maximize(self):
        """Toggles window between maximized and normal restored state."""
        try:
            if self.is_maximized:
                self.state('normal')
                self.is_maximized = False
                if hasattr(self, 'btn_maximize'):
                    self.btn_maximize.configure(text="🗖 Maximize")
            else:
                self.state('zoomed')
                self.is_maximized = True
                if hasattr(self, 'btn_maximize'):
                    self.btn_maximize.configure(text="🗗 Restore")
        except Exception:
            pass

    def _parse_track_points(self):
        """Extracts (lat, lon) coordinates from track file for route overlay."""
        ext = os.path.splitext(self.track_file)[1].lower()
        if ext == '.gpx':
            try:
                import xml.etree.ElementTree as ET
                tree = ET.parse(self.track_file)
                root = tree.getroot()
                ns = root.tag.split('}')[0] + '}' if root.tag.startswith('{') else ''
                for trkpt in root.iter(f"{ns}trkpt"):
                    lat = float(trkpt.attrib.get('lat', 0.0))
                    lon = float(trkpt.attrib.get('lon', 0.0))
                    self.track_points.append((lat, lon))
            except Exception:
                pass

    def build_ui(self):
        container = ttk.Frame(self, padding=8)
        container.pack(fill="both", expand=True)

        # Header Title Bar & Window Management Buttons
        top_hdr = ttk.Frame(container)
        top_hdr.pack(fill="x", pady=(0, 6))

        ttk.Label(top_hdr, text="Field Scouting Photo Review, Digital Notes & Real-Time GIS Map",
                  font=("Segoe UI", 12, "bold"), foreground="#38BDF8").pack(side="left")

        # Top-right controls: Minimize, Maximize/Restore, Close
        win_ctrls = ttk.Frame(top_hdr)
        win_ctrls.pack(side="right")

        ttk.Label(win_ctrls, text="⚡ Powered by Nasrullah Khan", font=("Segoe UI", 9, "bold italic"),
                  foreground="#38BDF8").pack(side="left", padx=(0, 12))

        ttk.Button(win_ctrls, text="🗕 Minimize", width=9, command=self.iconify).pack(side="left", padx=(0, 3))
        self.btn_maximize = ttk.Button(win_ctrls, text="🗖 Maximize", width=10, command=self.toggle_maximize)
        self.btn_maximize.pack(side="left", padx=(0, 3))
        ttk.Button(win_ctrls, text="✕ Close", width=7, command=self.on_close).pack(side="left")

        # Split PanedWindow: Left Pane = Photo Preview & Notes; Right Pane = Interactive GIS Map
        split = ttk.PanedWindow(container, orient="horizontal")
        split.pack(fill="both", expand=True, pady=(0, 6))

        # ======================================================================
        # LEFT PANE: PHOTO PREVIEW, JUMP, NOTES & CAPTION
        # ======================================================================
        left_pane = ttk.Frame(split, padding=4)
        split.add(left_pane, weight=5)

        # 1. Navigation & Jump Bar
        ctrl_bar = ttk.Frame(left_pane)
        ctrl_bar.pack(fill="x", pady=(0, 4))

        self.idx_lbl = ttk.Label(ctrl_bar, text="Photo 0 of 0", font=("Segoe UI", 10, "bold"), foreground="#F8FAFC")
        self.idx_lbl.pack(side="left")

        jump_frame = ttk.Frame(ctrl_bar)
        jump_frame.pack(side="right")
        ttk.Label(jump_frame, text="Jump to #:").pack(side="left", padx=(0, 4))
        self.jump_var = tk.StringVar(value="1")
        self.jump_ent = ttk.Entry(jump_frame, textvariable=self.jump_var, width=5)
        self.jump_ent.pack(side="left", padx=(0, 4))
        self.jump_ent.bind("<Return>", lambda e: self.jump_to_photo())
        ttk.Button(jump_frame, text="Go", width=4, command=self.jump_to_photo).pack(side="left")

        # 2. Main Photo Display Frame
        preview_frame = ttk.Frame(left_pane, style="Card.TFrame", padding=2)
        preview_frame.pack(fill="both", expand=True, pady=(0, 6))

        self.preview_lbl = ttk.Label(preview_frame, text="Loading photo...", anchor="center", background="#000000")
        self.preview_lbl.pack(fill="both", expand=True)
        self.preview_lbl.bind("<MouseWheel>", self._on_preview_mouse_wheel)

        # 3. Photo Metadata Bar
        self.meta_lbl = ttk.Label(left_pane, text="EXIF Metadata", font=("Segoe UI", 8), foreground="#94A3B8")
        self.meta_lbl.pack(fill="x", pady=(0, 4))

        # 4. Field Note Editor Box
        note_box = ttk.LabelFrame(left_pane, text=" Field Scouting Observation / Digital Note ", padding=6)
        note_box.pack(fill="x", pady=(0, 4))
        self.note_var = tk.StringVar()
        self.note_ent = ttk.Entry(note_box, textvariable=self.note_var, font=("Segoe UI", 9))
        self.note_ent.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self.note_ent.bind("<FocusOut>", lambda e: self.save_current_caption())
        ttk.Button(note_box, text="⚡ Refine with AI", command=self.ai_analyze_note_and_refine).pack(side="right")

        # 5. Formatted Report Caption Box
        caption_box = ttk.LabelFrame(left_pane, text=" Word Report Photo Plate Caption (14-Word Max) ", padding=6)
        caption_box.pack(fill="x", pady=(0, 6))
        self.caption_var = tk.StringVar()
        self.caption_ent = ttk.Entry(caption_box, textvariable=self.caption_var, font=("Segoe UI", 9, "bold"))
        self.caption_ent.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self.caption_ent.bind("<FocusOut>", lambda e: self.save_current_caption())
        ttk.Button(caption_box, text="✨ AI Caption", command=self.ai_regenerate_caption).pack(side="right")

        # 6. Bottom Navigation Bar
        nav_bar = ttk.Frame(left_pane)
        nav_bar.pack(fill="x", pady=(4, 0))

        ttk.Button(nav_bar, text="◀ Previous Photo", command=self.prev_photo).pack(side="left", padx=(0, 4))
        ttk.Button(nav_bar, text="Next Photo ▶", command=self.next_photo).pack(side="left", padx=(0, 6))

        self.reject_btn = ttk.Button(nav_bar, text="Exclude from Report", command=self.toggle_reject)
        self.reject_btn.pack(side="left", padx=(0, 4))
        ttk.Button(nav_bar, text="Finish & Close", style="Accent.TButton", command=self.on_close).pack(side="right")

        # ======================================================================
        # RIGHT PANE: LIVE INTERACTIVE GIS MAP
        # ======================================================================
        right_pane = ttk.Frame(split, padding=4)
        split.add(right_pane, weight=5)

        self.map_widget = InteractiveScoutMap(
            right_pane,
            on_photo_selected=self.on_map_photo_selected,
            on_visible_photos_changed=self.on_visible_photos_changed
        )
        self.map_widget.pack(fill="both", expand=True)

        # Ingest layers into map widget
        self.map_widget.set_data(
            photos=self.photos,
            current_idx=self.current_idx,
            track_points=self.track_points,
            waypoints=self.waypoints,
            terrain_shp=self.terrain_shp,
            boundary_polygons=self.boundary_polygons,
            project_name=self.project_name
        )

    # --------------------------------------------------------------------------
    # PHOTO DISPLAY & INTERACTION
    # --------------------------------------------------------------------------
    def on_visible_photos_changed(self, visible_indices: List[int]):
        """Callback when the active photo visibility filter updates on the map."""
        self.visible_indices = visible_indices
        if self.photos and 0 <= self.current_idx < len(self.photos):
            total = len(self.photos)
            vis_count = len(visible_indices)
            filter_note = f" (Filter: {vis_count} in view)" if vis_count < total else ""
            p_info = self.photos[self.current_idx]
            fname = p_info.get('filename', f"Photo #{self.current_idx + 1}")
            is_rej = p_info.get('is_rejected', False)
            status_txt = " [STATUS: EXCLUDED]" if is_rej else " [STATUS: INCLUDED]"
            self.idx_lbl.configure(text=f"Photo {self.current_idx + 1} of {total}{filter_note} — {fname}{status_txt}")

    def show_current_photo(self):
        if not self.photos or not (0 <= self.current_idx < len(self.photos)):
            return

        p_info = self.photos[self.current_idx]
        total = len(self.photos)
        fpath = p_info.get('file_path', '')
        fname = p_info.get('filename', os.path.basename(fpath))

        has_gps = p_info.get('has_gps', False)
        gps_txt = f"✔ Geotagged ({p_info.get('lat', 0):.5f}° N, {p_info.get('lon', 0):.5f}° E)" if has_gps else "✖ Non-Geotagged (No EXIF GPS)"
        is_rej = p_info.get('is_rejected', False)
        status_txt = " [STATUS: EXCLUDED]" if is_rej else " [STATUS: INCLUDED]"

        vis_count = len(self.visible_indices)
        filter_note = f" (Filter: {vis_count} in view)" if vis_count < total else ""
        self.idx_lbl.configure(text=f"Photo {self.current_idx + 1} of {total}{filter_note} — {fname}{status_txt}")
        self.jump_var.set(str(self.current_idx + 1))
        self.caption_var.set(p_info.get('caption', ''))
        self.note_var.set(p_info.get('note', ''))
        self.meta_lbl.configure(text=f"Terrain: {p_info.get('category', 'General')}  |  {gps_txt}  |  File: {fpath}")

        if hasattr(self, 'reject_btn'):
            if is_rej:
                self.reject_btn.configure(text="✔ Restore to Report")
            else:
                self.reject_btn.configure(text="✖ Exclude from Report")

        if os.path.exists(fpath):
            try:
                with Image.open(fpath) as im:
                    im.thumbnail((580, 380))
                    photo = ImageTk.PhotoImage(im)
                    self.preview_lbl.configure(image=photo, text="")
                    self.preview_lbl.image = photo
            except Exception:
                self.preview_lbl.configure(text=f"Cannot render image: {fname}")
        else:
            self.preview_lbl.configure(text="Image file not found on disk.")

        # Update GIS map and auto-pan to photo position
        if hasattr(self, 'map_widget'):
            self.map_widget.set_current_photo_idx(self.current_idx, auto_pan=True)

    def jump_to_photo(self):
        """Jumps directly to entered 1-based photo number."""
        try:
            val = int(self.jump_var.get().strip())
            if 1 <= val <= len(self.photos):
                self.save_current_caption()
                self.current_idx = val - 1
                self.show_current_photo()
            else:
                messagebox.showwarning("Invalid Number", f"Please enter a number between 1 and {len(self.photos)}.", parent=self)
        except Exception:
            pass

    def on_map_photo_selected(self, photo_idx: int):
        """Callback when user clicks directly on a photo dot on the GIS map."""
        if 0 <= photo_idx < len(self.photos):
            self.save_current_caption()
            self.current_idx = photo_idx
            self.show_current_photo()

    def _on_preview_mouse_wheel(self, event):
        """Scroll through photos using mouse wheel over preview."""
        if event.delta > 0:
            self.prev_photo()
        elif event.delta < 0:
            self.next_photo()

    def toggle_reject(self):
        if self.photos and 0 <= self.current_idx < len(self.photos):
            cur = self.photos[self.current_idx].get('is_rejected', False)
            self.photos[self.current_idx]['is_rejected'] = not cur
            self.show_current_photo()

    def save_current_caption(self):
        if self.photos and 0 <= self.current_idx < len(self.photos):
            self.photos[self.current_idx]['caption'] = self.caption_var.get().strip()
            self.photos[self.current_idx]['note'] = self.note_var.get().strip()

    def prev_photo(self):
        self.save_current_caption()
        # If filter is active, navigate to previous visible photo
        if self.visible_indices and len(self.visible_indices) < len(self.photos):
            curr_pos = [i for i, idx in enumerate(self.visible_indices) if idx == self.current_idx]
            if curr_pos and curr_pos[0] > 0:
                self.current_idx = self.visible_indices[curr_pos[0] - 1]
                self.show_current_photo()
            elif not curr_pos and self.visible_indices:
                self.current_idx = self.visible_indices[0]
                self.show_current_photo()
        else:
            if self.current_idx > 0:
                self.current_idx -= 1
                self.show_current_photo()

    def next_photo(self):
        self.save_current_caption()
        # If filter is active, navigate to next visible photo
        if self.visible_indices and len(self.visible_indices) < len(self.photos):
            curr_pos = [i for i, idx in enumerate(self.visible_indices) if idx == self.current_idx]
            if curr_pos and curr_pos[0] < len(self.visible_indices) - 1:
                self.current_idx = self.visible_indices[curr_pos[0] + 1]
                self.show_current_photo()
            elif not curr_pos and self.visible_indices:
                self.current_idx = self.visible_indices[0]
                self.show_current_photo()
        else:
            if self.current_idx < len(self.photos) - 1:
                self.current_idx += 1
                self.show_current_photo()

    def ai_regenerate_caption(self):
        """Regenerates AI photo caption using multimodal Gemini or offline geomatics engine."""
        if not self.photos or not (0 <= self.current_idx < len(self.photos)):
            return
        p_info = self.photos[self.current_idx]
        fpath = p_info.get('file_path', '')
        if not os.path.exists(fpath):
            messagebox.showwarning("File Missing", "Photo file does not exist on disk.", parent=self)
            return

        note = self.note_var.get().strip()
        nearby_wp = None
        if self.waypoints and p_info.get('has_gps'):
            plat, plon = p_info['lat'], p_info['lon']
            best_dist = 999999.0
            for wp in self.waypoints:
                wlat, wlon = wp.get('lat', 0.0), wp.get('lon', 0.0)
                d = math.hypot((plat - wlat) * 111000, (plon - wlon) * 111000 * math.cos(math.radians(plat)))
                if d < best_dist:
                    best_dist = d
                    nearby_wp = wp
            if nearby_wp:
                nearby_wp['distance_m'] = best_dist

        if self.ai:
            cap, conf = self.ai.generate_photo_caption(fpath, nearby_waypoint=nearby_wp, photo_note=note)
            self.caption_var.set(cap)
            self.save_current_caption()

    def ai_analyze_note_and_refine(self):
        """Enhances digital notes and refines the official caption."""
        note = self.note_var.get().strip()
        if not note:
            messagebox.showinfo("Empty Note", "Please type or paste field observation notes first.", parent=self)
            return
        self.ai_regenerate_caption()

    def on_close(self):
        """Handles dialog close, saves edits, and prompts about offline map cache."""
        self.save_current_caption()
        self.destroy()
