"""
Report Profile Management System for ARGAS Scouting Suite
Stores and loads report configurations, standard metadata defaults,
section mappings, and supports custom user templates.
"""

import os
import json
from typing import Dict, List, Optional


DEFAULT_PRELIMINARY_PROFILE = {
    "profile_name": "ARGAS Preliminary Scouting Report - Saudi Aramco",
    "report_type": "Preliminary Scouting Report",
    "template_file": r"D:\S86 Argas\Scouring Report Template\ARGAS S86-340400001_LIDAM II Scouting Report_August 2026_Template.docx",
    "metadata": {
        "report_date": "October 2026",
        "crew_name": "Crew S-86",
        "prospect_name": "Amzan South",
        "contract_no": "340400001",
        "client_name": "Saudi Aramco",
        "contractor_name": "ARGAS (S-86)",
        "revision_no": "Rev 0",
        "revision_date": "26/10/2026",
        "prepared_by": "Party Chief / Chief Surveyor",
        "reviewed_by": "Operations Manager / QHSE Manager",
        "approved_by": "Saudi Aramco GDAD Representative",
        "distribution_list": [
            {"company": "Saudi Aramco", "position": "Geophysical Operations Rep (GDAD)"},
            {"company": "Saudi Aramco", "position": "Party Chief Representative"},
            {"company": "ARGAS", "position": "Operations Manager"},
            {"company": "ARGAS", "position": "QHSE Manager"},
            {"company": "ARGAS", "position": "Crew S-86 Party Chief"}
        ],
        "scouting_team": [
            {"no": "1", "name": "Mohammad Al-Otaibi", "position": "Party Chief", "responsibility": "Overall field operations & logistics"},
            {"no": "2", "name": "Nasrullah Khan", "position": "Chief Surveyor", "responsibility": "Geomatics, GNSS control & boundary scouting"},
            {"no": "3", "name": "Ahmed Salem", "position": "Vibrator Supervisor", "responsibility": "Vibrator terrain access & line feasibility"},
            {"no": "4", "name": "Sultan Al-Harbi", "position": "QHSE Officer", "responsibility": "Risk assessment, heat stress & medevac routes"},
            {"no": "5", "name": "Tariq Mansoor", "position": "Permitting Officer", "responsibility": "Farmland, pipeline & community liaison"}
        ],
        "scouting_equipment": [
            {"item": "Survey Vehicle", "type": "Toyota Land Cruiser 4WD", "quantity": "3", "fleet_no": "FL-8601/8602/8603", "remark": "Equipped with IVMS, winch & sand tires"},
            {"item": "Low-Pressure Buggy", "type": "Polaris Ranger 6x6", "quantity": "1", "fleet_no": "BG-8601", "remark": "Sabkha soft ground probing"},
            {"item": "GNSS RTK System", "type": "Trimble R12i GNSS", "quantity": "2 sets", "fleet_no": "EQ-TR-01/02", "remark": "Base & Rover for geodetic verification"},
            {"item": "Satellite Messenger", "type": "Garmin inReach Explorer+", "quantity": "3", "fleet_no": "SAT-01/02/03", "remark": "Emergency SOS & live tracking"},
            {"item": "Soil Penetrometer", "type": "Dynamic Cone Penetrometer", "quantity": "1", "fleet_no": "QC-DCP-01", "remark": "Sabkha bearing capacity testing"},
            {"item": "Emergency First Aid", "type": "Trauma Medevac Kit & AED", "quantity": "3", "fleet_no": "MED-86-A/B/C", "remark": "Paramedic certified kits"}
        ],
        "objectives": [
            "Verify all survey prospect boundary corner coordinates against Saudi Aramco concession agreements.",
            "Assess surface trafficability across sabkha, dunes, and escarpments for heavy vibrators.",
            "Identify all active oil, gas, and water pipelines requiring 50m GDAD offset buffers.",
            "Locate and document populated settlements, date palm farms, and military no-go zones.",
            "Evaluate regional highway crossing feasibility, traffic permitting, and cable protection bridges.",
            "Identify optimal base camp locations, water supply boreholes, and staging yards.",
            "Survey primary and secondary emergency medical evacuation (Medevac) routes to regional hospitals."
        ],
        "communication_means": [
            "VHF Simplex Crew Operations Channel (Ch 1-4)",
            "Saudi Aramco Digital Trunking Radio System",
            "Iridium / Thuraya Mobile Satellite Telephony",
            "Garmin inReach Satellite Two-Way Messaging",
            "GSM 4G/5G Cellular Network Coverage (STC / Mobily)"
        ]
    },
    "sections": [
        "1. Location & Prospect Overview",
        "2. Scouting Team",
        "3. Access to Prospect",
        "4. Objectives of the Scouting",
        "5. Communication Means",
        "6. Terrain Description and Initial Terrain Classification",
        "7. Remoteness and Operation Area",
        "8. Permitting Requirements",
        "9. Camps Organization",
        "10. Local Hospital Support",
        "11. Major Difficulties of the Blocks",
        "12. Hazards and Risk Identification",
        "13. Conclusion and Recommendations"
    ]
}


class ProfileManager:
    """Manages profile loading, saving, and preset creation."""

    def __init__(self, profiles_dir: Optional[str] = None):
        if profiles_dir is None:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            self.profiles_dir = os.path.join(base_dir, "profiles")
        else:
            self.profiles_dir = profiles_dir

        os.makedirs(self.profiles_dir, exist_ok=True)
        self.ensure_default_profile()

    def ensure_default_profile(self):
        """Ensures the standard Saudi Aramco profile is present."""
        def_path = os.path.join(self.profiles_dir, "ARGAS_Preliminary_Scouting_Report_Saudi_Aramco.json")
        if not os.path.exists(def_path):
            self.save_profile("ARGAS Preliminary Scouting Report - Saudi Aramco", DEFAULT_PRELIMINARY_PROFILE)

    def list_profiles(self) -> List[str]:
        """Lists all available saved profile names."""
        profiles = []
        for f in os.listdir(self.profiles_dir):
            if f.endswith('.json'):
                p_path = os.path.join(self.profiles_dir, f)
                try:
                    with open(p_path, 'r', encoding='utf-8') as jf:
                        d = json.load(jf)
                        profiles.append(d.get('profile_name', os.path.splitext(f)[0]))
                except Exception:
                    profiles.append(os.path.splitext(f)[0])
        return sorted(profiles)

    def load_profile(self, name: str) -> Dict:
        """Loads a profile by name."""
        clean_name = name.replace(" ", "_").replace("/", "_").replace("\\", "_")
        target_path = os.path.join(self.profiles_dir, f"{clean_name}.json")
        if os.path.exists(target_path):
            with open(target_path, 'r', encoding='utf-8') as f:
                return json.load(f)

        # Fallback to search inside all json files
        for f in os.listdir(self.profiles_dir):
            if f.endswith('.json'):
                p_path = os.path.join(self.profiles_dir, f)
                try:
                    with open(p_path, 'r', encoding='utf-8') as jf:
                        d = json.load(jf)
                        if d.get('profile_name') == name:
                            return d
                except Exception:
                    pass

        return DEFAULT_PRELIMINARY_PROFILE.copy()

    def save_profile(self, name: str, data: Dict) -> str:
        """Saves a profile to JSON."""
        data['profile_name'] = name
        clean_name = name.replace(" ", "_").replace("/", "_").replace("\\", "_")
        target_path = os.path.join(self.profiles_dir, f"{clean_name}.json")
        with open(target_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return target_path
