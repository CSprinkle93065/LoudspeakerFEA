"""Tests for LoudspeakerDesign dataclass integrity.

Covers: construction, default values, field presence (visible and hidden),
JSON serialization round-trip.
"""

import json
from dataclasses import is_dataclass, asdict

import pytest

from src.models import LoudspeakerDesign
from src.api import get_default_values


def test_loudspeaker_design_dataclass_exists():
    """TC-M01: LoudspeakerDesign is a dataclass and can be instantiated."""
    assert is_dataclass(LoudspeakerDesign) is True
    instance = LoudspeakerDesign()
    assert instance is not None


def test_default_values_match_design1():
    """TC-M02: Default field values match Design 1 from the reference spreadsheet."""
    design = get_default_values()
    assert design.wire_diameter == 0.5
    assert design.vc_wire_dcr == 3.45
    assert design.tinsel_wire_dcr == 0.05
    assert design.coil_id == 75.0
    assert design.former_thickness == 0.1
    assert design.former_length == 38.0
    assert design.number_of_layers == 2.0
    assert design.wire_type == 1
    assert design.former_type == 1
    assert design.overhang == pytest.approx(15.82, abs=1e-9)
    assert design.inside_gap == 0.5
    assert design.outside_gap == 0.8
    assert design.top_plate_id == pytest.approx(79.018, abs=1e-9)
    assert design.top_plate_od == 170.0
    assert design.top_plate_thickness == 12.0
    assert design.magnet_id == 90.0
    assert design.magnet_od == 180.0
    assert design.magnet_thickness == 45.0
    assert design.pole_od == pytest.approx(74.0, abs=1e-9)
    assert design.pole_vent_hole == 38.0
    assert design.pole_overhang == 8.0
    assert design.bp_od == 170.0
    assert design.bp_thickness == 14.0
    assert design.vc_offset == -1.0
    assert design.side_leakage_distance == 100.0
    assert design.bl_threshold_pct == 0.82
    assert design.magnet_material == "Ceramic5"
    # Elmer path is auto-detected on this machine where ElmerFEM is installed
    assert design.elmer_solver_path == r"C:\Users\terav\ElmerFEM\bin\ElmerSolver.exe"


def test_all_visible_fields_present():
    """TC-M03: All visible input/output fields exist as attributes."""
    design = get_default_values()
    visible_inputs = [
        "wire_diameter", "vc_wire_dcr", "tinsel_wire_dcr", "coil_id",
        "coil_id_tolerance", "former_thickness", "former_length",
        "number_of_layers", "wire_type", "former_type", "overhang",
        "magnet_material", "inside_gap", "outside_gap", "top_plate_id",
        "top_plate_od", "top_plate_thickness", "magnet_id", "magnet_od",
        "magnet_thickness", "pole_od", "pole_vent_hole", "pole_overhang",
        "bp_od", "bp_thickness", "vc_offset", "side_leakage_distance",
        "bl_threshold_pct", "elmer_solver_path", "working_directory",
        "mesh_size_factor", "show_processor",
    ]
    for field in visible_inputs:
        assert hasattr(design, field), f"Missing visible field: {field}"
    visible_outputs = [
        "total_vc_dcr", "length_of_wire", "number_of_turns",
        "coil_winding_max_od", "mass_of_former", "mass_of_wire",
        "mass_of_voice_coil", "wire_dia_with_insulation",
        "resistivity_ohms_per_m", "length_of_wire_per_turn", "ww",
        "pole_height", "vc_location_diameter", "mechanical_xmax",
        "fea_b", "bl", "xmax_at_82bl", "bl_at_threshold",
        "max_side_leakage", "primary_magnet_avg_b", "secondary_magnet_avg_b",
    ]
    for field in visible_outputs:
        assert hasattr(design, field), f"Missing output field: {field}"


def test_hidden_fields_present_for_backward_compatibility():
    """TC-M04: Hidden fields exist for backward compatibility."""
    design = get_default_values()
    hidden_fields = [
        "bucking_mag_id", "bucking_mag_od", "bucking_mag_thickness",
        "target_bl", "target_cms", "target_mms", "target_sd", "target_xmax",
        "mass_diaphragm", "mass_surround", "mass_dome_coil",
        "mass_spider_coil", "mass_spider", "diaphragm_thickness",
        "diaphragm_density", "speaker_dia", "qm", "mms_minus_vcmass",
        "cms_ls", "selected_wire_type", "interpolated_xmax",
        "xmax_over_10", "pct_bl_at_xmax", "splref", "qes", "qts",
        "mms_total", "fs", "target_sens", "non_coil_total",
        "diaphragm_area", "diaphragm_mass_calc",
        "bl_x_data", "side_leakage_data", "bl_pct_array", "x_array",
    ]
    for field in hidden_fields:
        assert hasattr(design, field), f"Missing hidden field: {field}"
    assert design.bucking_mag_id == 0.0
    assert design.bucking_mag_od == 0.0
    assert design.bucking_mag_thickness == 0.0
    assert design.target_bl == 8.0


def test_json_serialization_roundtrip():
    """TC-M05: Design can be serialized to dict and reconstructed."""
    design = get_default_values()
    d = asdict(design)
    json_str = json.dumps(d)
    loaded_dict = json.loads(json_str)
    assert loaded_dict["wire_diameter"] == 0.5
    assert loaded_dict["magnet_material"] == "Ceramic5"
    # Round-trip through from_dict
    restored = LoudspeakerDesign.from_dict(loaded_dict)
    assert restored.wire_diameter == 0.5
    assert restored.magnet_material == "Ceramic5"
