"""Tests for calculation engine and Excel formula regression.

Covers: every derived field formula with exact Excel cell references.
All tests use Design 1 default inputs and assert outputs match the
reference spreadsheet to within 1e-6 relative tolerance.
"""

import math

import pytest

from src.api import create_design, recalculate_derived
from src.engine import get_wire_properties, get_former_density


def test_total_vc_dcr_formula_c14():
    """TC-F01: C14 = C12 + C13 (Total VC DCR)."""
    design = create_design()
    design = recalculate_derived(design)
    assert design.total_vc_dcr == pytest.approx(
        design.vc_wire_dcr + design.tinsel_wire_dcr, rel=1e-6
    )
    # Expected: 3.45 + 0.05 = 3.5
    assert design.total_vc_dcr == pytest.approx(3.5, rel=1e-9)


def test_ww_formula_c15():
    """TC-F02: C15 = ROUND(C32*(C27/C20+C20/2-1/2),2) (WW)."""
    design = create_design()
    design = recalculate_derived(design)
    expected = round(
        design.wire_dia_with_insulation
        * (design.number_of_turns / design.number_of_layers
           + design.number_of_layers / 2 - 0.5),
        2,
    )
    assert design.ww == pytest.approx(expected, rel=1e-6)


def test_selected_wire_type_formula_c22():
    """TC-F03: C22 = IF(C21=1,'Copper','CCA')."""
    design = create_design()
    design = recalculate_derived(design)
    assert design.selected_wire_type == "Copper"
    design.wire_type = 2
    design = recalculate_derived(design)
    assert design.selected_wire_type == "CCA"


def test_length_of_wire_formula_c26():
    """TC-F04: C26 = C12/C33 (Length of Wire)."""
    design = create_design()
    design = recalculate_derived(design)
    expected = design.vc_wire_dcr / design.resistivity_ohms_per_m
    assert design.length_of_wire == pytest.approx(expected, rel=1e-6)


def test_number_of_turns_formula_c27():
    """TC-F05: C27 = C12/(C33*C34)*1000 (Number of Turns)."""
    design = create_design()
    design = recalculate_derived(design)
    expected = (
        design.vc_wire_dcr
        / (design.resistivity_ohms_per_m * design.length_of_wire_per_turn)
        * 1000
    )
    assert design.number_of_turns == pytest.approx(expected, rel=1e-6)


def test_coil_winding_max_od_formula_c28():
    """TC-F06: C28 = C16+2*C18+2*C20*C32+C17 (Coil Winding MAX O.D.)."""
    design = create_design()
    design = recalculate_derived(design)
    expected = (
        design.coil_id
        + 2 * design.former_thickness
        + 2 * design.number_of_layers * design.wire_dia_with_insulation
        + design.coil_id_tolerance
    )
    assert design.coil_winding_max_od == pytest.approx(expected, rel=1e-6)


def test_mass_of_former_formula_c29():
    """TC-F07: C29 = (((C16+2*C18)^2-C16^2)*PI()/4*C19)/1000*LOOKUP(...) (Mass of Former)."""
    design = create_design()
    design = recalculate_derived(design)
    inner = design.coil_id + 2 * design.former_thickness
    volume_mm3 = (inner ** 2 - design.coil_id ** 2) * math.pi / 4 * design.former_length
    volume_cm3 = volume_mm3 / 1000
    density = get_former_density(design.former_type)
    expected = volume_cm3 * density
    assert design.mass_of_former == pytest.approx(expected, rel=1e-6)


def test_mass_of_wire_formula_c30():
    """TC-F08: C30 = IF(C21=1,LOOKUP(...,$Y$...),LOOKUP(...,$AA$...))*C26 (Mass of wire)."""
    design = create_design()
    design = recalculate_derived(design)
    props = get_wire_properties(design.wire_diameter, design.wire_type)
    mass_kg_per_km = props["mass_kg_per_km"]
    expected = mass_kg_per_km * design.length_of_wire
    assert design.mass_of_wire == pytest.approx(expected, rel=1e-6)


def test_mass_of_voice_coil_formula_c31():
    """TC-F09: C31 = SUM(C29,C30) (Mass of Voice Coil)."""
    design = create_design()
    design = recalculate_derived(design)
    assert design.mass_of_voice_coil == pytest.approx(
        design.mass_of_former + design.mass_of_wire, rel=1e-6
    )


def test_wire_dia_with_insulation_lookup_c32():
    """TC-F10: C32 = LOOKUP(C$11,$U$8:$U$52,$W$8:$W$52) (Wire Diameter with insulation)."""
    design = create_design()
    design = recalculate_derived(design)
    assert design.wire_dia_with_insulation == pytest.approx(0.542, rel=1e-6)


def test_resistivity_ohms_per_m_formula_c33():
    """TC-F11: C33 = IF(C21=1,LOOKUP(...,$X$...),LOOKUP(...,$Z$...))/1000."""
    design = create_design()
    design = recalculate_derived(design)
    assert design.resistivity_ohms_per_m == pytest.approx(89.95 / 1000, rel=1e-6)


def test_length_of_wire_per_turn_formula_c34():
    """TC-F12: C34 = PI()*(C16+(2*C18)+(C20*C32)) (Length of Wire per Turn)."""
    design = create_design()
    design = recalculate_derived(design)
    expected = math.pi * (
        design.coil_id
        + 2 * design.former_thickness
        + design.number_of_layers * design.wire_dia_with_insulation
    )
    assert design.length_of_wire_per_turn == pytest.approx(expected, rel=1e-6)


def test_top_plate_id_formula_c40():
    """TC-F13: C40 = C28+2*C38 (Top Plate ID)."""
    design = create_design()
    design = recalculate_derived(design)
    expected = design.coil_winding_max_od + 2 * design.outside_gap
    assert design.top_plate_id == pytest.approx(expected, rel=1e-6)


def test_pole_od_formula_c47():
    """TC-F14: C47 = C16-2*C37 (Pole OD)."""
    design = create_design()
    design = recalculate_derived(design)
    expected = design.coil_id - 2 * design.inside_gap
    assert design.pole_od == pytest.approx(expected, rel=1e-6)


def test_pole_height_formula_c59():
    """TC-F15: C59 = C42+C45+C49 (Pole Height)."""
    design = create_design()
    design = recalculate_derived(design)
    expected = (
        design.top_plate_thickness
        + design.magnet_thickness
        + design.pole_overhang
    )
    assert design.pole_height == pytest.approx(expected, rel=1e-6)


def test_vc_location_diameter_formula_c60():
    """TC-F16: C60 = ROUND(((C16+2*C18)+C28)/2,2) (VC location Diameter)."""
    design = create_design()
    design = recalculate_derived(design)
    expected = round(
        ((design.coil_id + 2 * design.former_thickness) + design.coil_winding_max_od)
        / 2,
        2,
    )
    assert design.vc_location_diameter == pytest.approx(expected, rel=1e-6)


def test_mechanical_xmax_formula_c61():
    """TC-F17: C61 = ROUND(C45-(C15-C42)/2+C55,1) (Mechanical Xmax)."""
    design = create_design()
    design = recalculate_derived(design)
    expected = round(
        design.magnet_thickness
        - (design.ww - design.top_plate_thickness) / 2
        + design.vc_offset,
        1,
    )
    assert design.mechanical_xmax == pytest.approx(expected, rel=1e-6)


def test_bl_formula_c65():
    """TC-F18: C65 = ROUND(C64*C26,2) (BL)."""
    design = create_design()
    design.fea_b = 1.234
    design = recalculate_derived(design)
    expected = round(1.234 * design.length_of_wire, 2)
    assert design.bl == pytest.approx(expected, rel=1e-6)


def test_bl_at_threshold_formula_c68():
    """TC-F19: C68 = C65*C66 (Bl @ 82%BLmax)."""
    design = create_design()
    design.fea_b = 1.234
    design = recalculate_derived(design)
    expected = design.bl * design.bl_threshold_pct
    assert design.bl_at_threshold == pytest.approx(expected, rel=1e-6)


def test_splref_formula_c79():
    """TC-F20: C79 = 20*LOG10(C65*C73^2/(SQRT(C14)*(C75+C31)))+57.37 (SPLref)."""
    design = create_design()
    design.fea_b = 1.234
    design = recalculate_derived(design)
    expected = (
        20 * math.log10(
            design.bl * design.speaker_dia ** 2
            / (math.sqrt(design.total_vc_dcr)
               * (design.mms_minus_vcmass + design.mass_of_voice_coil))
        )
        + 57.37
    )
    assert design.splref == pytest.approx(expected, rel=1e-6)


def test_qes_formula_c80():
    """TC-F21: C80 = 31.62*C14/C65^2*SQRT(C82/(5033^2/(C83^2*C82))) (Qes)."""
    design = create_design()
    design.fea_b = 1.234
    design = recalculate_derived(design)
    expected = (
        31.62
        * design.total_vc_dcr
        / design.bl ** 2
        * math.sqrt(
            design.mms_total
            / (5033 ** 2 / (design.fs ** 2 * design.mms_total))
        )
    )
    assert design.qes == pytest.approx(expected, rel=1e-6)


def test_qts_formula_c81():
    """TC-F22: C81 = 1/(1/C80+1/C74) (Qts)."""
    design = create_design()
    design.fea_b = 1.234
    design = recalculate_derived(design)
    expected = 1 / (1 / design.qes + 1 / design.qm)
    assert design.qts == pytest.approx(expected, rel=1e-6)


def test_mms_total_formula_c82():
    """TC-F23: C82 = C75+C31 (Mms)."""
    design = create_design()
    design = recalculate_derived(design)
    expected = design.mms_minus_vcmass + design.mass_of_voice_coil
    assert design.mms_total == pytest.approx(expected, rel=1e-6)


def test_fs_formula_c83():
    """TC-F24: C83 = 1/(2*PI()*SQRT(C82/1000*C76/1000000)) (Fs)."""
    design = create_design()
    design = recalculate_derived(design)
    expected = 1 / (
        2 * math.pi * math.sqrt(design.mms_total / 1000 * design.cms_ls / 1000000)
    )
    assert design.fs == pytest.approx(expected, rel=1e-6)


def test_target_sens_formula_c84():
    """TC-F25: C84 = 10*LOG(0.0544*$J$4^2*($J$7/100^2)^2/(($J$6/1000)^2*$C$14))+92."""
    design = create_design()
    design = recalculate_derived(design)
    expected = (
        10 * math.log10(
            0.0544
            * design.target_bl ** 2
            * (design.target_sd / 100 ** 2) ** 2
            / ((design.target_mms / 1000) ** 2 * design.total_vc_dcr)
        )
        + 92
    )
    assert design.target_sens == pytest.approx(expected, rel=1e-6)


def test_non_coil_total_formula_m8():
    """TC-F26: M8 = SUM(M3:M7) (Non-coil total)."""
    design = create_design()
    design = recalculate_derived(design)
    expected = sum([
        design.mass_diaphragm, design.mass_surround,
        design.mass_dome_coil, design.mass_spider_coil, design.mass_spider,
    ])
    assert design.non_coil_total == pytest.approx(expected, rel=1e-6)


def test_diaphragm_mass_calc_formula_p8():
    """TC-F27: P8 = P4^2*PI()/4*P5/1000*P6 (Mass)."""
    design = create_design()
    design = recalculate_derived(design)
    diameter = design.speaker_dia * 10 - design.target_xmax  # P4
    expected = (
        diameter ** 2 * math.pi / 4
        * design.diaphragm_thickness / 1000
        * design.diaphragm_density
    )
    assert design.diaphragm_mass_calc == pytest.approx(expected, rel=1e-6)


def test_diaphragm_area_formula_p7():
    """TC-F28: P7 = PI()*P4^2/4/100 (Area)."""
    design = create_design()
    design = recalculate_derived(design)
    diameter = design.speaker_dia * 10 - design.target_xmax  # P4
    expected = math.pi * diameter ** 2 / 4 / 100
    assert design.diaphragm_area == pytest.approx(expected, rel=1e-6)


def test_wire_properties_copper():
    """TC-19: JIS 0.5 mm Copper lookup matches reference table."""
    props = get_wire_properties(0.5, 1)
    assert props["max_od_with_insulation"] == pytest.approx(0.542, rel=1e-6)
    assert props["resistance_ohm_per_km"] == pytest.approx(89.95, rel=1e-6)
    assert props["mass_kg_per_km"] == pytest.approx(1.78, rel=1e-6)


def test_wire_properties_cca():
    """TC-19b: JIS 0.5 mm CCA lookup returns correct CCA values."""
    props = get_wire_properties(0.5, 2)
    assert "mass_kg_per_km" in props
    assert "resistance_ohm_per_km" in props
    assert props["resistance_ohm_per_km"] == pytest.approx(130.0, rel=1e-6)
    assert props["mass_kg_per_km"] == pytest.approx(0.8, rel=1e-6)


def test_former_densities():
    """TC-20: All four former types match reference density table."""
    assert get_former_density(1) == pytest.approx(1.43, rel=1e-6)   # Kapton
    assert get_former_density(2) == pytest.approx(2.7, rel=1e-6)    # Aluminum
    assert get_former_density(3) == pytest.approx(1.3, rel=1e-6)    # Nomex
    assert get_former_density(4) == pytest.approx(0.929, rel=1e-6)  # Kraft


def test_recalculate_derived():
    """TC-15: Recalculate Derived Fields — total_vc_dcr updates after tinsel_wire_dcr change."""
    design = create_design()
    design.tinsel_wire_dcr = 0.1
    design = recalculate_derived(design)
    assert design.total_vc_dcr == pytest.approx(3.55, rel=1e-9)
