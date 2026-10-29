"""
ARGAS Seismic Scouting Suite & Report Generator
Saudi Aramco Preliminary Scouting Report Utility (Crew S-86)

Comprehensive desktop application for:
1. Project Setup, Distribution & Sign-off Document Control
2. Scouting Team, Equipment, Travel Dates (GPX Scan), Objectives & Comms
3. Multi-Block Prospect Boundary Coordinates (Table 5) & Geometry Calculation
4. Field Tracks & Digital Notes Integration (CSV / GPX / QField)
5. Dynamic Map Figures Selection Matrix (Core Optional 1, 2, 3, 4, 5, 6, 8, 9 + Custom Maps)
6. GIS Terrain Classification, 300 DPI Pie Chart Generator & Area Types (Table 6)
7. Photo Curation, Vision AI Object Description & Interactive Thumbnail Review
8. Automated Word Report Generation (Template AST Preservation) & Calibrated PDF (~10 MB)
"""

import os
import sys
import shutil
import csv
import threading
import queue
import time
import math
import copy
import io
import re
import zipfile
import subprocess
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import List, Dict, Tuple, Optional, Any

from PIL import Image, ExifTags, ImageOps, ImageEnhance, ImageFilter, ImageTk
import numpy as np

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# Optional GIS / Docx / PDF libraries
try:
    import shapefile
except ImportError:
    shapefile = None

try:
    import docx
except ImportError:
    docx = None

try:
    import pypdf
except ImportError:
    pypdf = None

# Custom Submodules
from boundary_manager import BoundaryManager, BoundaryPoint, BlockPolygon
from maps_manager import MapsManager, MapFigureConfig, REPORT_SECTION_CHOICES
from gpx_track_analyzer import GpxTrackAnalyzer
from terrain_chart_generator import TerrainChartGenerator
from aramco_remoteness_analyzer import AramcoRemotenessAnalyzer, ARAMCO_CONTRACTUAL_TYPES
from report_profiles import ProfileManager, DEFAULT_PRELIMINARY_PROFILE
from ai_scout_assistant import AIScoutAssistant, discover_api_key, save_api_key
from report_docx_generator import ReportDocxGenerator
from report_template_modes import (
    ReportTemplateProcessingMode,
    ReportSectionItem,
    MODE_METADATA,
    get_default_scouting_sections
)
from report_analyzer_engine import ReportAnalyzerEngine
from section_prompts_dialog import SectionPromptsDialog
from help_guide import HelpDialog
from photo_map_viewer import PhotoReviewDialog, InteractiveScoutMap
from scouting_journal_manager import ScoutingJournalManager, JournalEntry
from scouting_package_manager import ScoutingPackageManager


# ==============================================================================
# PHOTO CURATION & IMAGE PROCESSING ALGORITHMS
# ==============================================================================

TARGET_CATEGORIES = [
    ('Sand Dunes', ['sand dune', 'crescent dune', 'dunes']),
    ('Subkha', ['subkha', 'sabkha']),
    ('Escarps', ['escarp', 'escarpment', 'break of elevation']),
    ('Dikaka', ['dikaka', 'dikakha']),
    ('Quarry Dumps', ['quarry dump', 'quarry dumped', 'rubbish dump']),
    ('Crusher/Quarry', ['crusher', 'quarry']),
    ('Scattered Plants', ['scattered plants', 'shrubs', 'sparse vegetation']),
    ('Dry Mud Area', ['dry mud', 'mud area']),
    ('Subkha & Sand', ['subkha & sand', 'sabkha & sand']),
    ('Gravel & Sand Plains', ['gravel & sand', 'gravel plain']),
    ('Gravel & Cobbles', ['gravel & cobbles', 'cobbles']),
    ('Rocky Plateau', ['rocky plateau', 'plateau', 'jebel', 'jebels']),
    ('Pipeline Corridor', ['pipeline', 'pipe', 'shbab', 'oilfield']),
    ('Highway/Roads', ['highway', 'road', 'asphalt', 'track']),
    ('Farms & Trees', ['farm', 'farms', 'palm', 'fence']),
    ('Camp/Settlements', ['camp', 'village', 'residential', 'settlement'])
]

TERRAIN_KEYWORDS = TARGET_CATEGORIES


def haversine_dist_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Computes Haversine great-circle distance between two GPS coordinates in meters."""
    R = 6371000.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = math.sin(delta_phi / 2.0)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0)**2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c


def extract_photo_note(exif_data: dict, img_path: str) -> str:
    """Extracts text notes/descriptions from EXIF fields or adjacent sidecar text files."""
    notes = []
    # 1. EXIF ImageDescription
    desc = exif_data.get('ImageDescription')
    if desc and isinstance(desc, str) and desc.strip():
        notes.append(desc.strip())

    # 2. EXIF UserComment
    comm = exif_data.get('UserComment')
    if comm:
        if isinstance(comm, bytes):
            for pfx in [b'ASCII\x00\x00\x00', b'UNICODE\x00\x00\x00', b'\x00\x00\x00']:
                if comm.startswith(pfx):
                    comm = comm[len(pfx):]
            try:
                txt = comm.decode('utf-8', errors='ignore').strip()
                if txt and len(txt) > 2:
                    notes.append(txt)
            except Exception:
                pass
        elif isinstance(comm, str) and comm.strip():
            notes.append(comm.strip())

    # 3. Windows Property XP Tags
    for xp in ['XPComment', 'XPTitle', 'XPSubject']:
        val = exif_data.get(xp)
        if val:
            if isinstance(val, bytes):
                try:
                    txt = val.decode('utf-16le', errors='ignore').replace('\x00', '').strip()
                    if txt:
                        notes.append(txt)
                except Exception:
                    pass
            elif isinstance(val, str) and val.strip():
                notes.append(val.strip())

    # 4. Check sidecar .txt file (e.g. IMG_1234.txt)
    base_no_ext = os.path.splitext(img_path)[0]
    sidecar_txt = base_no_ext + ".txt"
    if os.path.exists(sidecar_txt):
        try:
            with open(sidecar_txt, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read().strip()
                if content and len(content) > 2:
                    notes.append(content)
        except Exception:
            pass

    unique_notes = []
    for n in notes:
        clean = n.replace('\r', ' ').replace('\n', ' ').strip()
        if clean and clean not in unique_notes:
            unique_notes.append(clean)
    return " | ".join(unique_notes)


def extract_exif(img_path):
    try:
        with Image.open(img_path) as img:
            exif = img._getexif()
            if not exif:
                # Check for sidecar text file even if no EXIF present
                base_no_ext = os.path.splitext(img_path)[0]
                sidecar_txt = base_no_ext + ".txt"
                note = ""
                if os.path.exists(sidecar_txt):
                    try:
                        with open(sidecar_txt, 'r', encoding='utf-8', errors='ignore') as f:
                            note = f.read().strip()
                    except Exception:
                        pass
                return None, None, None, None, note

            exif_data = {}
            for tag_id, value in exif.items():
                tag = ExifTags.TAGS.get(tag_id, tag_id)
                exif_data[tag] = value

            dt_str = exif_data.get('DateTimeOriginal') or exif_data.get('DateTime')
            dt = None
            if dt_str:
                try:
                    dt = datetime.strptime(dt_str, '%Y:%m:%d %H:%M:%S')
                except Exception:
                    pass

            gps_info = exif_data.get('GPSInfo')
            lat, lon, direction = None, None, None
            if gps_info:
                lat, lon, direction = parse_gps_info(gps_info)

            note = extract_photo_note(exif_data, img_path)

            return dt, lat, lon, direction, note
    except Exception:
        return None, None, None, None, ""


def parse_gps_info(gps):
    def to_deg(val, ref):
        if not val:
            return None
        try:
            d = float(val[0])
            m = float(val[1])
            s = float(val[2])
            res = d + (m / 60.0) + (s / 3600.0)
            if ref in ['S', 'W']:
                res = -res
            return res
        except Exception:
            return None

    lat = to_deg(gps.get(2) or gps.get('GPSLatitude'), gps.get(1) or gps.get('GPSLatitudeRef'))
    lon = to_deg(gps.get(4) or gps.get('GPSLongitude'), gps.get(3) or gps.get('GPSLongitudeRef'))
    direction = gps.get(17) or gps.get('GPSImgDirection')
    if direction is not None:
        try:
            direction = float(direction)
        except Exception:
            direction = None
    return lat, lon, direction

def compute_sharpness(img_gray):
    arr = np.array(img_gray, dtype=np.float32)
    if arr.ndim == 3:
        arr = arr.mean(axis=2)
    lap = -4 * arr[1:-1, 1:-1] + arr[:-2, 1:-1] + arr[2:, 1:-1] + arr[1:-1, :-2] + arr[1:-1, 2:]
    return float(lap.var())

def enhance_image(img_path, out_path, apply_haze=True, apply_sharp=True, apply_color=True):
    with Image.open(img_path) as im:
        exif = im.info.get('exif')
        im = ImageOps.exif_transpose(im)
        if im.mode != 'RGB':
            im = im.convert('RGB')

        if apply_haze:
            arr = np.array(im, dtype=np.float32)
            p2 = np.percentile(arr, 1.5, axis=(0, 1))
            p98 = np.percentile(arr, 98.5, axis=(0, 1))
            diff = np.maximum(p98 - p2, 1.0)
            arr = np.clip((arr - p2) * (255.0 / diff), 0, 255).astype(np.uint8)
            im = Image.fromarray(arr)

        if apply_sharp:
            im = im.filter(ImageFilter.UnsharpMask(radius=1.5, percent=130, threshold=3))

        if apply_color:
            enh = ImageEnhance.Color(im)
            im = enh.enhance(1.18)
            cnt = ImageEnhance.Contrast(im)
            im = cnt.enhance(1.08)

        os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
        if exif:
            im.save(out_path, quality=92, exif=exif, optimize=True)
        else:
            im.save(out_path, quality=92, optimize=True)


def style_combobox_popdown(cb):
    """Enforces high-contrast styling on the Combobox popdown listbox across all platforms."""
    def _apply(event=None):
        try:
            popdown = cb.tk.eval(f'ttk::combobox::PopdownWindow {cb}')
            cb.tk.call(popdown + '.f.l', 'configure',
                       '-background', '#1E293B',
                       '-foreground', '#FFFFFF',
                       '-selectbackground', '#0284C7',
                       '-selectforeground', '#FFFFFF')
        except Exception:
            pass
    cb.bind('<Button-1>', _apply, add='+')
    cb.bind('<FocusIn>', _apply, add='+')
    cb.bind('<Map>', _apply, add='+')
    _apply()


# ==============================================================================
# INTERACTIVE MODAL DIALOGS (TEAM, EQUIPMENT, CUSTOM MAPS & IMAGE VIEWER)
# ==============================================================================

class TeamMemberDialog(tk.Toplevel):
    """Interactive modal to add or edit a scouting team member."""
    def __init__(self, parent, member_data: Optional[Any] = None):
        super().__init__(parent)
        self.title("Edit Team Member" if member_data else "Add Team Member")
        self.geometry("540x380")
        self.minsize(480, 300)
        self.configure(bg="#0A0F1D")
        self.transient(parent)

        name_val = ""
        pos_val = ""
        resp_val = ""
        if isinstance(member_data, dict):
            name_val = member_data.get('name', '')
            pos_val = member_data.get('position', '')
            resp_val = member_data.get('responsibility', '')
        elif isinstance(member_data, (list, tuple)):
            name_val = str(member_data[0]) if len(member_data) > 0 else ""
            pos_val = str(member_data[1]) if len(member_data) > 1 else ""
            resp_val = str(member_data[2]) if len(member_data) > 2 else ""

        self.result = None
        self.name_var = tk.StringVar(value=name_val)
        self.pos_var = tk.StringVar(value=pos_val)
        self.resp_var = tk.StringVar(value=resp_val)

        pad = ttk.Frame(self, padding=16)
        pad.pack(fill="both", expand=True)

        ttk.Label(pad, text="Scouting Team Member Roster Entry (Table 3)", font=("Segoe UI", 11, "bold"), foreground="#38BDF8").pack(anchor="w", pady=(0, 12))

        ttk.Label(pad, text="Full Name:").pack(anchor="w", pady=(0, 2))
        self.name_entry = ttk.Entry(pad, textvariable=self.name_var)
        self.name_entry.pack(fill="x", pady=(0, 8))

        ttk.Label(pad, text="Position / Professional Role:").pack(anchor="w", pady=(0, 2))
        self.pos_entry = ttk.Entry(pad, textvariable=self.pos_var)
        self.pos_entry.pack(fill="x", pady=(0, 8))

        ttk.Label(pad, text="Field Operational Responsibility:").pack(anchor="w", pady=(0, 2))
        self.resp_entry = ttk.Entry(pad, textvariable=self.resp_var)
        self.resp_entry.pack(fill="x", pady=(0, 16))

        btn_row = ttk.Frame(pad)
        btn_row.pack(fill="x")
        ttk.Button(btn_row, text="Cancel", command=self.destroy).pack(side="left")
        ttk.Button(btn_row, text="✔ Save Member", style="Accent.TButton", command=self.on_save).pack(side="right")

        self.bind("<Return>", lambda e: self.on_save())
        self.bind("<Escape>", lambda e: self.destroy())

        self.lift()
        self.focus_force()
        self.name_entry.focus_set()
        try:
            self.grab_set()
        except Exception:
            pass

    def on_save(self):
        name = self.name_var.get().strip()
        if not name:
            messagebox.showwarning("Missing Name", "Please enter member name.", parent=self)
            return
        self.result = {
            'name': name,
            'position': self.pos_var.get().strip(),
            'responsibility': self.resp_var.get().strip()
        }
        self.destroy()


class EquipmentDialog(tk.Toplevel):
    """Interactive modal to add or edit a scouting equipment asset."""
    def __init__(self, parent, eq_data: Optional[Any] = None):
        super().__init__(parent)
        self.title("Edit Equipment Item" if eq_data else "Add Equipment Item")
        self.geometry("540x420")
        self.minsize(480, 340)
        self.configure(bg="#0A0F1D")
        self.transient(parent)

        item_val = ""
        type_val = ""
        qty_val = "1"
        fleet_val = ""
        if isinstance(eq_data, dict):
            item_val = eq_data.get('item', '')
            type_val = eq_data.get('type', '')
            qty_val = str(eq_data.get('quantity', '1'))
            fleet_val = eq_data.get('fleet_no', '')
        elif isinstance(eq_data, (list, tuple)):
            item_val = str(eq_data[0]) if len(eq_data) > 0 else ""
            type_val = str(eq_data[1]) if len(eq_data) > 1 else ""
            qty_val = str(eq_data[2]) if len(eq_data) > 2 else "1"
            fleet_val = str(eq_data[3]) if len(eq_data) > 3 else ""

        self.result = None
        self.item_var = tk.StringVar(value=item_val)
        self.type_var = tk.StringVar(value=type_val)
        self.qty_var = tk.StringVar(value=qty_val)
        self.fleet_var = tk.StringVar(value=fleet_val)

        pad = ttk.Frame(self, padding=16)
        pad.pack(fill="both", expand=True)

        ttk.Label(pad, text="Scouting Equipment Roster Entry (Table 4)", font=("Segoe UI", 11, "bold"), foreground="#38BDF8").pack(anchor="w", pady=(0, 12))

        ttk.Label(pad, text="Equipment Item:").pack(anchor="w", pady=(0, 2))
        self.item_entry = ttk.Entry(pad, textvariable=self.item_var)
        self.item_entry.pack(fill="x", pady=(0, 8))

        ttk.Label(pad, text="Type / Manufacturer / Model:").pack(anchor="w", pady=(0, 2))
        self.type_entry = ttk.Entry(pad, textvariable=self.type_var)
        self.type_entry.pack(fill="x", pady=(0, 8))

        ttk.Label(pad, text="Quantity:").pack(anchor="w", pady=(0, 2))
        self.qty_entry = ttk.Entry(pad, textvariable=self.qty_var)
        self.qty_entry.pack(fill="x", pady=(0, 8))

        ttk.Label(pad, text="Fleet Number / Asset Tag:").pack(anchor="w", pady=(0, 2))
        self.fleet_entry = ttk.Entry(pad, textvariable=self.fleet_var)
        self.fleet_entry.pack(fill="x", pady=(0, 16))

        btn_row = ttk.Frame(pad)
        btn_row.pack(fill="x")
        ttk.Button(btn_row, text="Cancel", command=self.destroy).pack(side="left")
        ttk.Button(btn_row, text="✔ Save Equipment", style="Accent.TButton", command=self.on_save).pack(side="right")

        self.bind("<Return>", lambda e: self.on_save())
        self.bind("<Escape>", lambda e: self.destroy())

        self.lift()
        self.focus_force()
        self.item_entry.focus_set()
        try:
            self.grab_set()
        except Exception:
            pass

    def on_save(self):
        item = self.item_var.get().strip()
        if not item:
            messagebox.showwarning("Missing Item", "Please enter equipment item name.", parent=self)
            return
        self.result = {
            'item': item,
            'type': self.type_var.get().strip(),
            'quantity': self.qty_var.get().strip(),
            'fleet_no': self.fleet_var.get().strip()
        }
        self.destroy()


class ImageViewerDialog(tk.Toplevel):
    """High-resolution preview dialog for generated 300 DPI GIS maps."""
    def __init__(self, parent, title: str, image_path: str):
        super().__init__(parent)
        self.title(title)
        self.geometry("980x740")
        self.minsize(800, 600)
        self.configure(bg="#0A0F1D")
        self.transient(parent)

        container = ttk.Frame(self, padding=10)
        container.pack(fill="both", expand=True)

        top = ttk.Frame(container)
        top.pack(fill="x", pady=(0, 6))
        ttk.Label(top, text=title, font=("Segoe UI", 11, "bold"), foreground="#38BDF8").pack(side="left")
        ttk.Label(top, text="⚡ Powered by Nasrullah Khan", font=("Segoe UI", 9, "bold italic"), foreground="#38BDF8").pack(side="right")

        img_box = ttk.LabelFrame(container, text=" High-Resolution Map Preview (300 DPI) ", style="Section.TLabelframe", padding=6)
        img_box.pack(fill="both", expand=True)

        lbl = ttk.Label(img_box, text="Loading map...", anchor="center")
        lbl.pack(fill="both", expand=True)

        if os.path.exists(image_path):
            try:
                with Image.open(image_path) as im:
                    im.thumbnail((940, 640))
                    photo = ImageTk.PhotoImage(im)
                    lbl.configure(image=photo, text="")
                    lbl.image = photo
            except Exception as e:
                lbl.configure(text=f"Cannot render image: {str(e)}")
        else:
            lbl.configure(text="Image file does not exist on disk.")

        b_row = ttk.Frame(container)
        b_row.pack(fill="x", pady=(8, 0))
        ttk.Button(b_row, text="Close Window", style="Accent.TButton", command=self.destroy).pack(side="right")



class CustomMapDialog(tk.Toplevel):
    def __init__(self, parent, map_cfg: Optional[MapFigureConfig] = None, ai_assistant: Optional[AIScoutAssistant] = None, prospect_name: str = "Prospect"):
        super().__init__(parent)
        self.title("Configure Custom Map Figure")
        self.geometry("640x520")
        self.minsize(560, 460)
        self.configure(bg="#0A0F1D")
        self.transient(parent)
        self.grab_set()

        self.ai = ai_assistant
        self.prospect_name = prospect_name
        self.result: Optional[MapFigureConfig] = None

        self.file_var = tk.StringVar(value=map_cfg.file_path if map_cfg else "")
        self.title_var = tk.StringVar(value=map_cfg.title if map_cfg else "Figure: Custom Operational Map")
        self.sec_var = tk.StringVar(value=map_cfg.target_section if map_cfg else REPORT_SECTION_CHOICES[4])
        self.is_custom = map_cfg.is_custom if map_cfg else True
        self.key = map_cfg.key if map_cfg else ""

        self.build_ui(map_cfg.description if map_cfg else "")

    def build_ui(self, initial_desc: str):
        pad_frame = ttk.Frame(self, padding=16)
        pad_frame.pack(fill="both", expand=True)

        ttk.Label(pad_frame, text="Custom Map Figure Configuration", font=("Segoe UI", 12, "bold"), foreground="#38BDF8").pack(anchor="w", pady=(0, 10))

        # File picker
        ttk.Label(pad_frame, text="Map Image File (*.png, *.jpg, *.tif):").pack(anchor="w", pady=(0, 2))
        f_row = ttk.Frame(pad_frame)
        f_row.pack(fill="x", pady=(0, 8))
        ttk.Entry(f_row, textvariable=self.file_var).pack(side="left", fill="x", expand=True, padx=(0, 4))
        ttk.Button(f_row, text="Browse...", command=self.browse_file).pack(side="right")

        # Title / Caption
        ttk.Label(pad_frame, text="Figure Number & Title / Caption:").pack(anchor="w", pady=(0, 2))
        ttk.Entry(pad_frame, textvariable=self.title_var).pack(fill="x", pady=(0, 8))

        # Target Section
        ttk.Label(pad_frame, text="Target Report Section:").pack(anchor="w", pady=(0, 2))
        sec_combo = ttk.Combobox(pad_frame, textvariable=self.sec_var, values=REPORT_SECTION_CHOICES, state="readonly")
        sec_combo.pack(fill="x", pady=(0, 8))
        style_combobox_popdown(sec_combo)

        # Description Header + AI Draft button
        desc_hdr = ttk.Frame(pad_frame)
        desc_hdr.pack(fill="x", pady=(0, 2))
        ttk.Label(desc_hdr, text="Technical Description & Operational Summary:").pack(side="left")
        ttk.Button(desc_hdr, text="⚡ AI Draft Description", command=self.generate_ai_desc).pack(side="right")

        self.desc_text = tk.Text(pad_frame, bg="#0F172A", fg="#F8FAFC", insertbackground="#38BDF8",
                                 relief="flat", highlightthickness=1, highlightcolor="#38BDF8",
                                 highlightbackground="#334155", font=("Segoe UI", 9), height=7)
        self.desc_text.pack(fill="both", expand=True, pady=(0, 12))
        if initial_desc:
            self.desc_text.insert("1.0", initial_desc)

        btn_row = ttk.Frame(pad_frame)
        btn_row.pack(fill="x")
        ttk.Button(btn_row, text="Cancel", command=self.destroy).pack(side="left")
        ttk.Button(btn_row, text="✔ Save & Insert Map", style="Accent.TButton", command=self.on_save).pack(side="right")

    def browse_file(self):
        f = filedialog.askopenfilename(
            title="Select Map Image File",
            filetypes=[("Image Files", "*.png;*.jpg;*.jpeg;*.tif;*.tiff;*.bmp"), ("All Files", "*.*")]
        )
        if f:
            self.file_var.set(os.path.normpath(f))

    def generate_ai_desc(self):
        if not self.ai:
            return
        m_title = self.title_var.get().strip()
        m_sec = self.sec_var.get().strip()
        draft = self.ai.draft_map_description(m_title, self.prospect_name, m_sec)
        self.desc_text.delete("1.0", "end")
        self.desc_text.insert("1.0", draft)

    def on_save(self):
        f = self.file_var.get().strip()
        t = self.title_var.get().strip()
        s = self.sec_var.get().strip()
        d = self.desc_text.get("1.0", "end").strip()

        if not t:
            messagebox.showwarning("Missing Title", "Please provide a title for this map figure.", parent=self)
            return

        self.result = MapFigureConfig(
            key=self.key,
            default_title=t,
            target_section=s,
            is_custom=self.is_custom,
            file_path=f,
            description=d,
            enabled=True
        )
        self.destroy()


# Note: PhotoReviewDialog and InteractiveScoutMap are imported from photo_map_viewer.py
# which provides full dual-pane photo curation, interactive slippy GIS maps,
# route/waypoint overlay, auto-panning, wheel zoom, and jump-to-photo.


# ==============================================================================
# MAIN DESKTOP APPLICATION GUI (TKINTER / TTK)
# ==============================================================================

def optimize_docx_media_for_target_mb(docx_path: str, target_mb: float = 10.0, enforce_limit: bool = True, log_cb=None) -> bool:
    """
    Analyzes the DOCX archive, preserves all Map Figures (image1 through image12)
    100% LOSSLESS at original 300 DPI, and dynamically budgets field photo compression
    (image13 onwards) so that the exported PDF strictly satisfies the user's target MB limit.
    """
    if not enforce_limit or target_mb <= 0:
        if log_cb:
            log_cb("PDF Size Calibration: Limit enforcement DISABLED (Original high-res media retained)")
        return True

    if not os.path.exists(docx_path):
        return False

    if log_cb:
        log_cb(f"Analyzing report media for target PDF limit: {target_mb:.1f} MB...")

    temp_optimized = docx_path + ".optimized.docx"
    fixed_overhead_mb = 3.2
    available_photo_budget_mb = max(2.0, target_mb - fixed_overhead_mb)

    try:
        with zipfile.ZipFile(docx_path, 'r') as zin:
            namelist = zin.namelist()
            media_files = [f for f in namelist if f.startswith('word/media/')]

            photo_entries = []
            for f in media_files:
                base = os.path.basename(f)
                m = re.match(r"image(\d+)\.(png|jpe?g)", base, re.IGNORECASE)
                if m and int(m.group(1)) >= 13:
                    photo_entries.append((int(m.group(1)), f))

            n_photos = len(photo_entries)
            if log_cb:
                log_cb(f"Report Analysis: {len(media_files)} media items detected ({n_photos} field photo plates, {len(media_files) - n_photos} Map Figures & Charts).")
                log_cb("Figures 1-9 (Core Maps & Charts): Preserved 100% LOSSLESS at 300 DPI.")

            if n_photos > 0:
                budget_per_photo_bytes = (available_photo_budget_mb * 1024 * 1024) / n_photos
                if target_mb <= 10.5:
                    max_dim = 1400
                    jpg_quality = 72
                elif target_mb <= 15.5:
                    max_dim = 1600
                    jpg_quality = 78
                elif target_mb <= 25.5:
                    max_dim = 1920
                    jpg_quality = 84
                elif target_mb <= 50.5:
                    max_dim = 2400
                    jpg_quality = 88
                else:
                    max_dim = 3000
                    jpg_quality = 92

                if log_cb:
                    log_cb(f"Dynamic Media Budget: ~{budget_per_photo_bytes / 1024:.0f} KB/photo (Max Dimension: {max_dim}px, Quality: {jpg_quality}).")
            else:
                max_dim = 2000
                jpg_quality = 85

            dummy_wdp = b""
            for f in media_files:
                if f.lower().endswith('.wdp'):
                    data = zin.read(f)
                    if len(data) < 1000:
                        dummy_wdp = data
                        break

            with zipfile.ZipFile(temp_optimized, 'w', compression=zipfile.ZIP_DEFLATED) as zout:
                for item in zin.infolist():
                    fname = item.filename
                    data = zin.read(fname)

                    if fname.startswith('word/media/'):
                        base = os.path.basename(fname)
                        m = re.match(r"image(\d+)\.(png|jpe?g)", base, re.IGNORECASE)
                        if m and int(m.group(1)) >= 13:
                            try:
                                im = Image.open(io.BytesIO(data))
                                if max(im.width, im.height) > max_dim:
                                    im.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
                                if im.mode in ('RGBA', 'LA') or (im.mode == 'P' and 'transparency' in im.info):
                                    rgb = Image.new('RGB', im.size, (255, 255, 255))
                                    rgb.paste(im, mask=im.split()[3] if im.mode == 'RGBA' else None)
                                else:
                                    rgb = im.convert('RGB')

                                buf = io.BytesIO()
                                rgb.save(buf, format='JPEG', quality=jpg_quality, optimize=True)
                                data = buf.getvalue()
                            except Exception:
                                pass
                        elif fname.lower().endswith('.wdp') and dummy_wdp:
                            data = dummy_wdp

                    zout.writestr(item, data)

        if os.path.exists(temp_optimized):
            shutil.move(temp_optimized, docx_path)
            new_docx_mb = os.path.getsize(docx_path) / 1024 / 1024
            if log_cb:
                log_cb(f"Word Document media optimization complete: {new_docx_mb:.2f} MB.")
            return True
    except Exception as e:
        if log_cb:
            log_cb(f"Warning during media optimization: {str(e)}")
        if os.path.exists(temp_optimized):
            try:
                os.remove(temp_optimized)
            except Exception:
                pass
        return False



class ScoutingSuiteApp(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("ARGAS Seismic Scouting Suite & Report Generator — Powered by Nasrullah Khan")
        self.geometry("1240x860")
        self.minsize(1080, 720)

        # Core Engines
        self.profile_mgr = ProfileManager()
        self.boundary_mgr = BoundaryManager()
        self.maps_mgr = MapsManager()
        self.ai = AIScoutAssistant()
        self.journal_mgr = ScoutingJournalManager(project_id="Amzan South")

        # State Variables
        self.current_profile_data = copy.deepcopy(DEFAULT_PRELIMINARY_PROFILE)
        self.terrain_analysis_results = []
        self.generated_pie_chart_path = ""
        self.generated_terrain_map_path = ""
        self.user_terrain_map_path = tk.StringVar(value="")
        self.terrain_map_mode_var = tk.StringVar(value="system")

        self.aramco_contractual_results = []
        self.generated_aramco_map_path = ""
        self.user_aramco_map_path = tk.StringVar(value="")
        self.aramco_map_mode_var = tk.StringVar(value="system")

        self.curated_photos_list = []
        self.loaded_field_notes = []
        self.include_non_geotagged_var = tk.BooleanVar(value=True)
        self.is_processing = False

        self.pdf_enforce_limit_var = tk.BooleanVar(value=True)
        self.pdf_target_mb_var = tk.DoubleVar(value=10.0)
        self.template_mode_var = tk.StringVar(value=ReportTemplateProcessingMode.EXACT_COPY_SIZE_OPT)
        self.user_section_prompts = {}

        self.gemini_key_var = tk.StringVar(value=self.ai.api_key)
        self.gemini_key_var.trace_add("write", self._on_gemini_key_changed)

        self.setup_styles()
        self.build_ui()
        self.update_ai_status_display()

    def _on_gemini_key_changed(self, *args):
        k = self.gemini_key_var.get().strip()
        self.ai.set_api_key(k)
        if hasattr(self, 'ai_badge_lbl'):
            self.update_ai_status_display()

    def setup_styles(self):
        self.configure(bg="#0A0F1D")

        # Global Tk option database overrides for Combobox popdowns, Listboxes, and Menus:
        # Enforces crisp dark slate background (#1E293B) and brilliant white text (#FFFFFF)
        self.option_add('*TCombobox*Listbox.background', '#1E293B')
        self.option_add('*TCombobox*Listbox.foreground', '#FFFFFF')
        self.option_add('*TCombobox*Listbox.selectBackground', '#0284C7')
        self.option_add('*TCombobox*Listbox.selectForeground', '#FFFFFF')
        self.option_add('*TCombobox*Listbox.font', ('Segoe UI', 9))
        self.option_add('*ComboboxPopdown*Listbox.background', '#1E293B')
        self.option_add('*ComboboxPopdown*Listbox.foreground', '#FFFFFF')
        self.option_add('*ComboboxPopdown*Listbox.selectBackground', '#0284C7')
        self.option_add('*ComboboxPopdown*Listbox.selectForeground', '#FFFFFF')
        self.option_add('*ComboboxPopdown*Listbox.font', ('Segoe UI', 9))
        self.option_add('*Listbox.background', '#1E293B')
        self.option_add('*Listbox.foreground', '#FFFFFF')
        self.option_add('*Listbox.selectBackground', '#0284C7')
        self.option_add('*Listbox.selectForeground', '#FFFFFF')

        # Global Tk option database overrides for Spinbox:
        # Enforces dark navy field (#0F172A) and brilliant white text (#FFFFFF)
        self.option_add('*Spinbox.background', '#0F172A')
        self.option_add('*Spinbox.foreground', '#FFFFFF')
        self.option_add('*Spinbox.insertBackground', '#38BDF8')
        self.option_add('*Spinbox.selectBackground', '#0284C7')
        self.option_add('*Spinbox.selectForeground', '#FFFFFF')
        self.option_add('*TSpinbox*fieldbackground', '#0F172A')
        self.option_add('*TSpinbox*foreground', '#FFFFFF')

        style = ttk.Style(self)
        style.theme_use("clam")

        BG = "#0A0F1D"
        SURFACE = "#1E293B"
        BORDER = "#334155"
        ACCENT = "#0284C7"
        ACCENT_HOVER = "#0369A1"
        TEXT_LIGHT = "#FFFFFF"
        TEXT_MUTED = "#CBD5E1"

        style.configure(".", background=BG, foreground=TEXT_LIGHT, font=("Segoe UI", 9))
        style.configure("TFrame", background=BG)
        style.configure("Surface.TFrame", background=SURFACE)

        style.configure("Header.TLabel", background=BG, foreground="#38BDF8", font=("Segoe UI", 13, "bold"))
        style.configure("SubHeader.TLabel", background=BG, foreground=TEXT_MUTED, font=("Segoe UI", 9))

        style.configure("Section.TLabelframe", background=SURFACE, relief="flat", borderwidth=1)
        style.configure("Section.TLabelframe.Label", background=SURFACE, foreground="#38BDF8", font=("Segoe UI", 9, "bold"))

        style.configure("TButton", font=("Segoe UI", 9, "bold"), background=SURFACE, foreground=TEXT_LIGHT,
                        borderwidth=1, relief="flat", padding=(9, 5))
        style.map("TButton", background=[("active", BORDER), ("disabled", "#0F172A")],
                  foreground=[("disabled", "#64748B")])

        style.configure("Accent.TButton", background=ACCENT, foreground="#FFFFFF")
        style.map("Accent.TButton", background=[("active", ACCENT_HOVER)])

        style.configure("Success.TButton", background="#059669", foreground="#FFFFFF")
        style.map("Success.TButton", background=[("active", "#047857")])

        style.configure("Warning.TButton", background="#D97706", foreground="#FFFFFF")
        style.map("Warning.TButton", background=[("active", "#B45309")])

        style.configure("TEntry", fieldbackground="#0F172A", foreground="#FFFFFF", insertcolor="#38BDF8",
                        bordercolor=BORDER, padding=4)
        style.map("TEntry",
                  fieldbackground=[("readonly", "#1E293B"), ("disabled", "#0F172A")],
                  foreground=[("readonly", "#FFFFFF"), ("disabled", "#64748B")])

        style.configure("TCombobox", fieldbackground="#1E293B", background="#1E293B",
                        foreground="#FFFFFF", darkcolor="#334155", lightcolor="#334155",
                        bordercolor=BORDER, arrowcolor="#38BDF8", padding=4)
        style.map("TCombobox",
                  fieldbackground=[("readonly", "#1E293B"), ("disabled", "#0F172A"), ("active", "#334155")],
                  foreground=[("readonly", "#FFFFFF"), ("disabled", "#64748B"), ("active", "#FFFFFF")],
                  background=[("readonly", "#1E293B"), ("active", "#334155")],
                  arrowcolor=[("readonly", "#38BDF8"), ("disabled", "#475569")])

        # High-Contrast TSpinbox: Dark slate field (#0F172A), bright white numbers (#FFFFFF), sky blue arrows
        style.configure("TSpinbox", fieldbackground="#0F172A", background="#1E293B",
                        foreground="#FFFFFF", darkcolor="#334155", lightcolor="#334155",
                        bordercolor=BORDER, arrowcolor="#38BDF8", insertcolor="#38BDF8",
                        padding=4, arrowsize=11)
        style.map("TSpinbox",
                  fieldbackground=[("readonly", "#1E293B"), ("disabled", "#0F172A"), ("active", "#0F172A"), ("!disabled", "#0F172A")],
                  foreground=[("readonly", "#FFFFFF"), ("disabled", "#64748B"), ("active", "#FFFFFF"), ("!disabled", "#FFFFFF")],
                  arrowcolor=[("active", "#38BDF8"), ("disabled", "#475569")])

        style.configure("TNotebook", background=BG, tabmargins=[2, 5, 2, 0], borderwidth=0)
        style.configure("TNotebook.Tab", background=SURFACE, foreground=TEXT_MUTED, padding=[12, 6],
                        font=("Segoe UI", 9, "bold"), borderwidth=0)
        style.map("TNotebook.Tab", background=[("selected", ACCENT)], foreground=[("selected", "#FFFFFF")])

        style.configure("Treeview", background="#0F172A", foreground="#FFFFFF", fieldbackground="#0F172A",
                        rowheight=24, font=("Segoe UI", 9), borderwidth=0)
        style.configure("Treeview.Heading", background=SURFACE, foreground="#38BDF8", font=("Segoe UI", 9, "bold"))
        style.map("Treeview", background=[("selected", ACCENT)], foreground=[("selected", "#FFFFFF")])

        style.configure("Horizontal.TProgressbar", background="#38BDF8", troughcolor="#0F172A", borderwidth=0)

    def build_ui(self):
        root_container = ttk.Frame(self, padding=10)
        root_container.pack(fill="both", expand=True)

        header = ttk.Frame(root_container)
        header.pack(fill="x", pady=(0, 8))

        top_row = ttk.Frame(header)
        top_row.pack(fill="x")
        
        title_frame = ttk.Frame(top_row)
        title_frame.pack(side="left", anchor="w")
        ttk.Label(title_frame, text="ARGAS SEISMIC SCOUTING SUITE & REPORT GENERATOR", style="Header.TLabel").pack(anchor="w")
        ttk.Label(title_frame, text="⚡ Powered by Nasrullah Khan", font=("Segoe UI", 9, "bold italic"), foreground="#38BDF8").pack(anchor="w")

        # Profile selection in top bar with high contrast styling
        prof_bar = ttk.Frame(top_row)
        prof_bar.pack(side="right")
        ttk.Label(prof_bar, text="Report Profile:", font=("Segoe UI", 9, "bold"), foreground="#38BDF8").pack(side="left", padx=(0, 6))
        self.profile_var = tk.StringVar(value="ARGAS Preliminary Scouting Report - Saudi Aramco")
        self.profile_combo = ttk.Combobox(prof_bar, textvariable=self.profile_var, values=self.profile_mgr.list_profiles(), width=40, state="readonly")
        self.profile_combo.pack(side="left", padx=(0, 6))
        self.profile_combo.bind("<<ComboboxSelected>>", self.on_profile_selected)
        style_combobox_popdown(self.profile_combo)
        ttk.Button(prof_bar, text="Save Profile", command=self.save_current_profile).pack(side="left", padx=(0, 4))
        ttk.Button(prof_bar, text="📘 User Manual & Help", style="Warning.TButton", command=self.open_help_dialog).pack(side="left")

        sub = ttk.Label(header, text="Saudi Aramco Concession Reconnaissance • Multi-Block Geomatics • Dynamic Maps (Core 1-9 & Custom) • AI Vision & ~10MB PDF", style="SubHeader.TLabel")
        sub.pack(anchor="w", pady=(4, 0))

        # ======================================================================
        # TOP STRATEGY RIBBON: Master Template Processing Mode & AI Co-Authoring
        # ======================================================================
        strategy_ribbon = tk.Frame(header, bg="#0F172A", highlightthickness=1, highlightbackground="#38BDF8", padx=10, pady=7)
        strategy_ribbon.pack(fill="x", pady=(8, 0))

        s_row = tk.Frame(strategy_ribbon, bg="#0F172A")
        s_row.pack(fill="x")

        tk.Label(s_row, text="⚡ Report Strategy:", font=("Segoe UI", 9, "bold"), fg="#38BDF8", bg="#0F172A").pack(side="left", padx=(0, 6))

        # Top Dropdown Menu defaulting to Option 1
        self.template_mode_combo = ttk.Combobox(
            s_row,
            textvariable=self.template_mode_var,
            values=ReportTemplateProcessingMode.all_modes(),
            width=58,
            state="readonly",
            font=("Segoe UI", 9, "bold")
        )
        self.template_mode_combo.pack(side="left", padx=(0, 10))
        self.template_mode_combo.bind("<<ComboboxSelected>>", self.on_template_mode_changed)
        style_combobox_popdown(self.template_mode_combo)

        self.btn_section_prompts = ttk.Button(
            s_row,
            text="✍️ Configure Section Prompts...",
            style="Accent.TButton",
            command=self.open_section_prompts_dialog
        )
        self.btn_section_prompts.pack(side="left", padx=(0, 6))

        ttk.Button(
            s_row,
            text="📑 Generate Report",
            style="Success.TButton",
            command=self.start_generate_word_report
        ).pack(side="left", padx=(0, 6))

        self.strategy_badge_lbl = tk.Label(
            s_row,
            text="SIZE OPTIMIZED",
            font=("Segoe UI", 8, "bold"),
            bg="#064E3B",
            fg="#34D399",
            padx=8,
            pady=3
        )
        self.strategy_badge_lbl.pack(side="right")

        self.strategy_desc_lbl = tk.Label(
            strategy_ribbon,
            text=MODE_METADATA[ReportTemplateProcessingMode.EXACT_COPY_SIZE_OPT]["description"],
            font=("Segoe UI", 8),
            fg="#94A3B8",
            bg="#0F172A",
            wraplength=1100,
            justify="left"
        )
        self.strategy_desc_lbl.pack(anchor="w", pady=(4, 0))

        self.notebook = ttk.Notebook(root_container)
        self.notebook.pack(fill="both", expand=True, pady=(0, 6))

        # 1. Project Setup
        self.tab_setup = ttk.Frame(self.notebook, padding=8)
        self.notebook.add(self.tab_setup, text=" 1. Project Setup & Metadata ")

        # 2. Scouting Team & Logistics
        self.tab_ops = ttk.Frame(self.notebook, padding=8)
        self.notebook.add(self.tab_ops, text=" 2. Scouting Operations & Team ")

        # 3. Prospect Boundary Coordinates
        self.tab_boundary = ttk.Frame(self.notebook, padding=8)
        self.notebook.add(self.tab_boundary, text=" 3. Boundary Coordinates (Table 5) ")

        # 4. Field Tracks & Digital Notes
        self.tab_tracks = ttk.Frame(self.notebook, padding=8)
        self.notebook.add(self.tab_tracks, text=" 4. Field Tracks & Notes ")

        # 5. Map Figures Matrix (All Optional + Custom Maps)
        self.tab_maps = ttk.Frame(self.notebook, padding=8)
        self.notebook.add(self.tab_maps, text=" 5. Map Figures Matrix ")

        # 6. Terrain GIS & Map (Sec 6)
        self.tab_terrain = ttk.Frame(self.notebook, padding=8)
        self.notebook.add(self.tab_terrain, text=" 6. Terrain GIS & Map (Sec 6) ")

        # 7. Aramco Remoteness & Area Types (Sec 7)
        self.tab_aramco = ttk.Frame(self.notebook, padding=8)
        self.notebook.add(self.tab_aramco, text=" 7. Aramco Remoteness & Areas (Sec 7) ")

        # 8. Photo Curation & Vision AI
        self.tab_photos = ttk.Frame(self.notebook, padding=8)
        self.notebook.add(self.tab_photos, text=" 8. Photos & Vision AI ")

        # 9. Report Assembly & Calibrated PDF
        self.tab_export = ttk.Frame(self.notebook, padding=8)
        self.notebook.add(self.tab_export, text=" 9. Report Assembly & ~10MB PDF ")

        # 10. Daily Field Journal, Rough Thoughts Categorizer & Mobile Sync
        self.tab_journal = ttk.Frame(self.notebook, padding=8)
        self.notebook.add(self.tab_journal, text=" 10. Daily Field Journal & Mobile Sync ")

        self.build_tab_setup()
        self.build_tab_ops()
        self.build_tab_boundary()
        self.build_tab_tracks()
        self.build_tab_maps()
        self.build_tab_terrain()
        self.build_tab_aramco()
        self.build_tab_photos()
        self.build_tab_export()
        self.build_tab_journal()

    def on_template_mode_changed(self, event=None):
        mode = self.template_mode_var.get()
        meta = MODE_METADATA.get(mode, {})
        if hasattr(self, 'strategy_desc_lbl'):
            self.strategy_desc_lbl.configure(text=meta.get('description', ''))
        if hasattr(self, 'strategy_badge_lbl'):
            b_text = meta.get('badge', 'READY')
            b_col = meta.get('badge_color', '#0284C7')
            self.strategy_badge_lbl.configure(text=b_text, bg='#1E293B', fg=b_col)
        if hasattr(self, 'tab_export_mode_combo') and self.tab_export_mode_combo.get() != mode:
            self.tab_export_mode_combo.set(mode)

    def _build_project_meta(self) -> Dict[str, Any]:
        prospect = self.prospect_name_var.get().strip() if hasattr(self, 'prospect_name_var') else 'Prospect Area'
        crew = self.crew_name_var.get().strip() if hasattr(self, 'crew_name_var') else 'Crew S-86'
        return {
            'prospect_name': prospect,
            'crew_name': crew,
            'report_date': self.report_date_var.get().strip() if hasattr(self, 'report_date_var') else 'October 2026',
            'contract_no': self.contract_no_var.get().strip() if hasattr(self, 'contract_no_var') else '340400001',
            'contractor_name': f'ARGAS ({crew})',
            'revision_no': self.rev_no_var.get().strip() if hasattr(self, 'rev_no_var') else 'Rev 0',
            'revision_date': self.rev_date_var.get().strip() if hasattr(self, 'rev_date_var') else '26/10/2026',
            'prepared_by': self.prep_by_var.get().strip() if hasattr(self, 'prep_by_var') else 'Party Chief / Chief Surveyor',
            'reviewed_by': self.rev_by_var.get().strip() if hasattr(self, 'rev_by_var') else 'Operations Manager / QHSE Manager',
            'approved_by': self.appr_by_var.get().strip() if hasattr(self, 'appr_by_var') else 'Saudi Aramco GDAD Rep',
            'distribution_list': self.current_profile_data.get('metadata', {}).get('distribution_list', []),
            'scouting_team': self.current_profile_data.get('metadata', {}).get('scouting_team', []),
            'scouting_equipment': self.current_profile_data.get('metadata', {}).get('scouting_equipment', []),
            'objectives': self.current_profile_data.get('metadata', {}).get('objectives', []),
            'communication_means': self.current_profile_data.get('metadata', {}).get('communication_means', [])
        }

    def open_section_prompts_dialog(self):
        analyzer = ReportAnalyzerEngine(self.ai)
        tpl_path = self.template_doc_var.get().strip() if hasattr(self, 'template_doc_var') else ''
        sections = analyzer.detect_sections_and_map_sources(
            template_path=tpl_path,
            project_meta=self._build_project_meta(),
            boundary_mgr=self.boundary_mgr,
            terrain_data=self.terrain_analysis_results,
            aramco_data=getattr(self, 'aramco_contractual_results', None),
            maps_mgr=self.maps_mgr,
            curated_photos=self.curated_photos_list,
            user_section_prompts=self.user_section_prompts
        )

        def save_prompts_cb(prompts_dict):
            self.user_section_prompts = prompts_dict
            count = len(prompts_dict)
            if hasattr(self, 'export_log'):
                self.export_log(f'Updated user initial guidance for {count} report section(s).')
            if hasattr(self, 'btn_section_prompts'):
                self.btn_section_prompts.configure(text=f'✍️ Section Prompts ({count} Active)...')

        SectionPromptsDialog(
            parent=self,
            sections=sections,
            on_save_callback=save_prompts_cb,
            ai_assistant=self.ai,
            project_meta=self._build_project_meta()
        )

    def open_help_dialog(self):
        HelpDialog(self)

    # --------------------------------------------------------------------------
    # TAB 1: PROJECT SETUP & METADATA
    # --------------------------------------------------------------------------
    def build_tab_setup(self):
        meta = self.current_profile_data.get('metadata', {})

        box1 = ttk.LabelFrame(self.tab_setup, text=" Project Identification & Document Control ", style="Section.TLabelframe", padding=10)
        box1.pack(fill="x", pady=(0, 8))

        row1 = ttk.Frame(box1)
        row1.pack(fill="x", pady=(0, 6))
        ttk.Label(row1, text="Prospect Name:").grid(row=0, column=0, sticky="w", padx=(0, 6))
        self.prospect_name_var = tk.StringVar(value=meta.get('prospect_name', 'Amzan South'))
        ttk.Entry(row1, textvariable=self.prospect_name_var, width=24).grid(row=0, column=1, padx=(0, 16))

        ttk.Label(row1, text="Crew Name:").grid(row=0, column=2, sticky="w", padx=(0, 6))
        self.crew_name_var = tk.StringVar(value=meta.get('crew_name', 'Crew S-86'))
        ttk.Entry(row1, textvariable=self.crew_name_var, width=16).grid(row=0, column=3, padx=(0, 16))

        ttk.Label(row1, text="Report Date:").grid(row=0, column=4, sticky="w", padx=(0, 6))
        self.report_date_var = tk.StringVar(value=meta.get('report_date', 'October 2026'))
        ttk.Entry(row1, textvariable=self.report_date_var, width=18).grid(row=0, column=5)

        row2 = ttk.Frame(box1)
        row2.pack(fill="x", pady=(0, 6))
        ttk.Label(row2, text="Contract Number:").grid(row=0, column=0, sticky="w", padx=(0, 6))
        self.contract_no_var = tk.StringVar(value=meta.get('contract_no', '340400001'))
        ttk.Entry(row2, textvariable=self.contract_no_var, width=24).grid(row=0, column=1, padx=(0, 16))

        ttk.Label(row2, text="Revision No:").grid(row=0, column=2, sticky="w", padx=(0, 6))
        self.rev_no_var = tk.StringVar(value=meta.get('revision_no', 'Rev 0'))
        ttk.Entry(row2, textvariable=self.rev_no_var, width=16).grid(row=0, column=3, padx=(0, 16))

        ttk.Label(row2, text="Revision Date:").grid(row=0, column=4, sticky="w", padx=(0, 6))
        self.rev_date_var = tk.StringVar(value=meta.get('revision_date', '26/10/2026'))
        ttk.Entry(row2, textvariable=self.rev_date_var, width=18).grid(row=0, column=5)

        row3 = ttk.Frame(box1)
        row3.pack(fill="x")
        ttk.Label(row3, text="Prepared by:").grid(row=0, column=0, sticky="w", padx=(0, 6))
        self.prep_by_var = tk.StringVar(value=meta.get('prepared_by', 'Party Chief / Chief Surveyor'))
        ttk.Entry(row3, textvariable=self.prep_by_var, width=24).grid(row=0, column=1, padx=(0, 16))

        ttk.Label(row3, text="Reviewed by:").grid(row=0, column=2, sticky="w", padx=(0, 6))
        self.rev_by_var = tk.StringVar(value=meta.get('reviewed_by', 'Operations Manager / QHSE Manager'))
        ttk.Entry(row3, textvariable=self.rev_by_var, width=24).grid(row=0, column=3, padx=(0, 16))

        ttk.Label(row3, text="Approved by:").grid(row=0, column=4, sticky="w", padx=(0, 6))
        self.appr_by_var = tk.StringVar(value=meta.get('approved_by', 'Saudi Aramco GDAD Representative'))
        ttk.Entry(row3, textvariable=self.appr_by_var, width=26).grid(row=0, column=5)

        # Distribution List Grid
        box2 = ttk.LabelFrame(self.tab_setup, text=" Distribution List (Table 1) ", style="Section.TLabelframe", padding=10)
        box2.pack(fill="both", expand=True)

        cols = ("Company", "Position")
        self.dist_tree = ttk.Treeview(box2, columns=cols, show="headings", height=5)
        self.dist_tree.heading("Company", text="Company")
        self.dist_tree.heading("Position", text="Position / Recipient Role")
        self.dist_tree.column("Company", width=240, anchor="w")
        self.dist_tree.column("Position", width=500, anchor="w")
        self.dist_tree.pack(side="left", fill="both", expand=True)

        sb = ttk.Scrollbar(box2, orient="vertical", command=self.dist_tree.yview)
        self.dist_tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")

        self.populate_dist_tree(meta.get('distribution_list', []))

    def populate_dist_tree(self, dist_list):
        self.dist_tree.delete(*self.dist_tree.get_children())
        for d in dist_list:
            self.dist_tree.insert("", "end", values=(d.get('company', ''), d.get('position', '')))

    # --------------------------------------------------------------------------
    # TAB 2: SCOUTING OPERATIONS & TEAM
    # --------------------------------------------------------------------------
    def build_tab_ops(self):
        meta = self.current_profile_data.get('metadata', {})

        # Scouting Dates & GPX Scan
        top_box = ttk.LabelFrame(self.tab_ops, text=" Scouting Trip Dates & Duration ", style="Section.TLabelframe", padding=8)
        top_box.pack(fill="x", pady=(0, 8))

        d_row = ttk.Frame(top_box)
        d_row.pack(fill="x")
        ttk.Label(d_row, text="Date Travel to Area:").pack(side="left", padx=(0, 6))
        self.travel_date_var = tk.StringVar(value="08/08/2026")
        ttk.Entry(d_row, textvariable=self.travel_date_var, width=14).pack(side="left", padx=(0, 16))

        ttk.Label(d_row, text="Scouting Dates:").pack(side="left", padx=(0, 6))
        self.scout_dates_var = tk.StringVar(value="09/08/2026 to 14/08/2026 (6 Operational Days)")
        ttk.Entry(d_row, textvariable=self.scout_dates_var, width=44).pack(side="left", padx=(0, 16))

        ttk.Button(d_row, text="⚡ Auto-Scan Dates from GPX Track", command=self.auto_scan_gpx_dates).pack(side="right")

        # Team & Equipment Split
        split = ttk.Frame(self.tab_ops)
        split.pack(fill="both", expand=True)

        t_box = ttk.LabelFrame(split, text=" Scouting Team Roster (Table 3) ", style="Section.TLabelframe", padding=8)
        t_box.pack(side="left", fill="both", expand=True, padx=(0, 4))

        cols_t = ("No", "Name", "Position", "Responsibility")
        self.team_tree = ttk.Treeview(t_box, columns=cols_t, show="headings", height=5)
        self.team_tree.heading("No", text="#")
        self.team_tree.heading("Name", text="Full Name")
        self.team_tree.heading("Position", text="Position")
        self.team_tree.heading("Responsibility", text="Field Responsibility")
        self.team_tree.column("No", width=35, anchor="center")
        self.team_tree.column("Name", width=140, anchor="w")
        self.team_tree.column("Position", width=120, anchor="w")
        self.team_tree.column("Responsibility", width=190, anchor="w")
        self.team_tree.pack(fill="both", expand=True)

        self.team_tree.bind("<<TreeviewSelect>>", self.on_team_select)
        self.team_tree.bind("<Double-1>", lambda e: self.edit_team_member())

        # Inline Quick Edit / Entry Box for Team Member
        t_edit_box = ttk.LabelFrame(t_box, text=" Selected Member Details / Quick Edit ", padding=6)
        t_edit_box.pack(fill="x", pady=(6, 4))

        t_r1 = ttk.Frame(t_edit_box)
        t_r1.pack(fill="x", pady=2)
        ttk.Label(t_r1, text="Name:", width=12).pack(side="left")
        self.team_name_var = tk.StringVar()
        ttk.Entry(t_r1, textvariable=self.team_name_var).pack(side="left", fill="x", expand=True)

        t_r2 = ttk.Frame(t_edit_box)
        t_r2.pack(fill="x", pady=2)
        ttk.Label(t_r2, text="Position:", width=12).pack(side="left")
        self.team_pos_var = tk.StringVar()
        ttk.Entry(t_r2, textvariable=self.team_pos_var).pack(side="left", fill="x", expand=True)

        t_r3 = ttk.Frame(t_edit_box)
        t_r3.pack(fill="x", pady=2)
        ttk.Label(t_r3, text="Responsibility:", width=12).pack(side="left")
        self.team_resp_var = tk.StringVar()
        ttk.Entry(t_r3, textvariable=self.team_resp_var).pack(side="left", fill="x", expand=True)

        t_btn_row = ttk.Frame(t_box)
        t_btn_row.pack(fill="x", pady=(4, 0))
        ttk.Button(t_btn_row, text="💾 Update Selected", style="Accent.TButton", command=self.update_team_from_fields).pack(side="left", padx=(0, 4))
        ttk.Button(t_btn_row, text="+ Add New", command=self.add_team_from_fields).pack(side="left", padx=(0, 4))
        ttk.Button(t_btn_row, text="✏ Edit (Modal)", command=self.edit_team_member).pack(side="left", padx=(0, 4))
        ttk.Button(t_btn_row, text="🗑 Delete", command=self.delete_team_member).pack(side="left", padx=(0, 4))
        ttk.Button(t_btn_row, text="🔄 Reset", command=self.reset_team_defaults).pack(side="right")
        self.team_status_lbl = ttk.Label(t_btn_row, text="", foreground="#4ADE80", font=("Segoe UI", 9, "bold"))
        self.team_status_lbl.pack(side="left", padx=(8, 0))

        eq_box = ttk.LabelFrame(split, text=" Equipment Roster (Table 4) ", style="Section.TLabelframe", padding=8)
        eq_box.pack(side="right", fill="both", expand=True, padx=(4, 0))

        cols_eq = ("Item", "Type", "Qty", "FleetNo")
        self.eq_tree = ttk.Treeview(eq_box, columns=cols_eq, show="headings", height=5)
        self.eq_tree.heading("Item", text="Item")
        self.eq_tree.heading("Type", text="Equipment Type / Model")
        self.eq_tree.heading("Qty", text="Qty")
        self.eq_tree.heading("FleetNo", text="Fleet No")
        self.eq_tree.column("Item", width=120, anchor="w")
        self.eq_tree.column("Type", width=160, anchor="w")
        self.eq_tree.column("Qty", width=45, anchor="center")
        self.eq_tree.column("FleetNo", width=110, anchor="w")
        self.eq_tree.pack(fill="both", expand=True)

        self.eq_tree.bind("<<TreeviewSelect>>", self.on_eq_select)
        self.eq_tree.bind("<Double-1>", lambda e: self.edit_equipment())

        # Inline Quick Edit / Entry Box for Equipment
        eq_edit_box = ttk.LabelFrame(eq_box, text=" Selected Equipment Details / Quick Edit ", padding=6)
        eq_edit_box.pack(fill="x", pady=(6, 4))

        eq_r1 = ttk.Frame(eq_edit_box)
        eq_r1.pack(fill="x", pady=2)
        ttk.Label(eq_r1, text="Item:", width=11).pack(side="left")
        self.eq_item_var = tk.StringVar()
        ttk.Entry(eq_r1, textvariable=self.eq_item_var).pack(side="left", fill="x", expand=True)

        eq_r2 = ttk.Frame(eq_edit_box)
        eq_r2.pack(fill="x", pady=2)
        ttk.Label(eq_r2, text="Type/Model:", width=11).pack(side="left")
        self.eq_type_var = tk.StringVar()
        ttk.Entry(eq_r2, textvariable=self.eq_type_var).pack(side="left", fill="x", expand=True)

        eq_r3 = ttk.Frame(eq_edit_box)
        eq_r3.pack(fill="x", pady=2)
        ttk.Label(eq_r3, text="Qty:", width=5).pack(side="left")
        self.eq_qty_var = tk.StringVar()
        ttk.Entry(eq_r3, textvariable=self.eq_qty_var, width=6).pack(side="left", padx=(0, 8))
        ttk.Label(eq_r3, text="Fleet No:", width=9).pack(side="left")
        self.eq_fleet_var = tk.StringVar()
        ttk.Entry(eq_r3, textvariable=self.eq_fleet_var).pack(side="left", fill="x", expand=True)

        eq_btn_row = ttk.Frame(eq_box)
        eq_btn_row.pack(fill="x", pady=(4, 0))
        ttk.Button(eq_btn_row, text="💾 Update Selected", style="Accent.TButton", command=self.update_eq_from_fields).pack(side="left", padx=(0, 4))
        ttk.Button(eq_btn_row, text="+ Add New", command=self.add_eq_from_fields).pack(side="left", padx=(0, 4))
        ttk.Button(eq_btn_row, text="✏ Edit (Modal)", command=self.edit_equipment).pack(side="left", padx=(0, 4))
        ttk.Button(eq_btn_row, text="🗑 Delete", command=self.delete_equipment).pack(side="left", padx=(0, 4))
        ttk.Button(eq_btn_row, text="🔄 Reset", command=self.reset_equipment_defaults).pack(side="right")
        self.eq_status_lbl = ttk.Label(eq_btn_row, text="", foreground="#4ADE80", font=("Segoe UI", 9, "bold"))
        self.eq_status_lbl.pack(side="left", padx=(8, 0))

        self.populate_team_and_eq(meta.get('scouting_team', []), meta.get('scouting_equipment', []))

    def on_team_select(self, event=None):
        sel = self.team_tree.selection()
        if not sel:
            return
        try:
            idx = int(sel[0].replace('t_', ''))
            team = self.current_profile_data.get('metadata', {}).get('scouting_team', [])
            if 0 <= idx < len(team):
                m = team[idx]
                self.team_name_var.set(m.get('name', ''))
                self.team_pos_var.set(m.get('position', ''))
                self.team_resp_var.set(m.get('responsibility', ''))
        except Exception:
            pass

    def on_eq_select(self, event=None):
        sel = self.eq_tree.selection()
        if not sel:
            return
        try:
            idx = int(sel[0].replace('eq_', ''))
            eq_list = self.current_profile_data.get('metadata', {}).get('scouting_equipment', [])
            if 0 <= idx < len(eq_list):
                eq = eq_list[idx]
                self.eq_item_var.set(eq.get('item', ''))
                self.eq_type_var.set(eq.get('type', ''))
                self.eq_qty_var.set(str(eq.get('quantity', '1')))
                self.eq_fleet_var.set(eq.get('fleet_no', ''))
        except Exception:
            pass

    def update_team_from_fields(self):
        sel = self.team_tree.selection()
        if not sel:
            messagebox.showinfo("Select Member", "Please select a team member in the table to update.", parent=self)
            return
        name = self.team_name_var.get().strip()
        if not name:
            messagebox.showwarning("Missing Name", "Please enter a full name for the team member.", parent=self)
            return
        idx = int(sel[0].replace('t_', ''))
        team = self.current_profile_data.setdefault('metadata', {}).setdefault('scouting_team', [])
        if 0 <= idx < len(team):
            team[idx] = {
                'no': str(idx + 1),
                'name': name,
                'position': self.team_pos_var.get().strip(),
                'responsibility': self.team_resp_var.get().strip()
            }
            self.populate_team_and_eq(team, self.current_profile_data['metadata'].get('scouting_equipment', []))
            self.team_tree.selection_set(f"t_{idx}")
            self.team_status_lbl.configure(text=f"✔ Updated: {name}")
            self.after(3000, lambda: self.team_status_lbl.configure(text=""))

    def add_team_from_fields(self):
        name = self.team_name_var.get().strip()
        if not name:
            self.add_team_member()
            return
        team = self.current_profile_data.setdefault('metadata', {}).setdefault('scouting_team', [])
        idx = len(team)
        team.append({
            'no': str(idx + 1),
            'name': name,
            'position': self.team_pos_var.get().strip(),
            'responsibility': self.team_resp_var.get().strip()
        })
        self.populate_team_and_eq(team, self.current_profile_data['metadata'].get('scouting_equipment', []))
        self.team_tree.selection_set(f"t_{idx}")
        self.team_status_lbl.configure(text=f"✔ Added: {name}")
        self.after(3000, lambda: self.team_status_lbl.configure(text=""))

    def update_eq_from_fields(self):
        sel = self.eq_tree.selection()
        if not sel:
            messagebox.showinfo("Select Equipment", "Please select an equipment item in the table to update.", parent=self)
            return
        item = self.eq_item_var.get().strip()
        if not item:
            messagebox.showwarning("Missing Item", "Please enter an equipment item name.", parent=self)
            return
        idx = int(sel[0].replace('eq_', ''))
        eq_list = self.current_profile_data.setdefault('metadata', {}).setdefault('scouting_equipment', [])
        if 0 <= idx < len(eq_list):
            eq_list[idx] = {
                'item': item,
                'type': self.eq_type_var.get().strip(),
                'quantity': self.eq_qty_var.get().strip(),
                'fleet_no': self.eq_fleet_var.get().strip()
            }
            self.populate_team_and_eq(self.current_profile_data['metadata'].get('scouting_team', []), eq_list)
            self.eq_tree.selection_set(f"eq_{idx}")
            self.eq_status_lbl.configure(text=f"✔ Updated: {item}")
            self.after(3000, lambda: self.eq_status_lbl.configure(text=""))

    def add_eq_from_fields(self):
        item = self.eq_item_var.get().strip()
        if not item:
            self.add_equipment()
            return
        eq_list = self.current_profile_data.setdefault('metadata', {}).setdefault('scouting_equipment', [])
        idx = len(eq_list)
        eq_list.append({
            'item': item,
            'type': self.eq_type_var.get().strip(),
            'quantity': self.eq_qty_var.get().strip(),
            'fleet_no': self.eq_fleet_var.get().strip()
        })
        self.populate_team_and_eq(self.current_profile_data['metadata'].get('scouting_team', []), eq_list)
        self.eq_tree.selection_set(f"eq_{idx}")
        self.eq_status_lbl.configure(text=f"✔ Added: {item}")
        self.after(3000, lambda: self.eq_status_lbl.configure(text=""))

    def populate_team_and_eq(self, team, eq_list):
        # Normalize team items to dicts
        norm_team = []
        for i, t in enumerate(team, start=1):
            if isinstance(t, dict):
                d = dict(t)
                d['no'] = str(i)
                norm_team.append(d)
            elif isinstance(t, (list, tuple)):
                norm_team.append({
                    'no': str(i),
                    'name': str(t[0]) if len(t) > 0 else '',
                    'position': str(t[1]) if len(t) > 1 else '',
                    'responsibility': str(t[2]) if len(t) > 2 else ''
                })
        self.current_profile_data.setdefault('metadata', {})['scouting_team'] = norm_team

        # Normalize eq items to dicts
        norm_eq = []
        for eq in eq_list:
            if isinstance(eq, dict):
                norm_eq.append(dict(eq))
            elif isinstance(eq, (list, tuple)):
                norm_eq.append({
                    'item': str(eq[0]) if len(eq) > 0 else '',
                    'type': str(eq[1]) if len(eq) > 1 else '',
                    'quantity': str(eq[2]) if len(eq) > 2 else '1',
                    'fleet_no': str(eq[3]) if len(eq) > 3 else ''
                })
        self.current_profile_data.setdefault('metadata', {})['scouting_equipment'] = norm_eq

        self.team_tree.delete(*self.team_tree.get_children())
        for idx, t in enumerate(norm_team, start=1):
            self.team_tree.insert("", "end", iid=f"t_{idx-1}", values=(idx, t.get('name', ''), t.get('position', ''), t.get('responsibility', '')))

        self.eq_tree.delete(*self.eq_tree.get_children())
        for idx, eq in enumerate(norm_eq, start=1):
            self.eq_tree.insert("", "end", iid=f"eq_{idx-1}", values=(eq.get('item', ''), eq.get('type', ''), eq.get('quantity', ''), eq.get('fleet_no', '')))

    def add_team_member(self):
        dlg = TeamMemberDialog(self)
        self.wait_window(dlg)
        if dlg.result:
            team = self.current_profile_data.setdefault('metadata', {}).setdefault('scouting_team', [])
            idx = len(team)
            dlg.result['no'] = str(idx + 1)
            team.append(dlg.result)
            self.populate_team_and_eq(team, self.current_profile_data['metadata'].get('scouting_equipment', []))
            self.team_tree.selection_set(f"t_{idx}")
            self.on_team_select()

    def edit_team_member(self):
        sel = self.team_tree.selection()
        if not sel:
            messagebox.showinfo("Select Member", "Please select a team member to edit.", parent=self)
            return
        idx = int(sel[0].replace('t_', ''))
        team = self.current_profile_data.setdefault('metadata', {}).setdefault('scouting_team', [])
        if 0 <= idx < len(team):
            dlg = TeamMemberDialog(self, team[idx])
            self.wait_window(dlg)
            if dlg.result:
                dlg.result['no'] = str(idx + 1)
                team[idx] = dlg.result
                self.populate_team_and_eq(team, self.current_profile_data['metadata'].get('scouting_equipment', []))
                self.team_tree.selection_set(f"t_{idx}")
                self.on_team_select()

    def delete_team_member(self):
        sel = self.team_tree.selection()
        if not sel:
            messagebox.showinfo("Select Member", "Please select a team member to delete.", parent=self)
            return
        idx = int(sel[0].replace('t_', ''))
        team = self.current_profile_data.setdefault('metadata', {}).setdefault('scouting_team', [])
        if 0 <= idx < len(team):
            m_name = team[idx].get('name', 'Member')
            if messagebox.askyesno("Confirm Delete", f"Remove '{m_name}' from Scouting Team?", parent=self):
                team.pop(idx)
                for i, m in enumerate(team, start=1):
                    m['no'] = str(i)
                self.populate_team_and_eq(team, self.current_profile_data['metadata'].get('scouting_equipment', []))
                self.team_name_var.set("")
                self.team_pos_var.set("")
                self.team_resp_var.set("")

    def reset_team_defaults(self):
        if messagebox.askyesno("Reset Team", "Reset Scouting Team to default ARGAS S-86 personnel?", parent=self):
            default_team = DEFAULT_PRELIMINARY_PROFILE.get('metadata', {}).get('scouting_team', [])
            self.current_profile_data.setdefault('metadata', {})['scouting_team'] = copy.deepcopy(default_team)
            self.populate_team_and_eq(self.current_profile_data['metadata']['scouting_team'], self.current_profile_data['metadata'].get('scouting_equipment', []))
            self.team_name_var.set("")
            self.team_pos_var.set("")
            self.team_resp_var.set("")

    def add_equipment(self):
        dlg = EquipmentDialog(self)
        self.wait_window(dlg)
        if dlg.result:
            eq_list = self.current_profile_data.setdefault('metadata', {}).setdefault('scouting_equipment', [])
            idx = len(eq_list)
            eq_list.append(dlg.result)
            self.populate_team_and_eq(self.current_profile_data['metadata'].get('scouting_team', []), eq_list)
            self.eq_tree.selection_set(f"eq_{idx}")
            self.on_eq_select()

    def edit_equipment(self):
        sel = self.eq_tree.selection()
        if not sel:
            messagebox.showinfo("Select Item", "Please select an equipment item to edit.", parent=self)
            return
        idx = int(sel[0].replace('eq_', ''))
        eq_list = self.current_profile_data.setdefault('metadata', {}).setdefault('scouting_equipment', [])
        if 0 <= idx < len(eq_list):
            dlg = EquipmentDialog(self, eq_list[idx])
            self.wait_window(dlg)
            if dlg.result:
                eq_list[idx] = dlg.result
                self.populate_team_and_eq(self.current_profile_data['metadata'].get('scouting_team', []), eq_list)
                self.eq_tree.selection_set(f"eq_{idx}")
                self.on_eq_select()

    def delete_equipment(self):
        sel = self.eq_tree.selection()
        if not sel:
            messagebox.showinfo("Select Item", "Please select an equipment item to delete.", parent=self)
            return
        idx = int(sel[0].replace('eq_', ''))
        eq_list = self.current_profile_data.setdefault('metadata', {}).setdefault('scouting_equipment', [])
        if 0 <= idx < len(eq_list):
            item_name = eq_list[idx].get('item', 'Item')
            if messagebox.askyesno("Confirm Delete", f"Remove '{item_name}' from Equipment Roster?", parent=self):
                eq_list.pop(idx)
                self.populate_team_and_eq(self.current_profile_data['metadata'].get('scouting_team', []), eq_list)
                self.eq_item_var.set("")
                self.eq_type_var.set("")
                self.eq_qty_var.set("")
                self.eq_fleet_var.set("")

    def reset_equipment_defaults(self):
        if messagebox.askyesno("Reset Equipment", "Reset Equipment Roster to default ARGAS S-86 items?", parent=self):
            default_eq = DEFAULT_PRELIMINARY_PROFILE.get('metadata', {}).get('scouting_equipment', [])
            self.current_profile_data.setdefault('metadata', {})['scouting_equipment'] = copy.deepcopy(default_eq)
            self.populate_team_and_eq(self.current_profile_data['metadata'].get('scouting_team', []), self.current_profile_data['metadata']['scouting_equipment'])
            self.eq_item_var.set("")
            self.eq_type_var.set("")
            self.eq_qty_var.set("")
            self.eq_fleet_var.set("")

    # --------------------------------------------------------------------------
    # TAB 3: PROSPECT BOUNDARY COORDINATES (TABLE 5)
    # --------------------------------------------------------------------------
    def build_tab_boundary(self):
        top_bar = ttk.LabelFrame(self.tab_boundary, text=" Boundary Coordinate Ingestion (Single or Multi-Block) ", style="Section.TLabelframe", padding=10)
        top_bar.pack(fill="x", pady=(0, 8))

        row = ttk.Frame(top_bar)
        row.pack(fill="x", pady=(0, 6))
        ttk.Label(row, text="Boundary Coordinates CSV/TXT:").pack(side="left", padx=(0, 6))
        self.coord_file_var = tk.StringVar(value="")
        ttk.Entry(row, textvariable=self.coord_file_var).pack(side="left", fill="x", expand=True, padx=(0, 4))
        ttk.Button(row, text="Browse...", command=self.browse_coord_file).pack(side="left", padx=(0, 4))
        ttk.Button(row, text="Sample CSV Template", command=self.generate_sample_boundary_csv).pack(side="left", padx=(0, 4))
        ttk.Button(row, text="▶ Parse & Calculate Geometry", style="Accent.TButton", command=self.parse_boundary_coordinates).pack(side="right")

        # Stats banner
        self.boundary_summary_var = tk.StringVar(value="Load coordinate file to compute perimeters and areas for Table 5.")
        ttk.Label(self.tab_boundary, textvariable=self.boundary_summary_var, font=("Segoe UI", 10, "bold"), foreground="#38BDF8").pack(anchor="w", pady=(0, 6))

        # Points Table View
        cols = ("Block", "PointID", "Easting", "Northing", "Latitude", "Longitude", "Notes")
        self.coord_tree = ttk.Treeview(self.tab_boundary, columns=cols, show="headings", height=14)
        for c in cols:
            self.coord_tree.heading(c, text=c)
        self.coord_tree.column("Block", width=100, anchor="center")
        self.coord_tree.column("PointID", width=80, anchor="center")
        self.coord_tree.column("Easting", width=120, anchor="e")
        self.coord_tree.column("Northing", width=120, anchor="e")
        self.coord_tree.column("Latitude", width=110, anchor="center")
        self.coord_tree.column("Longitude", width=110, anchor="center")
        self.coord_tree.column("Notes", width=220, anchor="w")

        sb = ttk.Scrollbar(self.tab_boundary, orient="vertical", command=self.coord_tree.yview)
        self.coord_tree.configure(yscrollcommand=sb.set)
        self.coord_tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

    def browse_coord_file(self):
        f = filedialog.askopenfilename(
            title="Select Prospect Boundary Coordinates CSV",
            filetypes=[("Coordinate CSV/TXT", "*.csv;*.txt;*.tsv"), ("All Files", "*.*")]
        )
        if f:
            self.coord_file_var.set(os.path.normpath(f))
            self.parse_boundary_coordinates()

    def generate_sample_boundary_csv(self):
        target = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sample_prospect_boundaries.csv")
        self.boundary_mgr.generate_sample_csv(target)
        self.coord_file_var.set(target)
        messagebox.showinfo("Sample Template Created", f"Sample multi-block boundary coordinate CSV generated at:\n{target}", parent=self)
        self.parse_boundary_coordinates()

    def parse_boundary_coordinates(self):
        path = self.coord_file_var.get().strip()
        if not path or not os.path.exists(path):
            messagebox.showwarning("File Missing", "Please select a valid boundary coordinate CSV file.", parent=self)
            return

        ok, msg = self.boundary_mgr.parse_coordinate_file(path)
        if not ok:
            messagebox.showerror("Parsing Error", msg, parent=self)
            return

        self.coord_tree.delete(*self.coord_tree.get_children())
        for p in self.boundary_mgr.raw_points:
            lat_str = f"{p.latitude:.6f}°" if p.latitude is not None else "-"
            lon_str = f"{p.longitude:.6f}°" if p.longitude is not None else "-"
            self.coord_tree.insert("", "end", values=(
                p.block_name, p.point_id, f"{p.easting:,.2f}", f"{p.northing:,.2f}", lat_str, lon_str, p.notes
            ))

        summ = f"Total Blocks: {len(self.boundary_mgr.blocks)} | Total Points: {len(self.boundary_mgr.raw_points)} | Total Acquisition Area: {self.boundary_mgr.total_acquisition_area_sqkm:,.2f} km²"
        self.boundary_summary_var.set(summ)

    # --------------------------------------------------------------------------
    # TAB 4: FIELD TRACKS & DIGITAL NOTES
    # --------------------------------------------------------------------------
    def build_tab_tracks(self):
        box1 = ttk.LabelFrame(self.tab_tracks, text=" Scouted GPS Track Download (*.gpx, *.kml) ", style="Section.TLabelframe", padding=10)
        box1.pack(fill="x", pady=(0, 8))

        r1 = ttk.Frame(box1)
        r1.pack(fill="x", pady=(0, 6))
        ttk.Label(r1, text="Track File:").pack(side="left", padx=(0, 6))
        self.track_file_var = tk.StringVar(value="")
        ttk.Entry(r1, textvariable=self.track_file_var).pack(side="left", fill="x", expand=True, padx=(0, 4))
        ttk.Button(r1, text="Browse...", command=self.browse_track_file).pack(side="left", padx=(0, 4))
        ttk.Button(r1, text="Analyze Track", style="Accent.TButton", command=self.analyze_track_file).pack(side="right")

        self.track_info_var = tk.StringVar(value="Select a GPX or KML track file to calculate total scouted distance and operational dates.")
        ttk.Label(box1, textvariable=self.track_info_var, foreground="#38BDF8", font=("Segoe UI", 9, "italic")).pack(anchor="w")

        # Digital Field Notes (CSV/GPX/QField)
        box2 = ttk.LabelFrame(self.tab_tracks, text=" Digital Field Notes (CSV / GPX / QField Package) ", style="Section.TLabelframe", padding=10)
        box2.pack(fill="both", expand=True)

        r2 = ttk.Frame(box2)
        r2.pack(fill="x", pady=(0, 6))
        ttk.Label(r2, text="Field Notes File:").pack(side="left", padx=(0, 6))
        self.notes_file_var = tk.StringVar(value="")
        ttk.Entry(r2, textvariable=self.notes_file_var).pack(side="left", fill="x", expand=True, padx=(0, 4))
        ttk.Button(r2, text="Browse...", command=self.browse_notes_file).pack(side="right")

        cols = ("ID", "Latitude", "Longitude", "Note")
        self.notes_tree = ttk.Treeview(box2, columns=cols, show="headings", height=10)
        for c in cols:
            self.notes_tree.heading(c, text=c)
        self.notes_tree.column("ID", width=80, anchor="center")
        self.notes_tree.column("Latitude", width=95, anchor="center")
        self.notes_tree.column("Longitude", width=95, anchor="center")
        self.notes_tree.column("Note", width=520, anchor="w")
        self.notes_tree.pack(side="left", fill="both", expand=True)

        sb = ttk.Scrollbar(box2, orient="vertical", command=self.notes_tree.yview)
        self.notes_tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")

    def browse_track_file(self):
        f = filedialog.askopenfilename(
            title="Select Scouted GPS Track File",
            filetypes=[("GPS Tracks", "*.gpx;*.kml;*.kmz"), ("All Files", "*.*")]
        )
        if f:
            self.track_file_var.set(os.path.normpath(f))
            self.analyze_track_file()

    def analyze_track_file(self):
        p = self.track_file_var.get().strip()
        if not p or not os.path.exists(p):
            return
        res = GpxTrackAnalyzer.parse_track_file(p)
        if 'error' in res:
            messagebox.showerror("Track Error", res['error'], parent=self)
            return

        msg = f"Track Format: {res.get('format')} | Total Distance Scouted: {res.get('total_distance_km', 0):,.1f} km | GPS Fixes: {res.get('point_count'):,}"
        if res.get('unique_dates'):
            msg += f" | Scouting Dates: {res['unique_dates'][0]} to {res['unique_dates'][-1]} ({res['scouting_days_count']} days)"
            # Update operational dates
            self.scout_dates_var.set(f"{res['unique_dates'][0]} to {res['unique_dates'][-1]} ({res['scouting_days_count']} Operational Days)")
            self.travel_date_var.set(res['unique_dates'][0])
        self.track_info_var.set(msg)

    def auto_scan_gpx_dates(self):
        p = self.track_file_var.get().strip()
        if not p or not os.path.exists(p):
            self.browse_track_file()
        else:
            self.analyze_track_file()

    def browse_notes_file(self):
        f = filedialog.askopenfilename(
            title="Select Digital Field Notes File",
            filetypes=[
                ("Field Notes & Waypoint Files", "*.shp;*.csv;*.gpx;*.kml;*.qfield;*.gpkg;*.geojson"),
                ("Shapefiles (*.shp)", "*.shp"),
                ("CSV Spreadsheets (*.csv)", "*.csv"),
                ("GPX / KML GPS Data", "*.gpx;*.kml"),
                ("All Files", "*.*")
            ]
        )
        if f:
            self.notes_file_var.set(os.path.normpath(f))
            self.load_notes_tree(f)

    def load_notes_tree(self, path):
        self.notes_tree.delete(*self.notes_tree.get_children())
        if not getattr(self, 'loaded_field_notes', None):
            self.loaded_field_notes = []
        else:
            self.loaded_field_notes.clear()

        ext = os.path.splitext(path)[1].lower()
        if ext == '.csv':
            try:
                with open(path, 'r', encoding='utf-8-sig', errors='replace') as f:
                    reader = csv.DictReader(f)
                    for r in reader:
                        w_id = r.get('Name') or r.get('ID') or r.get('Waypoint') or r.get('Waypoint_N') or ''
                        w_lat = r.get('Latitude') or r.get('Lat') or r.get('Latitude_Y') or ''
                        w_lon = r.get('Longitude') or r.get('Lon') or r.get('Longitude_') or ''
                        w_note = r.get('Note') or r.get('Remarks') or r.get('Description') or r.get('Scouting_N') or ''
                        self.notes_tree.insert("", "end", values=(w_id, w_lat, w_lon, w_note))
                        try:
                            self.loaded_field_notes.append({
                                'id': str(w_id), 'lat': float(w_lat), 'lon': float(w_lon), 'note': str(w_note).strip()
                            })
                        except Exception:
                            pass
            except Exception as e:
                print(f"Warning: Failed to load CSV notes: {e}")

        elif ext == '.shp' and shapefile:
            self._load_notes_from_shp(path)
            for item in self.loaded_field_notes:
                self.notes_tree.insert("", "end", values=(
                    item.get('id', ''),
                    f"{item.get('lat', 0):.6f}" if item.get('lat') is not None else "-",
                    f"{item.get('lon', 0):.6f}" if item.get('lon') is not None else "-",
                    item.get('note', '')
                ))

        elif ext == '.gpx':
            try:
                tree = ET.parse(path)
                root = tree.getroot()
                ns = root.tag.split('}')[0] + '}' if root.tag.startswith('{') else ''
                for wpt in root.iter(f"{ns}wpt"):
                    w_lat = float(wpt.attrib.get('lat', 0.0))
                    w_lon = float(wpt.attrib.get('lon', 0.0))
                    name_elem = wpt.find(f"{ns}name")
                    desc_elem = wpt.find(f"{ns}desc") or wpt.find(f"{ns}cmt")
                    w_id = name_elem.text.strip() if name_elem is not None and name_elem.text else ""
                    w_note = desc_elem.text.strip() if desc_elem is not None and desc_elem.text else ""
                    if w_note:
                        self.notes_tree.insert("", "end", values=(w_id, f"{w_lat:.6f}", f"{w_lon:.6f}", w_note))
                        self.loaded_field_notes.append({
                            'id': w_id, 'lat': w_lat, 'lon': w_lon, 'note': w_note
                        })
            except Exception as e:
                print(f"Warning: Failed to load GPX waypoints: {e}")

    def _load_notes_from_shp(self, shp_path: str):
        """Extracts waypoint coordinates and notes from shapefiles like Scouting_Notes_Waypoints.shp."""
        if not shapefile or not os.path.exists(shp_path):
            return
        try:
            sf = shapefile.Reader(shp_path)
            field_names = [f[0].lower() for f in sf.fields[1:]]

            note_idx = None
            for cand in ['scouting_n', 'scouting', 'note', 'notes', 'desc', 'description', 'remarks', 'comment', 'comments']:
                if cand in field_names:
                    note_idx = field_names.index(cand)
                    break

            lat_idx = None
            for cand in ['latitude_y', 'latitude', 'lat', 'y']:
                if cand in field_names:
                    lat_idx = field_names.index(cand)
                    break

            lon_idx = None
            for cand in ['longitude_', 'longitude', 'lon', 'x']:
                if cand in field_names:
                    lon_idx = field_names.index(cand)
                    break

            wp_idx = None
            for cand in ['waypoint_n', 'waypoint', 'name', 'id']:
                if cand in field_names:
                    wp_idx = field_names.index(cand)
                    break

            for s, r in zip(sf.shapes(), sf.records()):
                w_note = str(r[note_idx]).strip() if (note_idx is not None and note_idx < len(r)) else ""
                w_id = str(r[wp_idx]).strip() if (wp_idx is not None and wp_idx < len(r)) else ""
                w_lat, w_lon = None, None

                if lat_idx is not None and lon_idx is not None:
                    try:
                        w_lat = float(r[lat_idx])
                        w_lon = float(r[lon_idx])
                    except Exception:
                        pass

                if (w_lat is None or w_lon is None) and s.points:
                    pt = s.points[0]
                    # Check if coordinates are in degrees vs UTM meters
                    if -180.0 <= pt[0] <= 180.0 and -90.0 <= pt[1] <= 90.0:
                        w_lon, w_lat = pt[0], pt[1]

                if w_note and w_note.lower() != 'none':
                    self.loaded_field_notes.append({
                        'id': w_id, 'lat': w_lat, 'lon': w_lon, 'note': w_note
                    })
        except Exception as e:
            print(f"Warning: Failed to load waypoint notes from {shp_path}: {e}")

    def _ensure_field_notes_loaded(self):
        """Automatically discovers and loads field waypoint notes if not already populated."""
        if getattr(self, 'loaded_field_notes', None):
            return
        self.loaded_field_notes = []

        # 1. Check notes_tree in Tab 4 if already populated
        if hasattr(self, 'notes_tree'):
            for item in self.notes_tree.get_children():
                vals = self.notes_tree.item(item, 'values')
                if len(vals) >= 4:
                    try:
                        w_id, w_lat, w_lon, w_note = vals[0], float(vals[1]), float(vals[2]), str(vals[3])
                        if w_note.strip():
                            self.loaded_field_notes.append({
                                'id': str(w_id), 'lat': w_lat, 'lon': w_lon, 'note': w_note.strip()
                            })
                    except Exception:
                        pass

        if self.loaded_field_notes:
            return

        # 2. Look for Scouting_Notes_Waypoints.shp on disk automatically
        candidate_shps = [
            r"D:\S86 Argas\Amzan South Scouting\Amzan Scouting Notes Shp\Scouting_Notes_Waypoints.shp",
            r"D:\S86 Argas\Amzan South Scouting\Downloads\Scouting_Notes_Waypoints.shp",
        ]
        for c_shp in candidate_shps:
            if os.path.exists(c_shp):
                self._load_notes_from_shp(c_shp)
                if self.loaded_field_notes:
                    if hasattr(self, 'notes_file_var'):
                        self.notes_file_var.set(os.path.normpath(c_shp))
                    if hasattr(self, 'notes_tree'):
                        for item in self.loaded_field_notes:
                            self.notes_tree.insert("", "end", values=(
                                item.get('id', ''),
                                f"{item.get('lat', 0):.6f}" if item.get('lat') is not None else "-",
                                f"{item.get('lon', 0):.6f}" if item.get('lon') is not None else "-",
                                item.get('note', '')
                            ))
                    break

    def find_nearest_field_note(self, lat: float, lon: float, max_dist_m: float = 350.0) -> str:
        """Finds closest field waypoint note within max_dist_m meters using Haversine distance."""
        if not getattr(self, 'loaded_field_notes', None):
            return ""
        best_note = ""
        best_dist = float('inf')
        best_id = ""

        for item in self.loaded_field_notes:
            w_lat = item.get('lat')
            w_lon = item.get('lon')
            if w_lat is not None and w_lon is not None:
                d = haversine_dist_m(lat, lon, w_lat, w_lon)
                if d <= max_dist_m and d < best_dist:
                    best_dist = d
                    best_note = item.get('note', '')
                    best_id = item.get('id', '')

        if best_note:
            pfx = f"Waypoint {best_id}: " if best_id else ""
            return f"{pfx}{best_note} (Field Obs at ~{best_dist:.0f}m)"
        return ""

    # --------------------------------------------------------------------------
    # TAB 5: DYNAMIC MAP FIGURES SELECTION MATRIX (OPTIONAL + CUSTOM)
    # --------------------------------------------------------------------------
    def build_tab_maps(self):
        top_bar = ttk.Frame(self.tab_maps)
        top_bar.pack(fill="x", pady=(0, 6))
        ttk.Label(top_bar, text="Report Map Figures (All Optional — Core Maps 1, 2, 3, 4, 5, 6, 8, 9 & Custom)",
                  font=("Segoe UI", 11, "bold"), foreground="#38BDF8").pack(side="left")
        ttk.Button(top_bar, text="+ Add Custom Map Figure", style="Accent.TButton", command=self.add_custom_map_dialog).pack(side="right")

        # Scrollable container for maps
        canvas = tk.Canvas(self.tab_maps, bg="#0A0F1D", highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.tab_maps, orient="vertical", command=canvas.yview)
        self.scrollable_maps_frame = ttk.Frame(canvas)

        self.scrollable_maps_frame.bind(
            "<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=self.scrollable_maps_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.map_ui_rows: Dict[str, Dict] = {}
        self.refresh_maps_ui()

    def refresh_maps_ui(self):
        for widget in self.scrollable_maps_frame.winfo_children():
            widget.destroy()
        self.map_ui_rows.clear()

        # Render Core Standard Maps First
        std_keys = ['map_1', 'map_2', 'map_3', 'map_4', 'map_5', 'map_6', 'map_8', 'map_9']
        for k in std_keys:
            if k in self.maps_mgr.maps:
                self._render_map_row(self.maps_mgr.maps[k])

        # Render Custom Maps
        customs = [m for m in self.maps_mgr.maps.values() if m.is_custom]
        if customs:
            sep = ttk.Separator(self.scrollable_maps_frame, orient="horizontal")
            sep.pack(fill="x", pady=10)
            ttk.Label(self.scrollable_maps_frame, text="User-Added Custom Maps:", font=("Segoe UI", 10, "bold"), foreground="#F59E0B").pack(anchor="w", padx=6, pady=(0, 6))
            for m in customs:
                self._render_map_row(m)

    def _render_map_row(self, m: MapFigureConfig):
        row_box = ttk.LabelFrame(self.scrollable_maps_frame, text=f" {m.title} ", style="Section.TLabelframe", padding=6)
        row_box.pack(fill="x", padx=6, pady=4, expand=True)

        ctrl_row = ttk.Frame(row_box)
        ctrl_row.pack(fill="x")

        chk_var = tk.BooleanVar(value=m.enabled)
        chk = ttk.Checkbutton(ctrl_row, text="Include in Report", variable=chk_var)
        chk.pack(side="left", padx=(0, 8))

        f_var = tk.StringVar(value=m.file_path)
        ent = ttk.Entry(ctrl_row, textvariable=f_var)
        ent.pack(side="left", fill="x", expand=True, padx=(0, 4))

        def on_browse(key=m.key, var=f_var):
            f = filedialog.askopenfilename(
                title=f"Select Map Image for {self.maps_mgr.maps[key].title}",
                filetypes=[("Image Files", "*.png;*.jpg;*.jpeg;*.tif;*.tiff;*.bmp"), ("All Files", "*.*")]
            )
            if f:
                f_norm = os.path.normpath(f)
                var.set(f_norm)
                self.maps_mgr.maps[key].file_path = f_norm

        ttk.Button(ctrl_row, text="Browse...", command=on_browse).pack(side="left", padx=(0, 4))

        def on_edit(key=m.key):
            dlg = CustomMapDialog(self, self.maps_mgr.maps[key], self.ai, self.prospect_name_var.get())
            self.wait_window(dlg)
            if dlg.result:
                self.maps_mgr.maps[key] = dlg.result
                self.refresh_maps_ui()

        ttk.Button(ctrl_row, text="Edit Description / Section", command=on_edit).pack(side="left", padx=(0, 4))

        if m.is_custom:
            def on_del(key=m.key):
                if messagebox.askyesno("Confirm Delete", f"Remove custom map '{self.maps_mgr.maps[key].title}'?", parent=self):
                    self.maps_mgr.remove_map(key)
                    self.refresh_maps_ui()
            ttk.Button(ctrl_row, text="✕ Remove", command=on_del).pack(side="left")

        # Description preview
        if m.description:
            d_prev = ttk.Label(row_box, text=f"Description: {m.description[:110]}...", foreground="#94A3B8", font=("Segoe UI", 8, "italic"))
            d_prev.pack(anchor="w", pady=(2, 0))

        self.map_ui_rows[m.key] = {'enabled_var': chk_var, 'file_var': f_var}

    def add_custom_map_dialog(self):
        dlg = CustomMapDialog(self, None, self.ai, self.prospect_name_var.get())
        self.wait_window(dlg)
        if dlg.result:
            self.maps_mgr.add_custom_map(
                title=dlg.result.title,
                file_path=dlg.result.file_path,
                target_section=dlg.result.target_section,
                description=dlg.result.description
            )
            self.refresh_maps_ui()

    # --------------------------------------------------------------------------
    # TAB 6: TERRAIN GIS & MAP (SECTION 6)
    # --------------------------------------------------------------------------
    def build_tab_terrain(self):
        top_box = ttk.LabelFrame(self.tab_terrain, text=" Shapefile Terrain Ingestion & Map Generation (Section 6 & Figure 5) ", style="Section.TLabelframe", padding=10)
        top_box.pack(fill="x", pady=(0, 8))

        r1 = ttk.Frame(top_box)
        r1.pack(fill="x", pady=(0, 6))
        ttk.Label(r1, text="Terrain Polygon Shapefile (*.shp):").pack(side="left", padx=(0, 6))

        # Default to full 324-polygon shapefile Terrain_Cut_SF.shp if present on disk
        default_terrain = r"D:\S86 Argas\Amzan South Scouting\Report\Terrain_Cut_SF.shp"
        if not os.path.exists(default_terrain):
            default_terrain = ""
        self.terrain_shp_var = tk.StringVar(value=default_terrain)
        ttk.Entry(r1, textvariable=self.terrain_shp_var).pack(side="left", fill="x", expand=True, padx=(0, 4))
        ttk.Button(r1, text="Browse...", command=self.browse_terrain_shp).pack(side="left", padx=(0, 4))
        ttk.Button(r1, text="🔍 Auto-Detect Full Shapefile", command=self.autodetect_full_terrain_shp).pack(side="left", padx=(0, 4))
        ttk.Button(r1, text="▶ Run GIS Classification & Generate Maps", style="Accent.TButton", command=self.run_terrain_gis_analysis).pack(side="right")

        self.terrain_status_lbl = ttk.Label(top_box, text="Status: Ready to analyze terrain shapefile.", foreground="#38BDF8", font=("Segoe UI", 9, "italic"))
        self.terrain_status_lbl.pack(anchor="w", pady=(2, 4))

        r_map = ttk.Frame(top_box)
        r_map.pack(fill="x", pady=(4, 0))
        ttk.Label(r_map, text="Figure 5 Map Source:").pack(side="left", padx=(0, 6))
        ttk.Radiobutton(r_map, text="System Generated from Shapefile (300 DPI)", variable=self.terrain_map_mode_var, value="system").pack(side="left", padx=(0, 10))
        ttk.Radiobutton(r_map, text="User-Provided Map Image File", variable=self.terrain_map_mode_var, value="user").pack(side="left", padx=(0, 10))

        r_user_map = ttk.Frame(top_box)
        r_user_map.pack(fill="x", pady=(4, 0))
        ttk.Label(r_user_map, text="User Map Image File:").pack(side="left", padx=(0, 6))
        ttk.Entry(r_user_map, textvariable=self.user_terrain_map_path).pack(side="left", fill="x", expand=True, padx=(0, 4))
        ttk.Button(r_user_map, text="Browse...", command=self.browse_user_terrain_map).pack(side="left", padx=(0, 4))
        ttk.Button(r_user_map, text="🗺 Preview Terrain Map", style="Warning.TButton", command=self.preview_terrain_map).pack(side="right")

        split = ttk.Frame(self.tab_terrain)
        split.pack(fill="both", expand=True)

        # Left: Table of classes
        t_box = ttk.LabelFrame(split, text=" Geomorphic Surface Terrain Classes (Matching Map Colors) ", style="Section.TLabelframe", padding=8)
        t_box.pack(side="left", fill="both", expand=True, padx=(0, 4))

        cols = ("Class", "Area_km2", "Percent", "Trafficability")
        self.terrain_tree = ttk.Treeview(t_box, columns=cols, show="headings", height=12)
        self.terrain_tree.heading("Class", text="Geomorphic Surface Terrain Class")
        self.terrain_tree.heading("Area_km2", text="Area (km²)")
        self.terrain_tree.heading("Percent", text="Percent (%)")
        self.terrain_tree.heading("Trafficability", text="Surface Characteristics & Scouting Trafficability")
        self.terrain_tree.column("Class", width=160, anchor="w")
        self.terrain_tree.column("Area_km2", width=85, anchor="e")
        self.terrain_tree.column("Percent", width=75, anchor="center")
        self.terrain_tree.column("Trafficability", width=340, anchor="w")
        self.terrain_tree.pack(fill="both", expand=True)

        # Right: Pie Chart Preview
        p_box = ttk.LabelFrame(split, text=" 300 DPI Geomorphic Pie Chart Preview ", style="Section.TLabelframe", padding=8)
        p_box.pack(side="right", fill="both", expand=True, padx=(4, 0))

        self.chart_preview_lbl = ttk.Label(p_box, text="Click 'Run GIS Classification' to generate and preview pie chart.")
        self.chart_preview_lbl.pack(fill="both", expand=True)

    def autodetect_full_terrain_shp(self):
        """Finds and loads full 324-polygon prospect shapefile (Terrain_Cut_SF.shp)."""
        candidates = [
            r"D:\S86 Argas\Amzan South Scouting\Report\Terrain_Cut_SF.shp",
            r"D:\S86 Argas\Amzan South Scouting\Terrain_Cut_SF.shp",
        ]
        found = None
        for c in candidates:
            if os.path.exists(c):
                found = c
                break
        if not found and os.path.exists(r"D:\S86 Argas"):
            for root, _, files in os.walk(r"D:\S86 Argas"):
                for f in files:
                    if f.lower() == "terrain_cut_sf.shp":
                        found = os.path.join(root, f)
                        break
                if found:
                    break

        if found:
            self.terrain_shp_var.set(os.path.normpath(found))
            self.run_terrain_gis_analysis()
            messagebox.showinfo("Full Shapefile Loaded",
                                f"Detected and loaded full prospect terrain shapefile with 324 polygons:\n{found}",
                                parent=self)
        else:
            messagebox.showwarning("Shapefile Not Found",
                                   "Could not locate Terrain_Cut_SF.shp automatically. Please use Browse...",
                                   parent=self)

    def browse_terrain_shp(self):
        f = filedialog.askopenfilename(
            title="Select Terrain Polygon Shapefile",
            filetypes=[("Shapefile", "*.shp"), ("All Files", "*.*")]
        )
        if f:
            self.terrain_shp_var.set(os.path.normpath(f))
            self.run_terrain_gis_analysis()

    def browse_user_terrain_map(self):
        f = filedialog.askopenfilename(
            title="Select User-Provided Terrain Map File",
            filetypes=[("Image Files", "*.png;*.jpg;*.jpeg;*.tif;*.tiff;*.bmp"), ("All Files", "*.*")]
        )
        if f:
            self.user_terrain_map_path.set(os.path.normpath(f))
            self.terrain_map_mode_var.set("user")

    def preview_terrain_map(self):
        mode = self.terrain_map_mode_var.get()
        p = self.generated_terrain_map_path if mode == "system" else self.user_terrain_map_path.get().strip()
        if not p or not os.path.exists(p):
            messagebox.showwarning("Map Missing", "No terrain map image generated or selected yet.", parent=self)
            return
        ImageViewerDialog(self, f"Figure 5: Terrain Classification Map ({mode.capitalize()})", p)

    def run_terrain_gis_analysis(self):
        shp = self.terrain_shp_var.get().strip()
        if not shp or not os.path.exists(shp):
            messagebox.showwarning("Shapefile Missing", "Please select a valid terrain shapefile (*.shp).", parent=self)
            return

        res = TerrainChartGenerator.analyze_shapefile(shp)
        if 'error' in res:
            messagebox.showerror("GIS Error", res['error'], parent=self)
            return

        self.terrain_analysis_results = res['terrain_classes']
        self.terrain_tree.delete(*self.terrain_tree.get_children())
        for c in self.terrain_analysis_results:
            self.terrain_tree.insert("", "end", values=(
                c['class_name'], f"{c['area_sqkm']:,.2f}", f"{c['percentage']:.1f}%", c.get('trafficability', '')
            ))

        # Check total shapes count in shapefile to guide user
        shape_count = 0
        if shapefile and os.path.exists(shp):
            try:
                sf = shapefile.Reader(shp)
                shape_count = len(sf.shapes())
            except Exception:
                pass

        total_area = res.get('total_area_sqkm', 0.0)
        classes_count = len(self.terrain_analysis_results)

        if shape_count < 100:
            if hasattr(self, 'terrain_status_lbl'):
                self.terrain_status_lbl.configure(
                    text=f"⚠️ Loaded {shape_count} polygons across {classes_count} classes ({total_area:,.2f} km²). Tip: For full prospect coverage, click 'Auto-Detect Full Shapefile' (Terrain_Cut_SF.shp with 324 polygons).",
                    foreground="#FBBF24"
                )
        else:
            if hasattr(self, 'terrain_status_lbl'):
                self.terrain_status_lbl.configure(
                    text=f"✔ Full Shapefile Loaded: {shape_count} polygons across {classes_count} classes (Total Area: {total_area:,.2f} km²).",
                    foreground="#38BDF8"
                )

        # Resolve output directory (handles both python source and PyInstaller frozen EXE)
        app_dir = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__))

        # Generate Pie Chart image (colors match map)
        out_chart = os.path.join(app_dir, "terrain_pie_chart.png")
        TerrainChartGenerator.generate_pie_chart(self.terrain_analysis_results, out_chart, self.prospect_name_var.get())
        self.generated_pie_chart_path = out_chart

        # Generate 300 DPI Spatial Terrain Map (Figure 5) matching report template layout
        out_map = os.path.join(app_dir, "generated_terrain_map.png")
        try:
            TerrainChartGenerator.generate_terrain_map(
                shp, out_map,
                prospect_name=self.prospect_name_var.get(),
                crew_name=self.crew_name_var.get(),
                author=self.prep_by_var.get(),
                date_str=self.report_date_var.get()
            )
            self.generated_terrain_map_path = out_map
        except Exception as e:
            print(f"Warning: Failed to generate spatial terrain map: {e}")

        # Update preview thumbnail
        try:
            with Image.open(out_chart) as im:
                im.thumbnail((420, 280))
                photo = ImageTk.PhotoImage(im)
                self.chart_preview_lbl.configure(image=photo, text="")
                self.chart_preview_lbl.image = photo
        except Exception:
            self.chart_preview_lbl.configure(text=f"Pie Chart Generated: {out_chart}")

    # --------------------------------------------------------------------------
    # TAB 7: ARAMCO REMOTENESS & AREA TYPES (SECTION 7)
    # --------------------------------------------------------------------------
    def build_tab_aramco(self):
        meta = self.current_profile_data.get('metadata', {})

        top_box = ttk.LabelFrame(self.tab_aramco, text=" Saudi Aramco GDAD Countrywide Operational Areas Ingestion (Section 7 & Table 6) ", style="Section.TLabelframe", padding=10)
        top_box.pack(fill="x", pady=(0, 8))

        r1 = ttk.Frame(top_box)
        r1.pack(fill="x", pady=(0, 6))
        ttk.Label(r1, text="Aramco Operational Area Shapefile (*.shp):").pack(side="left", padx=(0, 6))

        default_aramco = AramcoRemotenessAnalyzer.DEFAULT_ARAMCO_SHP
        if not os.path.exists(default_aramco):
            default_aramco = ""
        self.aramco_shp_var = tk.StringVar(value=default_aramco)
        ttk.Entry(r1, textvariable=self.aramco_shp_var).pack(side="left", fill="x", expand=True, padx=(0, 4))
        ttk.Button(r1, text="Browse...", command=self.browse_aramco_shp).pack(side="left", padx=(0, 4))
        ttk.Button(r1, text="✂ Crop Aramco Features to Prospect & Calculate Statistics", style="Accent.TButton", command=self.run_aramco_analysis).pack(side="right")

        # Map source selection
        r_map = ttk.Frame(top_box)
        r_map.pack(fill="x", pady=(4, 0))
        ttk.Label(r_map, text="Figure 7.1 Map Source:").pack(side="left", padx=(0, 6))
        ttk.Radiobutton(r_map, text="System Generated (Cropped to Prospect, 300 DPI)", variable=self.aramco_map_mode_var, value="system").pack(side="left", padx=(0, 10))
        ttk.Radiobutton(r_map, text="User-Provided Map Image File", variable=self.aramco_map_mode_var, value="user").pack(side="left", padx=(0, 10))

        r_user_map = ttk.Frame(top_box)
        r_user_map.pack(fill="x", pady=(4, 0))
        ttk.Label(r_user_map, text="User Map Image File:").pack(side="left", padx=(0, 6))
        ttk.Entry(r_user_map, textvariable=self.user_aramco_map_path).pack(side="left", fill="x", expand=True, padx=(0, 4))
        ttk.Button(r_user_map, text="Browse...", command=self.browse_user_aramco_map).pack(side="left", padx=(0, 4))
        ttk.Button(r_user_map, text="🗺 Preview Aramco Area Map", style="Warning.TButton", command=self.preview_aramco_map).pack(side="right")

        split = ttk.Frame(self.tab_aramco)
        split.pack(fill="both", expand=True)

        # Left: Table of cropped Aramco Categories
        t_box = ttk.LabelFrame(split, text=" Prospect Cropped Operational Areas (Table 6) ", style="Section.TLabelframe", padding=8)
        t_box.pack(side="left", fill="both", expand=True, padx=(0, 4))

        cols = ("Class", "Name", "Remoteness", "Area_km2", "Percent", "PaymentFactor")
        self.aramco_tree = ttk.Treeview(t_box, columns=cols, show="headings", height=12)
        self.aramco_tree.heading("Class", text="Class")
        self.aramco_tree.heading("Name", text="Aramco Category Name")
        self.aramco_tree.heading("Remoteness", text="Remoteness")
        self.aramco_tree.heading("Area_km2", text="Area (km²)")
        self.aramco_tree.heading("Percent", text="Percent (%)")
        self.aramco_tree.heading("PaymentFactor", text="Payment Complexity & Factor")
        self.aramco_tree.column("Class", width=55, anchor="center")
        self.aramco_tree.column("Name", width=180, anchor="w")
        self.aramco_tree.column("Remoteness", width=80, anchor="center")
        self.aramco_tree.column("Area_km2", width=80, anchor="e")
        self.aramco_tree.column("Percent", width=70, anchor="center")
        self.aramco_tree.column("PaymentFactor", width=240, anchor="w")
        self.aramco_tree.pack(fill="both", expand=True)

        # Right: Notebook with Pie Chart Preview & Remoteness Parameters / Narrative
        r_box = ttk.LabelFrame(split, text=" Section 7 Visuals & Logistics Parameters ", style="Section.TLabelframe", padding=8)
        r_box.pack(side="right", fill="both", expand=True, padx=(4, 0))

        self.aramco_nb = ttk.Notebook(r_box)
        self.aramco_nb.pack(fill="both", expand=True)

        # Sub-tab 1: Pie Chart Preview
        f_chart_tab = ttk.Frame(self.aramco_nb, padding=6)
        self.aramco_nb.add(f_chart_tab, text=" 300 DPI Pie Chart Preview ")

        self.aramco_chart_preview_lbl = ttk.Label(f_chart_tab, text="Click 'Crop Aramco Features' to calculate statistics and preview pie chart.")
        self.aramco_chart_preview_lbl.pack(fill="both", expand=True)

        # Sub-tab 2: Logistics & Narrative
        f_narr_tab = ttk.Frame(self.aramco_nb, padding=6)
        self.aramco_nb.add(f_narr_tab, text=" Logistics & Section 7 Narrative ")

        f_meta = ttk.Frame(f_narr_tab)
        f_meta.pack(fill="x", pady=(0, 6))

        ttk.Label(f_meta, text="Nearest Hub / City:").grid(row=0, column=0, sticky="w", padx=(0, 4), pady=2)
        self.nearest_city_var = tk.StringVar(value=meta.get('nearest_city', 'Abqaiq / Dhahran Supply Hub'))
        ttk.Entry(f_meta, textvariable=self.nearest_city_var, width=24).grid(row=0, column=1, padx=(0, 8), pady=2)

        ttk.Label(f_meta, text="Base Distance (km):").grid(row=0, column=2, sticky="w", padx=(0, 4), pady=2)
        self.base_dist_var = tk.StringVar(value=str(meta.get('base_distance_km', '120')))
        ttk.Entry(f_meta, textvariable=self.base_dist_var, width=8).grid(row=0, column=3, pady=2)

        ttk.Label(f_meta, text="Remoteness Classification:").grid(row=1, column=0, sticky="w", padx=(0, 4), pady=2)
        self.remoteness_zone_var = tk.StringVar(value=meta.get('remoteness_zone', 'Zone R0 (Standard Desert Concession)'))
        z_combo = ttk.Combobox(f_meta, textvariable=self.remoteness_zone_var,
                               values=["Zone R0 (Standard Desert Concession)",
                                       "Zone R1 (Intermediate Desert Concession)",
                                       "Zone R2 (Remote Concession - Mobile Fly Camps)",
                                       "Zone R4 (Deep Rub' al Khali / Extreme Frontier Concession)"],
                               width=34, state="readonly")
        z_combo.grid(row=1, column=1, columnspan=3, sticky="we", pady=2)
        style_combobox_popdown(z_combo)

        ttk.Label(f_narr_tab, text="Live Section 7 Technical Narrative Preview:").pack(anchor="w", pady=(6, 2))
        self.sec7_text = tk.Text(f_narr_tab, bg="#0F172A", fg="#F8FAFC", insertbackground="#38BDF8",
                                 relief="flat", highlightthickness=1, highlightcolor="#38BDF8",
                                 highlightbackground="#334155", font=("Segoe UI", 9), wrap="word")
        self.sec7_text.pack(fill="both", expand=True)

    def browse_aramco_shp(self):
        f = filedialog.askopenfilename(
            title="Select Saudi Aramco Contractual Area Shapefile",
            filetypes=[("Shapefile", "*.shp"), ("All Files", "*.*")]
        )
        if f:
            self.aramco_shp_var.set(os.path.normpath(f))
            self.run_aramco_analysis()

    def browse_user_aramco_map(self):
        f = filedialog.askopenfilename(
            title="Select User-Provided Aramco Contractual Map File",
            filetypes=[("Image Files", "*.png;*.jpg;*.jpeg;*.tif;*.tiff;*.bmp"), ("All Files", "*.*")]
        )
        if f:
            self.user_aramco_map_path.set(os.path.normpath(f))
            self.aramco_map_mode_var.set("user")

    def preview_aramco_map(self):
        mode = self.aramco_map_mode_var.get()
        p = self.generated_aramco_map_path if mode == "system" else self.user_aramco_map_path.get().strip()
        if not p or not os.path.exists(p):
            messagebox.showwarning("Map Missing", "No Aramco contractual map image generated or selected yet.", parent=self)
            return
        ImageViewerDialog(self, f"Figure 7.1: Aramco Contractual Operational Area Map ({mode.capitalize()})", p)

    def run_aramco_analysis(self):
        aramco_shp = self.aramco_shp_var.get().strip()
        if not aramco_shp or not os.path.exists(aramco_shp):
            messagebox.showwarning("Shapefile Missing", f"Saudi Aramco Operational Areas shapefile not found:\n{aramco_shp}\nPlease browse to select the shapefile.", parent=self)
            return

        terrain_shp = self.terrain_shp_var.get().strip()
        if not terrain_shp or not os.path.exists(terrain_shp):
            messagebox.showwarning("Terrain Shapefile Missing", "Please select the prospect's terrain shapefile in Tab 6 first.\nThe terrain boundaries are required to crop the countrywide Aramco dataset to the prospect area.", parent=self)
            return

        app_dir = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__))
        out_cropped_shp = os.path.join(app_dir, "aramco_cropped_prospect.shp")
        res = AramcoRemotenessAnalyzer.crop_and_analyze_aramco_areas(aramco_shp, terrain_shp, out_cropped_shp)
        if 'error' in res:
            messagebox.showerror("Aramco GIS Error", res['error'], parent=self)
            return

        self.aramco_contractual_results = res['contractual_types']
        self.aramco_tree.delete(*self.aramco_tree.get_children())
        for c in self.aramco_contractual_results:
            self.aramco_tree.insert("", "end", values=(
                c['class_code'], c['name'], c['remoteness'], f"{c['area_sqkm']:,.2f}", f"{c['percentage']:.1f}%", c['payment_factor']
            ))

        # Generate 300 DPI Aramco Pie Chart
        out_chart = os.path.join(app_dir, "aramco_pie_chart.png")
        try:
            AramcoRemotenessAnalyzer.generate_aramco_pie_chart(self.aramco_contractual_results, out_chart, self.prospect_name_var.get())
            self.generated_aramco_pie_chart_path = out_chart
            with Image.open(out_chart) as im:
                im.thumbnail((420, 280))
                photo = ImageTk.PhotoImage(im)
                self.aramco_chart_preview_lbl.configure(image=photo, text="")
                self.aramco_chart_preview_lbl.image = photo
        except Exception as e:
            print(f"Warning: Failed to generate Aramco pie chart: {e}")

        # Generate live narrative
        meta = {
            'prospect_name': self.prospect_name_var.get(),
            'nearest_city': self.nearest_city_var.get(),
            'base_distance_km': self.base_dist_var.get(),
            'remoteness_zone': self.remoteness_zone_var.get()
        }
        narrative = AramcoRemotenessAnalyzer.generate_section7_narrative(meta, self.aramco_contractual_results, res['total_area_sqkm'])
        self.sec7_text.delete("1.0", "end")
        self.sec7_text.insert("1.0", narrative)

        # Generate 300 DPI Spatial Aramco Map (Figure 7.1)
        out_map = os.path.join(app_dir, "generated_aramco_map.png")
        try:
            AramcoRemotenessAnalyzer.generate_aramco_map(aramco_shp, terrain_shp, out_map, self.prospect_name_var.get())
            self.generated_aramco_map_path = out_map
        except Exception as e:
            print(f"Warning: Failed to generate spatial Aramco map: {e}")



    # --------------------------------------------------------------------------
    # TAB 7: PHOTOS & VISION AI
    # --------------------------------------------------------------------------
    def build_tab_photos(self):
        p_top = ttk.LabelFrame(self.tab_photos, text=" Photo Source & Selection Settings ", style="Section.TLabelframe", padding=10)
        p_top.pack(fill="x", pady=(0, 8))

        r1 = ttk.Frame(p_top)
        r1.pack(fill="x", pady=(0, 6))
        ttk.Label(r1, text="Photos Folder:").pack(side="left", padx=(0, 6))
        self.photo_dir_var = tk.StringVar(value="")
        ttk.Entry(r1, textvariable=self.photo_dir_var).pack(side="left", fill="x", expand=True, padx=(0, 4))
        ttk.Button(r1, text="Browse...", command=self.browse_photo_dir).pack(side="left", padx=(0, 4))
        ttk.Button(r1, text="▶ Curate & Generate Captions", style="Accent.TButton", command=self.run_photo_curation).pack(side="right")

        r2 = ttk.Frame(p_top)
        r2.pack(fill="x", pady=(0, 6))
        ttk.Label(r2, text="Target Photo Count:").pack(side="left", padx=(0, 6))
        self.photo_count_var = tk.IntVar(value=60)
        sp = ttk.Spinbox(r2, from_=10, to=200, textvariable=self.photo_count_var, width=6, style="TSpinbox")
        sp.pack(side="left", padx=(0, 16))

        self.apply_haze_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(r2, text="Dehazing & Clarity", variable=self.apply_haze_var).pack(side="left", padx=(0, 10))
        self.apply_sharp_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(r2, text="Unsharp Mask", variable=self.apply_sharp_var).pack(side="left", padx=(0, 10))
        self.apply_color_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(r2, text="Vivid Color", variable=self.apply_color_var).pack(side="left")

        # Top option for non-geotagged photos inclusion
        r3 = ttk.Frame(p_top)
        r3.pack(fill="x")
        self.include_non_geotagged_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            r3,
            text="Include Non-Geotagged Photos in Report (Appended at end of Section 13 Photo Plates)",
            variable=self.include_non_geotagged_var
        ).pack(side="left")

        grid_frame = ttk.Frame(self.tab_photos)
        grid_frame.pack(fill="both", expand=True)

        cols = ("No", "Filename", "Geotag", "Category", "Confidence", "Status", "Note", "Caption")
        self.photo_tree = ttk.Treeview(grid_frame, columns=cols, show="headings", height=12)
        self.photo_tree.heading("No", text="#")
        self.photo_tree.heading("Filename", text="Image Filename")
        self.photo_tree.heading("Geotag", text="GPS Status")
        self.photo_tree.heading("Category", text="Terrain Category")
        self.photo_tree.heading("Confidence", text="Confidence")
        self.photo_tree.heading("Status", text="Report Status")
        self.photo_tree.heading("Note", text="Field Photo Note / Description")
        self.photo_tree.heading("Caption", text="AI Descriptive Caption (Plate Text)")

        self.photo_tree.column("No", width=35, anchor="center")
        self.photo_tree.column("Filename", width=130, anchor="w")
        self.photo_tree.column("Geotag", width=105, anchor="center")
        self.photo_tree.column("Category", width=115, anchor="w")
        self.photo_tree.column("Confidence", width=70, anchor="center")
        self.photo_tree.column("Status", width=90, anchor="center")
        self.photo_tree.column("Note", width=220, anchor="w")
        self.photo_tree.column("Caption", width=380, anchor="w")

        # Visual highlights: Yellow/amber for missing GPS, gray for rejected
        self.photo_tree.tag_configure("tag_ok", foreground="#F8FAFC")
        self.photo_tree.tag_configure("tag_nogps", foreground="#FBBF24")
        self.photo_tree.tag_configure("tag_rejected", foreground="#94A3B8")

        sb = ttk.Scrollbar(grid_frame, orient="vertical", command=self.photo_tree.yview)
        self.photo_tree.configure(yscrollcommand=sb.set)
        self.photo_tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.photo_tree.bind("<Double-1>", self.open_photo_review_modal)

        # Review & Edit button bar
        p_bar = ttk.Frame(self.tab_photos)
        p_bar.pack(fill="x", pady=(6, 0))
        ttk.Button(p_bar, text="🗺 Review Photos & Interactive GIS Map Inspector", style="Warning.TButton", command=self.open_photo_review_modal).pack(side="left", padx=(0, 6))
        ttk.Button(p_bar, text="📝 Check Notes & Re-Analyze with AI", style="Accent.TButton", command=self.check_notes_and_reanalyze_all).pack(side="left", padx=(0, 6))
        ttk.Button(p_bar, text="🚫 Exclude Selected Photo", command=self.exclude_selected_photo).pack(side="left", padx=(0, 6))
        ttk.Button(p_bar, text="🔄 Restore Selected Photo", command=self.restore_selected_photo).pack(side="left", padx=(0, 6))

    def refresh_photo_tree(self):
        self.photo_tree.delete(*self.photo_tree.get_children())
        for idx, item in enumerate(self.curated_photos_list, start=1):
            item['no'] = idx
            has_gps = item.get('has_gps', False)
            geo_txt = "✔ Geotagged" if has_gps else "✖ NO GPS"
            is_rej = item.get('is_rejected', False)
            status_txt = "Excluded" if is_rej else "Included"
            note_txt = item.get('note', '')

            tag = "tag_rejected" if is_rej else ("tag_ok" if has_gps else "tag_nogps")

            self.photo_tree.insert("", "end", iid=str(idx - 1), values=(
                idx, item.get('filename', ''), geo_txt, item.get('category', ''),
                item.get('confidence', ''), status_txt, note_txt, item.get('caption', '')
            ), tags=(tag,))

    def exclude_selected_photo(self):
        sel = self.photo_tree.selection()
        if not sel:
            messagebox.showinfo("Select Photo", "Please select a photo row to exclude from report.", parent=self)
            return
        for item_id in sel:
            try:
                idx = int(item_id)
                if 0 <= idx < len(self.curated_photos_list):
                    self.curated_photos_list[idx]['is_rejected'] = True
            except Exception:
                pass
        self.refresh_photo_tree()

    def restore_selected_photo(self):
        sel = self.photo_tree.selection()
        if not sel:
            messagebox.showinfo("Select Photo", "Please select a photo row to restore to report.", parent=self)
            return
        for item_id in sel:
            try:
                idx = int(item_id)
                if 0 <= idx < len(self.curated_photos_list):
                    self.curated_photos_list[idx]['is_rejected'] = False
            except Exception:
                pass
        self.refresh_photo_tree()

    def open_photo_review_modal(self, event=None):
        if not self.curated_photos_list:
            messagebox.showinfo("No Photos", "Please run 'Curate & Generate Captions' first to populate the photo list.", parent=self)
            return

        # Determine selected photo index from photo tree if any
        selected_idx = 0
        sel = self.photo_tree.selection()
        if sel:
            try:
                item_vals = self.photo_tree.item(sel[0]).get('values', [])
                if item_vals:
                    selected_idx = max(0, int(item_vals[0]) - 1)
            except Exception:
                selected_idx = 0

        track_f = self.track_file_var.get().strip() if hasattr(self, 'track_file_var') else ""
        terrain_shp = self.terrain_shp_var.get().strip() if hasattr(self, 'terrain_shp_var') else ""
        wps = getattr(self, 'loaded_field_notes', [])
        b_mgr = getattr(self, 'boundary_mgr', None)

        prospect_name = self.prospect_name_var.get().strip() or "Default"
        dlg = PhotoReviewDialog(
            parent=self,
            photo_list=self.curated_photos_list,
            ai_assistant=self.ai,
            track_file=track_f,
            waypoints=wps,
            terrain_shp=terrain_shp,
            boundary_mgr=b_mgr,
            initial_idx=selected_idx,
            project_name=prospect_name
        )
        self.wait_window(dlg)
        self.refresh_photo_tree()

    def browse_photo_dir(self):
        d = filedialog.askdirectory(title="Select Scouting Photos Directory")
        if d:
            self.photo_dir_var.set(os.path.normpath(d))

    def run_photo_curation(self):
        try:
            p_dir = self.photo_dir_var.get().strip()
            if not p_dir or not os.path.exists(p_dir):
                messagebox.showwarning("Missing Folder", "Please select a valid photos directory.", parent=self)
                return

            self.curated_photos_list.clear()
            self.photo_tree.delete(*self.photo_tree.get_children())

            # Scan folder for photos
            all_imgs = []
            for root, _, files in os.walk(p_dir):
                for f in sorted(files):
                    if f.lower().endswith(('.jpg', '.jpeg', '.png')):
                        all_imgs.append(os.path.join(root, f))

            if not all_imgs:
                messagebox.showinfo("No Images", "No JPG or PNG images found in directory.", parent=self)
                return

            # Ensure field notes are loaded if available
            self._ensure_field_notes_loaded()

            # Target count safe parsing
            try:
                target_count = int(self.photo_count_var.get())
            except Exception:
                target_count = 60
            target_count = max(1, min(target_count, len(all_imgs)))

            step = max(1, len(all_imgs) // target_count)
            selected = all_imgs[::step][:target_count]

            for idx, img_p in enumerate(selected, start=1):
                fname = os.path.basename(img_p)
                # Correctly unpack 5 elements from extract_exif!
                dt, lat, lon, direction, note = extract_exif(img_p)
                has_gps = (lat is not None and lon is not None)
                dt_str = dt.strftime("%Y-%m-%d %H:%M:%S") if dt else "N/A"

                # If no note in EXIF, correlate with nearest GPS waypoint
                if not note and has_gps:
                    wp_note = self.find_nearest_field_note(lat, lon, max_dist_m=350)
                    if wp_note:
                        note = wp_note

                # Call AI assistant with the photo and the note
                cap, conf = self.ai.generate_photo_caption(img_p, photo_note=note)

                cat = "General Field Condition"
                lower_text = f"{fname} {note}".lower()
                for c_name, kw_list in TARGET_CATEGORIES:
                    if any(kw in lower_text for kw in kw_list):
                        cat = c_name
                        break

                item = {
                    'no': idx,
                    'file_path': img_p,
                    'filename': fname,
                    'category': cat,
                    'confidence': f"{conf * 100:.0f}%",
                    'caption': cap,
                    'note': note,
                    'has_gps': has_gps,
                    'lat': lat,
                    'lon': lon,
                    'direction': direction,
                    'datetime': dt_str,
                    'is_rejected': False
                }
                self.curated_photos_list.append(item)

            self.refresh_photo_tree()
            messagebox.showinfo("Curation Complete",
                                f"Successfully curated {len(self.curated_photos_list)} field photos with AI vision captions and ground notes.",
                                parent=self)
        except Exception as e:
            messagebox.showerror("Photo Curation Error", f"An error occurred while curating photos:\n{str(e)}", parent=self)

    def check_notes_and_reanalyze_all(self):
        """Re-analyzes all curated photos, inspecting EXIF and waypoint notes with AI."""
        if not self.curated_photos_list:
            messagebox.showinfo("No Photos", "Please run 'Curate & Generate Captions' first.", parent=self)
            return

        self._ensure_field_notes_loaded()
        updated_count = 0

        for item in self.curated_photos_list:
            fpath = item.get('file_path', '')
            dt, lat, lon, direction, note = extract_exif(fpath)
            if not note and item.get('has_gps'):
                lat = item.get('lat')
                lon = item.get('lon')
                if lat is not None and lon is not None:
                    wp_note = self.find_nearest_field_note(lat, lon, max_dist_m=350)
                    if wp_note:
                        note = wp_note

            # Preserve existing note if newly found note is empty
            if not note:
                note = item.get('note', '')
            item['note'] = note

            # Generate new AI caption integrating this note
            cap, conf = self.ai.generate_photo_caption(fpath, photo_note=note)
            item['caption'] = cap
            item['confidence'] = f"{conf * 100:.0f}%"

            # Re-check category with note keywords
            fname = item.get('filename', '')
            lower_text = f"{fname} {note}".lower()
            for c_name, kw_list in TARGET_CATEGORIES:
                if any(kw in lower_text for kw in kw_list):
                    item['category'] = c_name
                    break
            updated_count += 1

        self.refresh_photo_tree()
        messagebox.showinfo("Notes & AI Re-Analysis Complete",
                            f"Checked notes and re-analyzed {updated_count} photos with AI assistant.",
                            parent=self)

    # --------------------------------------------------------------------------
    # TAB 9: REPORT ASSEMBLY & CALIBRATED PDF (~10MB)
    # --------------------------------------------------------------------------
    def build_tab_export(self):
        top_box = ttk.LabelFrame(self.tab_export, text=" Master Template & Output Deliverables ", style="Section.TLabelframe", padding=10)
        top_box.pack(fill="x", pady=(0, 8))

        r1 = ttk.Frame(top_box)
        r1.pack(fill="x", pady=(0, 6))
        ttk.Label(r1, text="Template Word Doc (*.docx):").pack(side="left", padx=(0, 6))
        self.template_doc_var = tk.StringVar(value=DEFAULT_PRELIMINARY_PROFILE.get('template_file', ''))
        ttk.Entry(r1, textvariable=self.template_doc_var).pack(side="left", fill="x", expand=True, padx=(0, 4))
        ttk.Button(r1, text="Browse...", command=self.browse_template_doc).pack(side="right")

        r2 = ttk.Frame(top_box)
        r2.pack(fill="x", pady=(0, 6))
        ttk.Label(r2, text="Report Output Folder:").pack(side="left", padx=(0, 6))
        self.output_dir_var = tk.StringVar(value=os.path.join(os.path.dirname(os.path.abspath(__file__)), "Output"))
        ttk.Entry(r2, textvariable=self.output_dir_var).pack(side="left", fill="x", expand=True, padx=(0, 4))
        ttk.Button(r2, text="Browse...", command=self.browse_output_dir).pack(side="right")

        r3 = ttk.Frame(top_box)
        r3.pack(fill="x", pady=(4, 6))
        ttk.Label(r3, text="Template Strategy:").pack(side="left", padx=(0, 6))
        self.tab_export_mode_combo = ttk.Combobox(
            r3,
            textvariable=self.template_mode_var,
            values=ReportTemplateProcessingMode.all_modes(),
            width=58,
            state="readonly",
            font=("Segoe UI", 9, "bold")
        )
        self.tab_export_mode_combo.pack(side="left", padx=(0, 10))
        self.tab_export_mode_combo.bind("<<ComboboxSelected>>", self.on_template_mode_changed)
        style_combobox_popdown(self.tab_export_mode_combo)

        ttk.Button(r3, text="✍️ Configure Section Prompts / AI Guidance...", command=self.open_section_prompts_dialog).pack(side="left")

        # PDF Size Calibration & Quality Optimization
        pdf_calib_box = ttk.LabelFrame(self.tab_export, text=" PDF Size Calibration & Quality Optimization ", style="Section.TLabelframe", padding=10)
        pdf_calib_box.pack(fill="x", pady=(0, 8))

        c_row1 = ttk.Frame(pdf_calib_box)
        c_row1.pack(fill="x", pady=(0, 6))
        ttk.Checkbutton(c_row1, text="Enforce Target PDF Size Limit (Preserve Map Figures 1-9 & Charts Lossless at 300 DPI)",
                        variable=self.pdf_enforce_limit_var, command=self._update_pdf_export_btn_label).pack(side="left")

        c_row2 = ttk.Frame(pdf_calib_box)
        c_row2.pack(fill="x", pady=(0, 6))
        ttk.Label(c_row2, text="Target PDF Size:").pack(side="left", padx=(0, 6))
        ttk.Entry(c_row2, textvariable=self.pdf_target_mb_var, width=6, font=("Segoe UI", 9, "bold")).pack(side="left", padx=(0, 2))
        ttk.Label(c_row2, text="MB", font=("Segoe UI", 9, "bold")).pack(side="left", padx=(0, 10))

        ttk.Button(c_row2, text="10 MB (Aramco Standard)", command=lambda: self.set_pdf_target_mb(10.0)).pack(side="left", padx=(0, 4))
        ttk.Button(c_row2, text="15 MB (Balanced)", command=lambda: self.set_pdf_target_mb(15.0)).pack(side="left", padx=(0, 4))
        ttk.Button(c_row2, text="25 MB (High Detail)", command=lambda: self.set_pdf_target_mb(25.0)).pack(side="left", padx=(0, 4))
        ttk.Button(c_row2, text="50 MB (Maximum Print)", command=lambda: self.set_pdf_target_mb(50.0)).pack(side="left", padx=(0, 4))
        ttk.Button(c_row2, text="Unrestricted (High-Res)", command=self.disable_pdf_size_limit).pack(side="left", padx=(0, 4))

        calib_note = ttk.Label(pdf_calib_box,
                               text="✔ Smart Report Media Analyzer: Figures 1 to 9 (Core Maps & GIS Pie Charts) remain 100% uncompressed at full 300 DPI fidelity. Field photo plates are automatically analyzed and dynamically budgeted to strictly satisfy your target MB limit.",
                               foreground="#38BDF8", font=("Segoe UI", 8))
        calib_note.pack(anchor="w")

        ai_box = ttk.LabelFrame(self.tab_export, text=" Multimodal AI Vision & Geomatics Autonomous Intelligence ", style="Section.TLabelframe", padding=10)
        ai_box.pack(fill="x", pady=(0, 8))

        # Status Badge Row
        st_row = ttk.Frame(ai_box)
        st_row.pack(fill="x", pady=(0, 6))
        self.ai_badge_lbl = tk.Label(st_row, text="", font=("Segoe UI", 9, "bold"), padx=10, pady=4, relief="flat")
        self.ai_badge_lbl.pack(side="left")
        self.ai_info_lbl = ttk.Label(st_row, text="", foreground="#CBD5E1", font=("Segoe UI", 9))
        self.ai_info_lbl.pack(side="left", padx=(10, 0))

        # Key Input & Auto-Detect Row
        k_row = ttk.Frame(ai_box)
        k_row.pack(fill="x", pady=(2, 4))
        ttk.Label(k_row, text="Gemini AI API Key (Auto-Saved):").pack(side="left", padx=(0, 6))
        ttk.Entry(k_row, textvariable=self.gemini_key_var, show="*").pack(side="left", fill="x", expand=True, padx=(0, 6))
        ttk.Button(k_row, text="🔍 Auto-Detect / Reload", command=self.auto_detect_ai_key).pack(side="left", padx=(0, 6))
        ttk.Button(k_row, text="⚡ Test AI Connection", command=self.test_ai_key).pack(side="left")

        note_lbl = ttk.Label(ai_box, text="✔ Note: The suite functions continuously 100% of the time with autonomous offline intelligence. Entering a free Gemini API key is optional and will be automatically saved across all sessions.", foreground="#94A3B8", font=("Segoe UI", 8))
        note_lbl.pack(anchor="w", pady=(2, 0))

        # Live Execution Log
        log_box = ttk.LabelFrame(self.tab_export, text=" Generation, Word COM Automation & Size Calibration Log ", style="Section.TLabelframe", padding=8)
        log_box.pack(fill="both", expand=True, pady=(0, 8))

        self.export_log_text = tk.Text(log_box, bg="#0A0F1D", fg="#E2E8F0", insertbackground="#38BDF8",
                                       relief="flat", highlightthickness=1, highlightcolor="#38BDF8",
                                       highlightbackground="#334155", font=("Consolas", 9), height=12)
        self.export_log_text.pack(fill="both", expand=True)

        # Buttons Bar
        b_bar = ttk.Frame(self.tab_export)
        b_bar.pack(fill="x")
        ttk.Button(b_bar, text="▶ Generate Complete Word Report (*.docx)", style="Accent.TButton", command=self.start_generate_word_report).pack(side="left", padx=(0, 8))
        self.export_pdf_btn = ttk.Button(b_bar, text="📄 Export Calibrated PDF (Target <= 10.0 MB)", style="Success.TButton", command=self.start_export_calibrated_pdf)
        self.export_pdf_btn.pack(side="left", padx=(0, 8))
        ttk.Button(b_bar, text="📁 Open Output Folder", command=self.open_output_folder).pack(side="right")

    def set_pdf_target_mb(self, mb: float):
        self.pdf_enforce_limit_var.set(True)
        self.pdf_target_mb_var.set(mb)
        self._update_pdf_export_btn_label()

    def disable_pdf_size_limit(self):
        self.pdf_enforce_limit_var.set(False)
        self._update_pdf_export_btn_label()

    def _update_pdf_export_btn_label(self, *args):
        if not hasattr(self, 'export_pdf_btn'):
            return
        if self.pdf_enforce_limit_var.get():
            try:
                mb = float(self.pdf_target_mb_var.get())
                self.export_pdf_btn.configure(text=f"📄 Export Calibrated PDF (Target <= {mb:.1f} MB)")
            except Exception:
                self.export_pdf_btn.configure(text="📄 Export Calibrated PDF")
        else:
            self.export_pdf_btn.configure(text="📄 Export PDF (Unrestricted Size)")

    def export_log(self, msg):
        self.export_log_text.insert("end", msg + "\n")
        self.export_log_text.see("end")

    def update_ai_status_display(self):
        if not hasattr(self, 'ai_badge_lbl'):
            return
        st = self.ai.get_status_info()
        bg_col = "#064E3B" if st.get("online") else "#0C4A6E"
        fg_col = "#34D399" if st.get("online") else "#38BDF8"
        self.ai_badge_lbl.configure(text=st.get("badge", ""), bg=bg_col, fg=fg_col)
        self.ai_info_lbl.configure(text=st.get("details", ""))

    def auto_detect_ai_key(self):
        detected = discover_api_key()
        if detected:
            self.gemini_key_var.set(detected)
            self.ai.set_api_key(detected)
            self.update_ai_status_display()
            masked = f"{detected[:6]}...{detected[-4:]}"
            messagebox.showinfo("AI Key Auto-Detected", f"Active Gemini API Key was automatically discovered and saved!\nKey: {masked}\nCloud Vision & live research are fully enabled.", parent=self)
        else:
            self.update_ai_status_display()
            messagebox.showinfo("Autonomous AI Active", "Autonomous Geomatics & Vision Engine is active and operating 100% offline.\nNo API key is required to use all suite features and report generators.", parent=self)

    def test_ai_key(self):
        k = self.gemini_key_var.get().strip()
        self.ai.set_api_key(k)
        self.update_ai_status_display()
        p_name = self.prospect_name_var.get().strip() or "Prospect"
        fact = self.ai.research_prospect(p_name)
        if self.ai.has_api_key():
            if fact and 'closest_town' in fact:
                messagebox.showinfo("AI Connected", f"Live Gemini Cloud API Connected Successfully!\n\nProspect: {p_name}\nClosest Hub: {fact.get('closest_town')}\nTerrain: {fact.get('terrain_summary')}", parent=self)
            else:
                messagebox.showwarning("Connection Notice", "Cloud API key entered, but network connection could not reach Gemini.\nAutonomous AI Engine remains active as seamless fallback.", parent=self)
        else:
            messagebox.showinfo("Autonomous AI Ready", f"Autonomous Geomatics Intelligence is 100% Operational!\n\nProspect: {p_name}\nClosest Hub: {fact.get('closest_town')}\nTerrain: {fact.get('terrain_summary')}\nClimate: {fact.get('climate_summary')}\n\nNo external API is required.", parent=self)

    def browse_template_doc(self):
        f = filedialog.askopenfilename(
            title="Select Master Report Template Document",
            filetypes=[("Word Document", "*.docx"), ("All Files", "*.*")]
        )
        if f:
            self.template_doc_var.set(os.path.normpath(f))

    def browse_output_dir(self):
        d = filedialog.askdirectory(title="Select Report Output Directory")
        if d:
            self.output_dir_var.set(os.path.normpath(d))


    # --------------------------------------------------------------------------
    # TAB 10: DAILY FIELD JOURNAL, ROUGH THOUGHTS CATEGORIZER & MOBILE SYNC
    # --------------------------------------------------------------------------
    def build_tab_journal(self):
        """Constructs Tab 10: Field Journal, Thoughts Categorizer, and Mobile Synchronization."""
        # 1. Top Trip & Project Header Bar
        top_box = ttk.LabelFrame(self.tab_journal, text=" Scouting Trip Identity & Portable Package Synchronization ", style="Section.TLabelframe", padding=8)
        top_box.pack(fill="x", pady=(0, 6))

        r1 = ttk.Frame(top_box)
        r1.pack(fill="x", pady=(0, 4))
        ttk.Label(r1, text="Project ID / Prospect:", font=("Segoe UI", 9, "bold")).pack(side="left", padx=(0, 4))
        self.journal_proj_var = tk.StringVar(value=self.prospect_name_var.get() or "Amzan South")
        ttk.Entry(r1, textvariable=self.journal_proj_var, width=18).pack(side="left", padx=(0, 10))

        ttk.Label(r1, text="Trip ID:").pack(side="left", padx=(0, 4))
        self.journal_trip_var = tk.StringVar(value=f"TRIP_{datetime.now().strftime('%Y%m%d')}_01")
        ttk.Entry(r1, textvariable=self.journal_trip_var, width=18).pack(side="left", padx=(0, 10))

        ttk.Label(r1, text="Scout Name:").pack(side="left", padx=(0, 4))
        self.journal_scout_var = tk.StringVar(value=self.prep_by_var.get() or "Nasrullah Khan")
        ttk.Entry(r1, textvariable=self.journal_scout_var, width=18).pack(side="left", padx=(0, 10))

        ttk.Button(r1, text="🔄 Switch / Reload Project", command=self.on_journal_project_changed).pack(side="left", padx=(0, 6))
        ttk.Button(r1, text="📦 Import Mobile Package (*.scoutpkg)...", style="Accent.TButton", command=self.import_mobile_package_dialog).pack(side="right", padx=(4, 0))
        ttk.Button(r1, text="📤 Export Scouting Package...", command=self.export_mobile_package_dialog).pack(side="right")

        # 2. Split Body: Left = Quick Thought Entry; Right = Categorized Timeline & Section Pre-fill
        split = ttk.PanedWindow(self.tab_journal, orient="horizontal")
        split.pack(fill="both", expand=True)

        # LEFT: Thought Recorder Box
        left_box = ttk.LabelFrame(split, text=" Continuous Field Observation / Voice Transcript Recorder ", style="Section.TLabelframe", padding=8)
        split.add(left_box, weight=4)

        ttk.Label(left_box, text="Type rough daily thoughts, speech-to-text dictations, or field notes below:\n(No complete sentences required — AI will assess & assign to report sections)",
                  font=("Segoe UI", 8), foreground="#94A3B8").pack(anchor="w", pady=(0, 4))

        self.txt_journal_entry = tk.Text(left_box, height=8, bg="#0F172A", fg="#F8FAFC", insertbackground="#38BDF8",
                                         font=("Segoe UI", 10), wrap="word", relief="flat",
                                         highlightthickness=1, highlightcolor="#38BDF8", highlightbackground="#334155")
        self.txt_journal_entry.pack(fill="both", expand=True, pady=(0, 6))

        # Metadata options row (Timestamp, GPS)
        meta_row = ttk.Frame(left_box)
        meta_row.pack(fill="x", pady=(0, 4))
        self.journal_auto_time_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(meta_row, text="Auto-timestamp entry", variable=self.journal_auto_time_var).pack(side="left")

        ttk.Label(meta_row, text="Lat:").pack(side="left", padx=(8, 2))
        self.journal_lat_var = tk.StringVar()
        ttk.Entry(meta_row, textvariable=self.journal_lat_var, width=9).pack(side="left")
        ttk.Label(meta_row, text="Lon:").pack(side="left", padx=(4, 2))
        self.journal_lon_var = tk.StringVar()
        ttk.Entry(meta_row, textvariable=self.journal_lon_var, width=9).pack(side="left")
        ttk.Button(meta_row, text="📍 Get GPS", width=8, command=self.journal_grab_last_gps).pack(side="left", padx=(4, 0))

        # Category Assignment Row
        cat_row = ttk.Frame(left_box)
        cat_row.pack(fill="x", pady=(0, 6))
        self.journal_auto_cat_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(cat_row, text="⚡ Auto-Categorize with AI (Recommended)", variable=self.journal_auto_cat_var).pack(side="left")

        ttk.Label(cat_row, text="Override Section:").pack(side="left", padx=(8, 2))
        self.journal_sec_override_var = tk.StringVar(value="Auto")
        cat_choices = ["Auto"] + [f"{k}: {v['name']}" for k, v in ScoutingJournalManager.SECTION_TAXONOMY.items()]
        cb_override = ttk.Combobox(cat_row, textvariable=self.journal_sec_override_var, values=cat_choices, state="readonly", width=24)
        cb_override.pack(side="left", fill="x", expand=True)

        # Action Buttons
        btn_bar = ttk.Frame(left_box)
        btn_bar.pack(fill="x", pady=(4, 0))
        ttk.Button(btn_bar, text="➕ Add Field Thought to Project", style="Accent.TButton", command=self.add_journal_entry).pack(side="left", fill="x", expand=True, padx=(0, 4))
        ttk.Button(btn_bar, text="Clear Box", width=9, command=lambda: self.txt_journal_entry.delete("1.0", "end")).pack(side="right")

        self.lbl_journal_feedback = ttk.Label(left_box, text="Ready for field input.", font=("Segoe UI", 8, "italic"), foreground="#38BDF8")
        self.lbl_journal_feedback.pack(anchor="w", pady=(4, 0))

        # RIGHT: Timeline & Section Prompts Aggregator
        right_box = ttk.LabelFrame(split, text=" Daily Scouting Timeline & Pre-fill Prompts Hub ", style="Section.TLabelframe", padding=8)
        split.add(right_box, weight=6)

        filter_row = ttk.Frame(right_box)
        filter_row.pack(fill="x", pady=(0, 6))
        ttk.Label(filter_row, text="Filter Section:").pack(side="left", padx=(0, 4))
        self.journal_filter_var = tk.StringVar(value="All Sections")
        filter_choices = ["All Sections"] + [v['name'] for v in ScoutingJournalManager.SECTION_TAXONOMY.values()]
        cb_filter = ttk.Combobox(filter_row, textvariable=self.journal_filter_var, values=filter_choices, state="readonly", width=28)
        cb_filter.pack(side="left", padx=(0, 8))
        cb_filter.bind("<<ComboboxSelected>>", lambda e: self.refresh_journal_tree())

        self.lbl_journal_stats = ttk.Label(filter_row, text="Entries: 0", font=("Segoe UI", 9, "bold"), foreground="#10B981")
        self.lbl_journal_stats.pack(side="right")

        # Treeview Timeline Table
        cols = ("time", "sec", "conf", "gps", "text")
        self.journal_tree = ttk.Treeview(right_box, columns=cols, show="headings", height=12)
        self.journal_tree.heading("time", text="Timestamp")
        self.journal_tree.heading("sec", text="Categorized Section")
        self.journal_tree.heading("conf", text="Confidence")
        self.journal_tree.heading("gps", text="GPS Coords")
        self.journal_tree.heading("text", text="Field Observation / Rough Thought")

        self.journal_tree.column("time", width=125, anchor="center")
        self.journal_tree.column("sec", width=190, anchor="w")
        self.journal_tree.column("conf", width=75, anchor="center")
        self.journal_tree.column("gps", width=110, anchor="center")
        self.journal_tree.column("text", width=340, anchor="w")

        j_sb = ttk.Scrollbar(right_box, orient="vertical", command=self.journal_tree.yview)
        self.journal_tree.configure(yscrollcommand=j_sb.set)
        self.journal_tree.pack(side="top", fill="both", expand=True)
        j_sb.pack(side="right", fill="y")

        # Bottom Action Bar
        act_bar = ttk.Frame(right_box)
        act_bar.pack(fill="x", pady=(8, 0))

        ttk.Button(act_bar, text="🗑 Delete Selected Entry", command=self.delete_selected_journal_entry).pack(side="left", padx=(0, 6))
        ttk.Button(act_bar, text="📖 Open Section Prompts Dialog", command=self.open_section_prompts_dialog).pack(side="right")
        ttk.Button(act_bar, text="⚡ Pre-fill All 14 Section Prompts from Journal", style="Accent.TButton", command=self.synthesize_journal_to_prompts).pack(side="right", padx=(0, 6))

        self.refresh_journal_tree()

    def on_journal_project_changed(self):
        proj = self.journal_proj_var.get().strip() or "Amzan South"
        self.journal_mgr.load_project(proj)
        self.refresh_journal_tree()
        self.export_log(f"Switched scouting journal to project: {proj} ({len(self.journal_mgr.entries)} entries).")

    def journal_grab_last_gps(self):
        """Pulls GPS coordinates from the last selected photo or active track."""
        if hasattr(self, 'curated_photos_list') and self.curated_photos_list:
            for p in reversed(self.curated_photos_list):
                if p.get('has_gps') and p.get('lat') is not None:
                    self.journal_lat_var.set(f"{p['lat']:.5f}")
                    self.journal_lon_var.set(f"{p['lon']:.5f}")
                    self.lbl_journal_feedback.configure(text=f"Filled GPS from photo: {p.get('filename')}")
                    return
        messagebox.showinfo("GPS Not Found", "No geotagged photos or active GPS fix available yet.", parent=self)

    def add_journal_entry(self):
        text = self.txt_journal_entry.get("1.0", "end").strip()
        if not text:
            messagebox.showwarning("Empty Entry", "Please type or paste your daily field observation.", parent=self)
            return

        # Determine section
        chosen_sec = None
        override = self.journal_sec_override_var.get()
        if override != "Auto" and ":" in override:
            chosen_sec = override.split(":", 1)[0].strip()

        # Parse GPS if entered
        lat_val = None
        lon_val = None
        try:
            if self.journal_lat_var.get().strip():
                lat_val = float(self.journal_lat_var.get().strip())
            if self.journal_lon_var.get().strip():
                lon_val = float(self.journal_lon_var.get().strip())
        except ValueError:
            pass

        entry = self.journal_mgr.add_entry(
            text=text,
            section_id=chosen_sec,
            lat=lat_val,
            lon=lon_val,
            source_type="manual_text"
        )

        self.txt_journal_entry.delete("1.0", "end")
        self.refresh_journal_tree()
        self.lbl_journal_feedback.configure(
            text=f"✔ Saved & Assigned to '{entry.category_name}' (Confidence: {int(entry.confidence*100)}%)"
        )
        self.export_log(f"Journal thought added: [{entry.category_name}] {text[:45]}...")

    def delete_selected_journal_entry(self):
        sel = self.journal_tree.selection()
        if not sel:
            messagebox.showinfo("Selection Required", "Please select an entry in the timeline table to delete.", parent=self)
            return
        item_id = sel[0]
        entry_id = self.journal_tree.item(item_id, "tags")[0] if self.journal_tree.item(item_id, "tags") else ""
        if entry_id and messagebox.askyesno("Delete Entry", "Delete this field observation from project journal?", parent=self):
            self.journal_mgr.delete_entry(entry_id)
            self.refresh_journal_tree()

    def refresh_journal_tree(self):
        if not hasattr(self, 'journal_tree'):
            return
        for item in self.journal_tree.get_children():
            self.journal_tree.delete(item)

        filter_sec_name = self.journal_filter_var.get()
        filtered_entries = []

        for e in self.journal_mgr.entries:
            if filter_sec_name != "All Sections" and e.category_name != filter_sec_name:
                continue
            filtered_entries.append(e)

            gps_str = f"{e.lat:.4f}, {e.lon:.4f}" if (e.lat and e.lon) else "—"
            conf_str = f"{int(e.confidence*100)}%"
            self.journal_tree.insert("", "end", values=(e.timestamp, e.category_name, conf_str, gps_str, e.text), tags=(e.entry_id,))

        stats = self.journal_mgr.get_summary_stats()
        self.lbl_journal_stats.configure(
            text=f"Total: {stats['total_entries']} entries | Sections Covered: {len(stats['by_section'])}/14"
        )

    def synthesize_journal_to_prompts(self):
        """Converts accumulated daily thoughts into structured user section prompts."""
        if not self.journal_mgr.entries:
            messagebox.showinfo("Journal Empty", "No field observations recorded yet. Enter thoughts or import a mobile package first.", parent=self)
            return

        synthesized = self.journal_mgr.synthesize_section_prompts()
        self.user_section_prompts.update(synthesized)
        self.export_log(f"Synthesized field journal into prompts for {len(synthesized)} report sections.")
        msg = f"Successfully synthesized {len(self.journal_mgr.entries)} field thoughts into structured prompts for {len(synthesized)} report sections!\n\nClick 'Configure Section Prompts...' to inspect or test AI drafts."
        messagebox.showinfo("Prompts Pre-filled", msg, parent=self)

    def import_mobile_package_dialog(self):
        """Dialog to import a portable field package (*.scoutpkg / *.zip)."""
        fpath = filedialog.askopenfilename(
            title="Import Mobile Scouting Package (*.scoutpkg, *.zip)",
            filetypes=[("Scouting Package", "*.scoutpkg;*.zip"), ("All Files", "*.*")],
            parent=self
        )
        if not fpath:
            return

        # Target photos directory
        target_dir = self.photo_dir_var.get().strip() if hasattr(self, 'photo_dir_var') and self.photo_dir_var.get().strip() else ""
        if not target_dir or not os.path.exists(target_dir):
            target_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "imported_scout_photos")
            os.makedirs(target_dir, exist_ok=True)
            if hasattr(self, 'photo_dir_var'):
                self.photo_dir_var.set(target_dir)

        try:
            res = ScoutingPackageManager.import_package(
                pkg_path=fpath,
                target_photos_dir=target_dir,
                journal_manager=self.journal_mgr,
                log_cb=self.export_log
            )

            # Update project name if provided
            proj_id = res.get("project_id")
            if proj_id and hasattr(self, 'prospect_name_var') and not self.prospect_name_var.get().strip():
                self.prospect_name_var.set(proj_id)
                self.journal_proj_var.set(proj_id)

            # Load photos if any imported
            if res.get("photos"):
                self.curated_photos_list = res["photos"]
                self.refresh_photo_tree()

            # Load track if any imported
            if res.get("track_path") and hasattr(self, 'track_file_var'):
                self.track_file_var.set(res["track_path"])
                if hasattr(self, 'track_analyzer'):
                    self.track_analyzer.load_track(res["track_path"])

            # Load waypoints if any imported
            if res.get("waypoints"):
                self.loaded_field_notes = res["waypoints"]

            # Refresh journal UI
            self.refresh_journal_tree()

            # Auto-synthesize prompts
            self.synthesize_journal_to_prompts()

            imported_msg = (
                f"Scouting package successfully imported:\n\n"
                f"• {len(res.get('photos', []))} Georeferenced field photos\n"
                f"• {len(res.get('waypoints', []))} GPS Waypoints\n"
                f"• {len(res.get('journal_entries', []))} Daily field observations\n"
                f"• GPS Track Log: {'Yes' if res.get('track_path') else 'None'}\n\n"
                f"All daily thoughts have been categorized and pre-filled into report prompts!"
            )
            messagebox.showinfo("Package Imported", imported_msg, parent=self)
        except Exception as ex:
            self.export_log(f"Error importing scouting package: {ex}")
            messagebox.showerror("Import Error", f"Failed to import scouting package:\n{ex}", parent=self)

    def export_mobile_package_dialog(self):
        """Dialog to export current desktop project data as a *.scoutpkg."""
        proj = self.prospect_name_var.get().strip() or "Prospect_Scout"
        default_name = f"{proj}_Scouting_Package_{datetime.now().strftime('%Y%m%d')}.scoutpkg"
        save_path = filedialog.asksaveasfilename(
            title="Export Mobile Scouting Package (*.scoutpkg)",
            initialfile=default_name,
            defaultextension=".scoutpkg",
            filetypes=[("Scouting Package", "*.scoutpkg"), ("ZIP Archive", "*.zip")],
            parent=self
        )
        if not save_path:
            return

        track_f = self.track_file_var.get().strip() if hasattr(self, 'track_file_var') else None
        wps = getattr(self, 'loaded_field_notes', [])
        crew = self.crew_name_var.get().strip() if hasattr(self, 'crew_name_var') else "Crew S-86"

        try:
            pkg_file = ScoutingPackageManager.export_package(
                output_pkg_path=save_path,
                project_id=proj,
                crew_name=crew,
                scout_name=self.prep_by_var.get() or "Field Scout",
                journal_manager=self.journal_mgr,
                photo_list=self.curated_photos_list,
                waypoints=wps,
                track_file_path=track_f,
                log_cb=self.export_log
            )
            messagebox.showinfo("Package Exported", f"Scouting package successfully exported:\n{pkg_file}", parent=self)
        except Exception as ex:
            self.export_log(f"Error exporting package: {ex}")
            messagebox.showerror("Export Error", f"Failed to export package:\n{ex}", parent=self)

    def start_generate_word_report(self):
        tpl = self.template_doc_var.get().strip()
        out_d = self.output_dir_var.get().strip()
        if not tpl or not os.path.exists(tpl):
            messagebox.showerror("Template Missing", f"Template Word doc does not exist:\n{tpl}", parent=self)
            return

        prospect = self.prospect_name_var.get().strip()
        out_docx = os.path.join(out_d, f"ARGAS_S86_{prospect}_Scouting_Report.docx")

        # Sync active maps from UI
        for k, ui in self.map_ui_rows.items():
            if k in self.maps_mgr.maps:
                self.maps_mgr.maps[k].enabled = ui['enabled_var'].get()
                self.maps_mgr.maps[k].file_path = ui['file_var'].get().strip()

        project_meta = {
            'prospect_name': prospect,
            'crew_name': self.crew_name_var.get().strip(),
            'report_date': self.report_date_var.get().strip(),
            'contract_no': self.contract_no_var.get().strip(),
            'contractor_name': f"ARGAS ({self.crew_name_var.get().strip()})",
            'revision_no': self.rev_no_var.get().strip(),
            'revision_date': self.rev_date_var.get().strip(),
            'prepared_by': self.prep_by_var.get().strip(),
            'reviewed_by': self.rev_by_var.get().strip(),
            'approved_by': self.appr_by_var.get().strip(),
            'distribution_list': self.current_profile_data.get('metadata', {}).get('distribution_list', []),
            'scouting_team': self.current_profile_data.get('metadata', {}).get('scouting_team', []),
            'scouting_equipment': self.current_profile_data.get('metadata', {}).get('scouting_equipment', []),
            'objectives': self.current_profile_data.get('metadata', {}).get('objectives', []),
            'communication_means': self.current_profile_data.get('metadata', {}).get('communication_means', [])
        }

        # Resolve Figure 5 Scouting Terrain Map (System-Generated vs User-Provided)
        terrain_map = None
        if hasattr(self, 'terrain_map_mode_var') and self.terrain_map_mode_var.get() == "system":
            terrain_map = getattr(self, 'generated_terrain_map_path', None)
        else:
            user_m = self.user_terrain_map_path.get().strip() if hasattr(self, 'user_terrain_map_path') else ""
            terrain_map = user_m if (user_m and os.path.exists(user_m)) else getattr(self, 'generated_terrain_map_path', None)

        # Resolve Figure 7.1 Aramco Contractual Operational Area Map (System-Generated vs User-Provided)
        aramco_map = None
        if hasattr(self, 'aramco_map_mode_var') and self.aramco_map_mode_var.get() == "system":
            aramco_map = getattr(self, 'generated_aramco_map_path', None)
        else:
            user_a = self.user_aramco_map_path.get().strip() if hasattr(self, 'user_aramco_map_path') else ""
            aramco_map = user_a if (user_a and os.path.exists(user_a)) else getattr(self, 'generated_aramco_map_path', None)

        gen = ReportDocxGenerator(tpl)
        try:
            mode = self.template_mode_var.get()
            if mode == ReportTemplateProcessingMode.INTERACTIVE_SECTION_COAUTHORING:
                if not self.user_section_prompts:
                    self.open_section_prompts_dialog()
            self.export_log(f'Executing report generation under strategy: {mode}...')
            gen.generate_report(
                output_docx_path=out_docx,
                project_meta=project_meta,
                boundary_mgr=self.boundary_mgr,
                maps_mgr=self.maps_mgr,
                terrain_data=self.terrain_analysis_results,
                pie_chart_path=self.generated_pie_chart_path,
                terrain_map_path=terrain_map,
                aramco_map_path=aramco_map,
                aramco_pie_chart_path=getattr(self, 'generated_aramco_pie_chart_path', None),
                aramco_data=getattr(self, 'aramco_contractual_results', None),
                curated_photos=self.curated_photos_list,
                include_non_geotagged=self.include_non_geotagged_var.get() if hasattr(self, 'include_non_geotagged_var') else True,
                processing_mode=mode,
                user_section_prompts=self.user_section_prompts,
                journal_mgr=self.journal_mgr,
                log_cb=self.export_log
            )
            messagebox.showinfo("Report Generated", f"Scouting Report Word Document successfully generated:\n{out_docx}", parent=self)
        except Exception as e:
            self.export_log(f"Error generating report: {str(e)}")
            messagebox.showerror("Generation Error", str(e), parent=self)

    def start_export_calibrated_pdf(self):
        prospect = self.prospect_name_var.get().strip()
        out_d = self.output_dir_var.get().strip()
        out_docx = os.path.join(out_d, f"ARGAS_S86_{prospect}_Scouting_Report.docx")
        out_pdf = os.path.join(out_d, f"ARGAS_S86_{prospect}_Scouting_Report.pdf")

        if not os.path.exists(out_docx):
            self.export_log("DOCX not found. Generating Word document first...")
            self.start_generate_word_report()

        if not os.path.exists(out_docx):
            return

        enforce_lim = self.pdf_enforce_limit_var.get()
        target_mb = 10.0
        try:
            target_mb = float(self.pdf_target_mb_var.get())
        except Exception:
            target_mb = 10.0

        if enforce_lim:
            self.export_log(f"Calibrating document media for target limit: <= {target_mb:.1f} MB...")
            optimize_docx_media_for_target_mb(out_docx, target_mb=target_mb, enforce_limit=True, log_cb=self.export_log)

        self.export_log("Exporting to PDF via Microsoft Word Automation...")
        ps_script = f"""
        $word = New-Object -ComObject Word.Application
        $word.Visible = $false
        try {{
            $doc = $word.Documents.Open('{os.path.abspath(out_docx)}')
            $doc.ExportAsFixedFormat('{os.path.abspath(out_pdf)}', 17, $false, 0)
            $doc.Close($false)
        }} finally {{
            $word.Quit()
            [System.Runtime.Interopservices.Marshal]::ReleaseComObject($word) | Out-Null
        }}
        """
        cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_script]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0 or not os.path.exists(out_pdf):
            self.export_log(f"Word Automation Error: {res.stderr}")
            messagebox.showerror("PDF Export Failed", res.stderr, parent=self)
            return

        size_mb = os.path.getsize(out_pdf) / 1024 / 1024
        self.export_log(f"Exported PDF Size: {size_mb:.2f} MB")

        # Stream calibration if larger than target_mb
        if enforce_lim and size_mb > target_mb and pypdf:
            self.export_log(f"Calibrating PDF streams to reach <= {target_mb:.1f} MB target (preserving lossless maps)...")
            temp_pdf = out_pdf + ".calib.pdf"
            reader = pypdf.PdfReader(out_pdf)
            writer = pypdf.PdfWriter()
            for page in reader.pages:
                p = writer.add_page(page)
                p.compress_content_streams()
            with open(temp_pdf, 'wb') as f:
                writer.write(f)
            if os.path.exists(out_pdf):
                os.remove(out_pdf)
            shutil.move(temp_pdf, out_pdf)
            size_mb = os.path.getsize(out_pdf) / 1024 / 1024
            self.export_log(f"Calibrated PDF final size: {size_mb:.2f} MB")

        status_msg = f"Final Size: {size_mb:.2f} MB"
        if enforce_lim:
            status_msg += f" (Target: <= {target_mb:.1f} MB)"
        messagebox.showinfo("PDF Ready",
                            f"Scouting Report PDF successfully exported to:\n{out_pdf}\n\n{status_msg}\nFigures 1-9: 100% Lossless at 300 DPI",
                            parent=self)

    def open_output_folder(self):
        d = self.output_dir_var.get().strip()
        if os.path.exists(d):
            os.startfile(d)

    # --------------------------------------------------------------------------
    # PROFILE MANAGEMENT CALLBACKS
    # --------------------------------------------------------------------------
    def on_profile_selected(self, event=None):
        name = self.profile_var.get()
        data = self.profile_mgr.load_profile(name)
        self.current_profile_data = data
        meta = data.get('metadata', {})

        self.prospect_name_var.set(meta.get('prospect_name', ''))
        self.crew_name_var.set(meta.get('crew_name', ''))
        self.report_date_var.set(meta.get('report_date', ''))
        self.contract_no_var.set(meta.get('contract_no', ''))
        self.rev_no_var.set(meta.get('revision_no', 'Rev 0'))
        self.rev_date_var.set(meta.get('revision_date', ''))
        self.prep_by_var.set(meta.get('prepared_by', ''))
        self.rev_by_var.set(meta.get('reviewed_by', ''))
        self.appr_by_var.set(meta.get('approved_by', ''))

        self.populate_dist_tree(meta.get('distribution_list', []))
        self.populate_team_and_eq(meta.get('scouting_team', []), meta.get('scouting_equipment', []))

        if hasattr(self, 'template_mode_var'):
            saved_mode = data.get('template_processing_mode') or meta.get('template_processing_mode')
            if saved_mode and saved_mode in ReportTemplateProcessingMode.all_modes():
                self.template_mode_var.set(saved_mode)
                self.on_template_mode_changed()

    def save_current_profile(self):
        name = self.profile_var.get().strip()
        if not name:
            name = "Custom Scouting Profile"
        if hasattr(self, 'template_mode_var'):
            self.current_profile_data['template_processing_mode'] = self.template_mode_var.get()
        self.profile_mgr.save_profile(name, self.current_profile_data)
        self.profile_combo.configure(values=self.profile_mgr.list_profiles())
        messagebox.showinfo("Profile Saved", f"Profile '{name}' saved successfully.", parent=self)


# ==============================================================================
# MAIN LAUNCHER
# ==============================================================================

def main():
    app = ScoutingSuiteApp()
    app.mainloop()

if __name__ == "__main__":
    main()
