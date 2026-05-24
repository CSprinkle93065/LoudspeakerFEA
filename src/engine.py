"""Calculation engine for LoudspeakerFEA.

All formulas are implemented exactly as specified in the FEMotor spreadsheet.
No algebraic simplifications or substitutions are performed.
"""

from __future__ import annotations

import math
from bisect import bisect_right
from typing import List

from src.models import LoudspeakerDesign


# ─── Reference Data: JIS Wire Gauge (columns U–AA, rows 8–52) ────────────────
# Columns: diameter(mm), tolerance, max_od_with_insulation, copper_resistance_ohm_per_km,
#          copper_mass_kg_per_km, cca_resistance_ohm_per_km, cca_mass_kg_per_km
_WIRE_GAUGE_TABLE: List[tuple] = [
    (0.02, 0.002, 0.03, 69850.0, 0.0028, None, None),
    (0.025, 0.002, 0.037, 42780.0, 0.0049, None, None),
    (0.03, 0.002, 0.044, 28870.0, 0.007, None, None),
    (0.04, 0.002, 0.056, 15670.0, 0.012, None, None),
    (0.05, 0.003, 0.069, 10240.0, 0.02, None, None),
    (0.06, 0.003, 0.081, 6966.0, 0.027, 9040.0, 0.013),
    (0.07, 0.003, 0.091, 4990.0, 0.036, 6630.0, 0.017),
    (0.08, 0.003, 0.103, 3778.0, 0.048, 5080.0, 0.022),
    (0.09, 0.003, 0.113, 2959.0, 0.06, 4020.0, 0.028),
    (0.1, 0.003, 0.125, 2381.0, 0.074, 3250.0, 0.034),
    (0.11, 0.003, 0.135, 1957.0, 0.089, 2690.0, 0.041),
    (0.12, 0.003, 0.147, 1636.0, 0.11, 2260.0, 0.049),
    (0.13, 0.003, 0.157, 1389.0, 0.12, 1920.0, 0.057),
    (0.14, 0.003, 0.167, 1193.0, 0.14, 1660.0, 0.066),
    (0.15, 0.003, 0.177, 1037.0, 0.16, 1440.0, 0.075),
    (0.16, 0.003, 0.189, 908.8, 0.19, 1270.0, 0.086),
    (0.17, 0.003, 0.199, 803.2, 0.21, 1120.0, 0.096),
    (0.18, 0.003, 0.211, 715.0, 0.24, 1000.0, 0.1),
    (0.19, 0.003, 0.221, 640.6, 0.26, 900.0, 0.12),
    (0.2, 0.003, 0.231, 577.2, 0.29, 812.0, 0.13),
    (0.21, 0.003, 0.241, 522.8, 0.32, 737.0, 0.15),
    (0.22, 0.004, 0.252, 480.1, 0.35, 672.0, 0.16),
    (0.23, 0.004, 0.264, 438.6, 0.38, 613.0, 0.17),
    (0.24, 0.004, 0.274, 402.2, 0.42, 564.0, 0.19),
    (0.25, 0.004, 0.284, 370.2, 0.45, 520.0, 0.2),
    (0.26, 0.004, 0.294, 341.8, 0.49, 482.0, 0.22),
    (0.27, 0.004, 0.304, 316.6, 0.52, 446.0, 0.24),
    (0.28, 0.004, 0.314, 294.1, 0.57, 415.0, 0.25),
    (0.29, 0.004, 0.324, 273.9, 0.6, 387.0, 0.27),
    (0.3, 0.005, 0.337, 254.0, 0.65, 361.0, 0.29),
    (0.32, 0.005, 0.357, 222.8, 0.73, 318.0, 0.33),
    (0.35, 0.005, 0.387, 187.5, 0.88, 265.0, 0.39),
    (0.37, 0.005, 0.407, 165.9, 0.98, 238.0, 0.44),
    (0.4, 0.005, 0.439, 141.7, 1.14, 203.0, 0.52),
    (0.45, 0.006, 0.49, 112.1, 1.44, 160.625, None),
    (0.5, 0.012, 0.542, 89.95, 1.78, 130.0, 0.8),
    (0.55, 0.012, 0.592, 74.18, 2.15, 107.625, None),
    (0.6, 0.012, 0.644, 62.64, 2.56, 90.25, 1.16),
    (0.65, 0.012, 0.694, 53.26, 3.0, None, None),
    (0.7, 0.013, 0.746, 45.84, 3.47, 66.25, None),
    (0.75, 0.014, 0.798, 39.87, 3.99, None, None),
    (0.8, 0.015, 0.852, 35.17, 4.54, 50.75, None),
    (0.85, 0.015, 0.904, 31.11, 5.12, None, None),
    (0.9, 0.016, 0.956, 27.71, 5.74, 40.15625, None),
]

_WIRE_DIAMETERS = [row[0] for row in _WIRE_GAUGE_TABLE]


# ─── Reference Data: Former Material Density ─────────────────────────────────
# Columns V–Y, rows 55–57
_FORMER_DENSITIES = {
    1: 1.43,   # Kapton
    2: 2.7,    # Aluminum
    3: 1.3,    # Nomex
    4: 0.929,  # Kraft
}


# ─── Reference Data: Magnet Materials ────────────────────────────────────────
MAGNET_MATERIALS = [
    "Ceramic5",
    "NdFe38",
    "NdFe48",
    "NdFe35",
    "NdFe38 High Temp",
    "NdFe39 Super High Temp",
    "NdFe38 Ultra High Temp",
]


def _lookup_wire_row(wire_diameter: float) -> tuple:
    """Excel-style LOOKUP for the largest wire diameter <= lookup value."""
    idx = bisect_right(_WIRE_DIAMETERS, wire_diameter) - 1
    if idx < 0:
        idx = 0
    return _WIRE_GAUGE_TABLE[idx]


def get_wire_properties(wire_diameter: float, wire_type: int) -> dict:
    """Look up wire gauge table and return properties dict.

    Keys: max_od_with_insulation, resistance_ohm_per_km, mass_kg_per_km.
    """
    row = _lookup_wire_row(wire_diameter)
    _, _, max_od, cu_r, cu_mass, cca_r, cca_mass = row
    if wire_type == 1:
        return {
            "max_od_with_insulation": max_od,
            "resistance_ohm_per_km": cu_r,
            "mass_kg_per_km": cu_mass,
        }
    else:
        return {
            "max_od_with_insulation": max_od,
            "resistance_ohm_per_km": cca_r if cca_r is not None else 0.0,
            "mass_kg_per_km": cca_mass if cca_mass is not None else 0.0,
        }


def get_former_density(former_type: int) -> float:
    """Return the density (g/cm³) for the given former type ID."""
    return _FORMER_DENSITIES.get(former_type, 1.43)


def recalculate_derived(design: LoudspeakerDesign) -> LoudspeakerDesign:
    """Recompute every derived field using the exact Excel formulas.

    Does NOT call Elmer.  Formula-default input fields (overhang, top_plate_id,
    pole_od, speaker_dia, mms_minus_vcmass, cms_ls) are treated as user-editable
    inputs and are NOT overwritten by this function.
    """
    # ─── A.6 Non-Coil Mass ──────────────────────────────────────────────
    # M8 = SUM(M3:M7)
    design.non_coil_total = (
        design.mass_diaphragm
        + design.mass_surround
        + design.mass_dome_coil
        + design.mass_spider_coil
        + design.mass_spider
    )

    # P4 = C73*10-J8
    p4 = design.speaker_dia * 10.0 - design.target_xmax
    # P7 = PI()*P4^2/4/100
    design.diaphragm_area = math.pi * (p4 ** 2) / 4.0 / 100.0
    # P8 = P4^2*PI()/4*P5/1000*P6
    design.diaphragm_mass_calc = (
        (p4 ** 2) * math.pi / 4.0 * design.diaphragm_thickness / 1000.0 * design.diaphragm_density
    )

    # ─── A.1 Voice Coil Calculations ────────────────────────────────────
    # C32 = LOOKUP(C$11,$U$8:$U$52,$W$8:$W$52)
    wire_row = _lookup_wire_row(design.wire_diameter)
    design.wire_dia_with_insulation = wire_row[2]

    # C33 = IF(C21=1,LOOKUP(...,$X$...),LOOKUP(...,$Z$...))/1000
    if design.wire_type == 1:
        design.resistivity_ohms_per_m = wire_row[3] / 1000.0
    else:
        design.resistivity_ohms_per_m = (wire_row[5] if wire_row[5] is not None else 0.0) / 1000.0

    # C34 = PI()*(C16+(2*C18)+(C20*C32))
    design.length_of_wire_per_turn = (
        math.pi * (design.coil_id + (2.0 * design.former_thickness) + (design.number_of_layers * design.wire_dia_with_insulation))
    )

    # C26 = C12/C33
    design.length_of_wire = design.vc_wire_dcr / design.resistivity_ohms_per_m

    # C27 = C12/(C33*C34)*1000
    design.number_of_turns = design.vc_wire_dcr / (design.resistivity_ohms_per_m * design.length_of_wire_per_turn) * 1000.0

    # C28 = C16+2*C18+2*C20*C32+C17
    design.coil_winding_max_od = (
        design.coil_id
        + 2.0 * design.former_thickness
        + 2.0 * design.number_of_layers * design.wire_dia_with_insulation
        + design.coil_id_tolerance
    )

    # C14 = C12+C13
    design.total_vc_dcr = design.vc_wire_dcr + design.tinsel_wire_dcr

    # C15 = ROUND(C32*(C27/C20+C20/2-1/2),2)
    design.ww = round(
        design.wire_dia_with_insulation * (design.number_of_turns / design.number_of_layers + design.number_of_layers / 2.0 - 0.5),
        2,
    )

    # C22 = IF(C21=1,"Copper","CCA")
    design.selected_wire_type = "Copper" if design.wire_type == 1 else "CCA"

    # C29 = (((C16+2*C18)^2-C16^2)*PI()/4*C19)/1000*LOOKUP(C23,$V$55:$Y$55,$V$57:$Y$57)
    former_density = _FORMER_DENSITIES.get(design.former_type, 1.43)
    design.mass_of_former = (
        (
            ((design.coil_id + 2.0 * design.former_thickness) ** 2 - design.coil_id ** 2)
            * math.pi
            / 4.0
            * design.former_length
        )
        / 1000.0
        * former_density
    )

    # C30 = IF(C21=1,LOOKUP(C$11,$U$8:$U$52,$Y$8:$Y$52),LOOKUP(C$11,$U$8:$U$52,$AA$8:$AA$52))*C26
    if design.wire_type == 1:
        wire_mass_per_km = wire_row[4]
    else:
        wire_mass_per_km = wire_row[6] if wire_row[6] is not None else 0.0
    design.mass_of_wire = wire_mass_per_km * design.length_of_wire

    # C31 = SUM(C29,C30)
    design.mass_of_voice_coil = design.mass_of_former + design.mass_of_wire

    # ─── A.2 Motor Geometry ─────────────────────────────────────────────
    # C40 = C28+2*C38
    # (top_plate_id is a formula-default input; we do NOT overwrite it here)

    # C47 = C16-2*C37
    # (pole_od is a formula-default input; we do NOT overwrite it here)

    # C59 = C42+C45+C49
    design.pole_height = design.top_plate_thickness + design.magnet_thickness + design.pole_overhang

    # C60 = ROUND(((C16+2*C18)+C28)/2,2)
    design.vc_location_diameter = round(
        ((design.coil_id + 2.0 * design.former_thickness) + design.coil_winding_max_od) / 2.0,
        2,
    )

    # C61 = ROUND(C45-(C15-C42)/2+C55,1)
    design.mechanical_xmax = round(
        design.magnet_thickness - (design.ww - design.top_plate_thickness) / 2.0 + design.vc_offset,
        1,
    )

    # ─── A.3 FEA-Derived Outputs ────────────────────────────────────────
    # C65 = ROUND(C64*C26,2)
    design.bl = round(design.fea_b * design.length_of_wire, 2)

    # C68 = C65*C66
    design.bl_at_threshold = design.bl * design.bl_threshold_pct

    # C69 = MAX(C218:C317)
    if design.side_leakage_data:
        design.max_side_leakage = max(design.side_leakage_data)
    else:
        design.max_side_leakage = 0.0

    # ─── A.5 Xmax Interpolation ─────────────────────────────────────────
    # C86 = IF(C154>C66,(ABS(C91)+C151)/2,ABS(...))
    # C88 = IF(C154>C66,(C154+C214)/2,C66)
    if design.bl_pct_array and design.x_array and len(design.bl_pct_array) > 0 and len(design.x_array) > 0:
        first_bl_pct = design.bl_pct_array[0]
        last_bl_pct = design.bl_pct_array[-1]
        first_x = design.x_array[0]
        last_x = design.x_array[-1]

        if first_bl_pct > design.bl_threshold_pct:
            # (ABS(C91)+C151)/2
            design.interpolated_xmax = (abs(first_x) + last_x) / 2.0
            # (C154+C214)/2
            design.pct_bl_at_xmax = (first_bl_pct + last_bl_pct) / 2.0
        else:
            # Interpolation branch
            design.interpolated_xmax = _interpolate_xmax(
                design.bl_threshold_pct,
                design.bl_pct_array,
                design.x_array,
            )
            design.pct_bl_at_xmax = design.bl_threshold_pct
    else:
        design.interpolated_xmax = 0.0
        design.pct_bl_at_xmax = design.bl_threshold_pct

    # C87 = C86/10
    design.xmax_over_10 = design.interpolated_xmax / 10.0

    # C67 = ROUND(C86,2)
    design.xmax_at_82bl = round(design.interpolated_xmax, 2)

    # ─── A.4 Loudspeaker Parameters ─────────────────────────────────────
    # C82 = C75+C31
    design.mms_total = design.mms_minus_vcmass + design.mass_of_voice_coil

    # C83 = 1/(2*PI()*SQRT(C82/1000*C76/1000000))
    if design.mms_total > 0 and design.cms_ls > 0:
        design.fs = 1.0 / (2.0 * math.pi * math.sqrt(design.mms_total / 1000.0 * design.cms_ls / 1000000.0))
    else:
        design.fs = 0.0

    # C79 = 20*LOG10(C65*C73^2/(SQRT(C14)*(C75+C31)))+57.37
    if design.bl > 0 and design.total_vc_dcr > 0 and (design.mms_minus_vcmass + design.mass_of_voice_coil) > 0:
        design.splref = (
            20.0 * math.log10(
                design.bl * (design.speaker_dia ** 2)
                / (math.sqrt(design.total_vc_dcr) * (design.mms_minus_vcmass + design.mass_of_voice_coil))
            )
            + 57.37
        )
    else:
        design.splref = 0.0

    # C80 = 31.62*C14/C65^2*SQRT(C82/(5033^2/(C83^2*C82)))
    if design.bl > 0 and design.fs > 0 and design.mms_total > 0:
        design.qes = (
            31.62
            * design.total_vc_dcr
            / (design.bl ** 2)
            * math.sqrt(design.mms_total / ((5033.0 ** 2) / ((design.fs ** 2) * design.mms_total)))
        )
    else:
        design.qes = 0.0

    # C81 = 1/(1/C80+1/C74)
    if design.qes > 0 and design.qm > 0:
        design.qts = 1.0 / (1.0 / design.qes + 1.0 / design.qm)
    else:
        design.qts = 0.0

    # C84 = 10*LOG(0.0544*$J$4^2*($J$7/100^2)^2/(($J$6/1000)^2*$C$14))+92
    if design.total_vc_dcr > 0:
        design.target_sens = (
            10.0 * math.log10(
                0.0544
                * (design.target_bl ** 2)
                * ((design.target_sd / (100.0 ** 2)) ** 2)
                / (((design.target_mms / 1000.0) ** 2) * design.total_vc_dcr)
            )
            + 92.0
        )
    else:
        design.target_sens = 0.0

    return design


def _interpolate_xmax(threshold: float, bl_pct_array: list, x_array: list) -> float:
    """Excel-style interpolation for C86.

    =ABS(
        (INDEX(bl_pct_array, MATCH(threshold, bl_pct_array)) - threshold)
        / (INDEX(bl_pct_array, MATCH(threshold, bl_pct_array)) - INDEX(bl_pct_array, MATCH(threshold, bl_pct_array)+1))
        * (INDEX(x_array, MATCH(threshold, bl_pct_array)+1) - INDEX(x_array, MATCH(threshold, bl_pct_array)))
        + INDEX(x_array, MATCH(threshold, bl_pct_array))
    )
    """
    # Excel MATCH with default match_type=1 finds the largest value <= lookup_value.
    # The array must be in ascending order for this mode.
    match_idx = _excel_match(threshold, bl_pct_array)
    if match_idx is None or match_idx >= len(bl_pct_array) - 1:
        return 0.0

    idx1 = match_idx
    idx2 = match_idx + 1

    b1 = bl_pct_array[idx1]
    b2 = bl_pct_array[idx2]
    x1 = x_array[idx1]
    x2 = x_array[idx2]

    if abs(b1 - b2) < 1e-15:
        return abs(x1)

    result = abs(
        (b1 - threshold) / (b1 - b2) * (x2 - x1) + x1
    )
    return result


def _excel_match(lookup_value: float, array: list) -> int | None:
    """Excel MATCH(match_type=1): largest value <= lookup_value. Returns 0-based index or None."""
    idx = None
    for i, val in enumerate(array):
        if val <= lookup_value:
            idx = i
        else:
            break
    return idx


def initialize_formula_defaults(design: LoudspeakerDesign) -> LoudspeakerDesign:
    """Set formula-default input fields to their computed values.

    Called once by create_design() to initialise a fresh design.
    """
    # C24 = (C15-C42)/2  → overhang
    # But C15 depends on C32/C27 which depend on wire lookup.  Compute those first.
    design = recalculate_derived(design)

    # C24 = (C15-C42)/2
    design.overhang = (design.ww - design.top_plate_thickness) / 2.0

    # C40 = C28+2*C38
    design.top_plate_id = design.coil_winding_max_od + 2.0 * design.outside_gap

    # C47 = C16-2*C37
    design.pole_od = design.coil_id - 2.0 * design.inside_gap

    # C73 = SQRT(4*J7/PI())
    design.speaker_dia = math.sqrt(4.0 * design.target_sd / math.pi)

    # C75 = M8
    design.mms_minus_vcmass = design.non_coil_total

    # C76 = J5
    design.cms_ls = design.target_cms

    # side_leakage_distance remains a user-editable input (default 100.0 mm)

    # Recompute derived fields now that formula-default inputs are set
    design = recalculate_derived(design)
    return design
