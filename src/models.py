"""Data model for LoudspeakerFEA.

LoudspeakerDesign dataclass representing one design column from the FEMotor spreadsheet.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from dataclasses import dataclass, field, asdict
from typing import Optional


def find_elmer_executable() -> str:
    """Search common Elmer installation paths and return the first existing executable.

    Also checks the system PATH via ``shutil.which``.  Falls back to
    ``"ElmerSolver.exe"`` (PATH lookup) if none are found.
    """
    candidates = [
        r"C:\Program Files\ElmerFEM\bin\ElmerSolver.exe",
        r"C:\Program Files (x86)\ElmerFEM\bin\ElmerSolver.exe",
    ]
    for path in candidates:
        if os.path.isfile(path):
            return path
    path_exe = shutil.which("ElmerSolver.exe")
    if path_exe:
        return path_exe
    return "ElmerSolver.exe"


def _default_working_directory() -> str:
    """Return a portable default working directory under the system temp folder."""
    return os.path.join(tempfile.gettempdir(), "ElmerFEA")


@dataclass
class LoudspeakerDesign:
    """Primary design entity — one column in the FEMotor spreadsheet."""

    # Identity
    name: str = ""
    id: Optional[int] = None

    # ─── Setup Information (Elmer) ───
    elmer_solver_path: str = "ElmerSolver.exe"
    working_directory: str = field(default_factory=_default_working_directory)
    mesh_size_factor: float = 1.0
    show_processor: int = 0
    magnet_material: str = "Ceramic5"

    # ─── Group B: Target Transducer Parameters ───
    target_bl: float = 8.0          # T·m
    target_cms: float = 344.0       # µm/N
    target_mms: float = 45.0        # g
    target_sd: float = 165.0        # cm²
    target_xmax: float = 1.5        # mm

    # ─── Group C: Non-Coil Mass Table ───
    mass_diaphragm: float = 17.453073689949782   # g
    mass_surround: float = 5.0                   # g
    mass_dome_coil: float = 5.0                  # g
    mass_spider_coil: float = 0.0                # g
    mass_spider: float = 0.0                     # g
    diaphragm_thickness: float = 0.4             # mm
    diaphragm_density: float = 2.7               # g/cm³

    # ─── Group A: Voice Coil ───
    wire_diameter: float = 0.5        # mm
    vc_wire_dcr: float = 3.45         # Ω
    tinsel_wire_dcr: float = 0.05     # Ω
    coil_id: float = 75.0             # mm
    coil_id_tolerance: float = 0.05   # mm
    former_thickness: float = 0.1     # mm
    former_length: float = 38.0       # mm
    number_of_layers: float = 2.0
    wire_type: int = 1                # 1=Copper, 2=CCA
    former_type: int = 1              # 1=Kapton, 2=Aluminum, 3=Nomex, 4=Kraft
    overhang: float = 15.82           # mm  (formula default; user may override)

    # ─── Group B: Motor Geometry ───
    inside_gap: float = 0.5           # mm
    outside_gap: float = 0.8          # mm
    top_plate_id: float = 79.018      # mm  (formula default; user may override)
    top_plate_od: float = 170.0       # mm
    top_plate_thickness: float = 12.0 # mm
    magnet_id: float = 90.0           # mm
    magnet_od: float = 180.0          # mm
    magnet_thickness: float = 45.0    # mm
    pole_od: float = 74.0             # mm  (formula default; user may override)
    pole_vent_hole: float = 38.0      # mm
    pole_overhang: float = 8.0        # mm
    bp_od: float = 170.0              # mm
    bp_thickness: float = 14.0        # mm
    bucking_mag_id: float = 0.0       # mm
    bucking_mag_od: float = 0.0       # mm
    bucking_mag_thickness: float = 0.0# mm
    vc_offset: float = -1.0           # mm
    side_leakage_distance: float = 100.0  # mm

    # ─── Group G: Input Loudspeaker Parameters ───
    speaker_dia: float = 14.494292838262302   # cm  (formula default; user may override)
    qm: float = 6.5
    mms_minus_vcmass: float = 27.453073689949782  # g  (formula default; user may override)
    cms_ls: float = 344.0                     # µm/N  (formula default; user may override)
    bl_threshold_pct: float = 0.82

    # ─── Derived / Output Parameters ───
    non_coil_total: float = 0.0
    diaphragm_area: float = 0.0
    diaphragm_mass_calc: float = 0.0
    total_vc_dcr: float = 0.0
    selected_wire_type: str = ""
    length_of_wire: float = 0.0       # m
    number_of_turns: float = 0.0
    coil_winding_max_od: float = 0.0  # mm
    mass_of_former: float = 0.0       # g
    mass_of_wire: float = 0.0         # g
    mass_of_voice_coil: float = 0.0   # g
    wire_dia_with_insulation: float = 0.0  # mm
    resistivity_ohms_per_m: float = 0.0
    length_of_wire_per_turn: float = 0.0   # mm
    ww: float = 0.0

    pole_height: float = 0.0          # mm
    vc_location_diameter: float = 0.0 # mm
    mechanical_xmax: float = 0.0      # mm

    fea_b: float = 0.0                # T
    bl: float = 0.0                   # T·m
    xmax_at_82bl: float = 0.0         # mm
    bl_at_threshold: float = 0.0      # T·m
    max_side_leakage: float = 0.0
    primary_magnet_avg_b: float = 0.0
    secondary_magnet_avg_b: float = 0.0

    splref: float = 0.0               # dB
    qes: float = 0.0
    qts: float = 0.0
    mms_total: float = 0.0            # g
    fs: float = 0.0                   # Hz
    target_sens: float = 0.0          # dB

    interpolated_xmax: float = 0.0    # mm
    xmax_over_10: float = 0.0         # mm
    pct_bl_at_xmax: float = 0.0

    # ─── Arrays / Tables ───
    bl_x_data: list = field(default_factory=list)          # list[(x_mm, BL_Tm)]
    side_leakage_data: list = field(default_factory=list)  # list[float]
    bl_pct_array: list = field(default_factory=list)       # list[float]
    x_array: list = field(default_factory=list)            # list[float]

    def to_dict(self) -> dict:
        """Serialize to plain dict (includes all fields)."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "LoudspeakerDesign":
        """Deserialize from plain dict."""
        # Filter to only known fields
        known = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in known}
        return cls(**filtered)
