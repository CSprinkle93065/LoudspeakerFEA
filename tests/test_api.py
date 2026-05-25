"""Tests for API lifecycle functions.

Covers: create, clone, save, load, delete, list, switch, compare, defaults,
update parameter, export, settings, and UI-only negative test.
"""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

import src.api as api_module
from src.api import (
    create_design, save_design, load_design, delete_design, list_designs,
    clone_design, switch_active_design, compare_designs, get_default_values,
    update_design_parameter, recalculate_derived,
    export_blx_csv, export_side_leakage_csv, export_results_json,
    set_elmer_executable_path, set_working_directory, init_database,
    run_elmer_simulation,
)


def test_update_design_parameter(tmp_path: Path):
    """TC-01: Change / Update Input Parameter — field updated and derived values recalculated."""
    init_database(str(tmp_path / "test.db"))
    design = create_design()
    design = update_design_parameter(design, "top_plate_thickness", 15.0)
    assert design.top_plate_thickness == 15.0
    assert design.pole_height == 68.0  # 15 + 45 + 8


def test_create_design(tmp_path: Path):
    """TC-03: New Design — create_design returns LoudspeakerDesign with Design 1 defaults."""
    init_database(str(tmp_path / "test.db"))
    design = create_design(name="TestDesign")
    assert design.name == "TestDesign"
    assert design.wire_diameter == 0.5
    assert design.magnet_material == "Ceramic5"


def test_save_design(tmp_path: Path):
    """TC-04: Save Design — returns integer primary key > 0."""
    init_database(str(tmp_path / "test.db"))
    design = create_design(name="SaveTest")
    design_id = save_design(design)
    assert isinstance(design_id, int)
    assert design_id > 0


def test_load_design(tmp_path: Path):
    """TC-05: Load Design — retrieved design matches saved design."""
    init_database(str(tmp_path / "test.db"))
    design = create_design(name="LoadTest")
    design_id = save_design(design)
    loaded = load_design(design_id)
    assert loaded.name == design.name
    assert loaded.wire_diameter == design.wire_diameter
    assert loaded.magnet_material == design.magnet_material


def test_delete_design(tmp_path: Path):
    """TC-06: Delete Design — design removed from database."""
    init_database(str(tmp_path / "test.db"))
    design = create_design(name="DeleteTest")
    design_id = save_design(design)
    delete_design(design_id)
    designs = list_designs()
    assert design_id not in [d["id"] for d in designs]


def test_clone_design(tmp_path: Path):
    """TC-16: Clone Design — deep copy with new name, not yet saved."""
    init_database(str(tmp_path / "test.db"))
    design = create_design(name="Original")
    design_id = save_design(design)
    cloned = clone_design(design_id, new_name="Clone")
    assert cloned.name == "Clone"
    assert cloned.wire_diameter == design.wire_diameter
    assert getattr(cloned, "id", None) is None


def test_list_designs(tmp_path: Path):
    """TC-17: List Designs — returns list of dicts with id, name, updated_at."""
    init_database(str(tmp_path / "test.db"))
    design = create_design(name="ListTest")
    design_id = save_design(design)
    designs = list_designs()
    assert isinstance(designs, list)
    assert any(d["id"] == design_id for d in designs)
    assert all({"id", "name", "updated_at"} <= set(d.keys()) for d in designs)


def test_switch_active_design():
    """TC-10: Switch Active Design — slot initialized with defaults when empty."""
    api_module._active_slots.clear()
    design = switch_active_design(slot=2)
    assert design.wire_diameter == 0.5
    assert design.magnet_material == "Ceramic5"


def test_compare_designs(tmp_path: Path):
    """TC-11: Compare Designs — dict of metrics keyed by design ID."""
    init_database(str(tmp_path / "test.db"))
    d1 = create_design(name="D1")
    id1 = save_design(d1)
    d2 = create_design(name="D2")
    id2 = save_design(d2)
    result = compare_designs([id1, id2])
    assert len(result) == 2
    assert all(isinstance(result[did], dict) and "Bl" in result[did] for did in [id1, id2])


def test_export_blx_csv(tmp_path: Path):
    """TC-07: Export BL(x) CSV — file created with correct headers and data rows."""
    design = create_design()
    design.bl_x_data = [(-10.0, 6.5), (0.0, 8.0), (10.0, 6.5)]
    filepath = tmp_path / "blx.csv"
    export_blx_csv(design, str(filepath))
    content = filepath.read_text()
    assert "x_mm,BL_Tm" in content
    assert "-10.0,6.5" in content


def test_export_side_leakage_csv(tmp_path: Path):
    """TC-08: Export Side Leakage CSV — file created with correct headers and data rows."""
    design = create_design()
    design.side_leakage_data = [0.1, 0.2, 0.3]
    filepath = tmp_path / "leakage.csv"
    export_side_leakage_csv(design, str(filepath))
    content = filepath.read_text()
    assert "index,leakage_G" in content
    assert "0,0.1" in content


def test_export_results_json(tmp_path: Path):
    """TC-09: Export Results Summary — JSON file contains all input and output fields."""
    design = create_design(name="ExportTest")
    filepath = tmp_path / "results.json"
    export_results_json(design, str(filepath))
    data = json.loads(filepath.read_text())
    assert data["name"] == "ExportTest"
    assert "wire_diameter" in data
    assert "total_vc_dcr" in data
    assert "pole_height" in data


def test_set_elmer_executable_path(tmp_path: Path):
    """TC-12: Set Elmer Path — global setting persisted without error."""
    db_path = tmp_path / "test.db"
    init_database(str(db_path))
    result = set_elmer_executable_path(r"C:\ElmerFEM\bin\ElmerSolver.exe")
    assert result is None


def test_set_working_directory(tmp_path: Path):
    """TC-13: Set Working Directory — global setting persisted without error."""
    db_path = tmp_path / "test.db"
    init_database(str(db_path))
    result = set_working_directory(r"C:\ElmerFEA")
    assert result is None


def test_view_about_has_no_api():
    """TC-14: View About — verify no API function exists for this UI-only action."""
    assert not hasattr(api_module, "show_about")


def test_recalculate_derived():
    """TC-15: Recalculate Derived Fields — total_vc_dcr updates after tinsel_wire_dcr change."""
    design = create_design()
    design.tinsel_wire_dcr = 0.1
    design = recalculate_derived(design)
    assert design.total_vc_dcr == pytest.approx(3.55, rel=1e-9)


def test_get_default_values(tmp_path: Path):
    """TC-18: Get Default Values — matches Design 1 reference defaults."""
    init_database(str(tmp_path / "test.db"))
    defaults = get_default_values()
    assert defaults.wire_diameter == 0.5
    assert defaults.magnet_material == "Ceramic5"
    assert defaults.bl_threshold_pct == 0.82
    assert defaults.target_bl == 8.0


def test_run_elmer_simulation_mocked(tmp_path: Path):
    """TC-02: Run Elmer Simulation — mocked; design fields populated from synthetic output."""
    design = create_design()
    design.working_directory = str(tmp_path)
    # Pre-create synthetic Elmer output files
    vc_file = tmp_path / "VCSweepOutput.txt"
    vc_content = (
        "B(x=0) = 1.234\n"
        "dataPoints = 61\n"
        "Bmagnet = 0.987\n"
        "VC Position  B_avg\n"
    )
    for i in range(61):
        vc_content += f"{i-30}  {1.234 + i * 0.001}\n"
    vc_content += "B(x) dataPoints\n"
    vc_file.write_text(vc_content)
    leak_file = tmp_path / "leakage contour.txt"
    leak_file.write_text("\n".join(str(0.01 * i) for i in range(100)))
    mock_parsed = {
        "b_at_zero": 1.234,
        "data_points": 61,
        "bmagnet": 0.987,
        "bbuck": 0.0,
        "vc_sweep": [(float(i - 30), 1.234 + i * 0.001) for i in range(61)],
        "raw_b": [(float(i - 30), 1.234 + i * 0.001) for i in range(61)],
        "side_leakage": [0.01 * i for i in range(100)],
    }
    with patch("src.elmer_integration.build_geometry") as mock_build, \
         patch("src.elmer_integration.build_and_solve") as mock_solve, \
         patch("src.elmer_integration.extract_vc_sweep") as mock_vc, \
         patch("src.elmer_integration.extract_side_leakage") as mock_leak, \
         patch("src.elmer_integration.write_output_files"), \
         patch("src.elmer_integration.generate_density_plot"), \
         patch("src.elmer_integration.parse_elmer_output") as mock_parse:
        mock_build.return_value = str(tmp_path / "motor.msh")
        mock_solve.return_value = tmp_path / "case.vtu"
        mock_vc.return_value = mock_parsed
        mock_leak.return_value = mock_parsed["side_leakage"]
        mock_parse.return_value = mock_parsed
        design = run_elmer_simulation(design, show_window=False)
    assert design.fea_b is not None
    assert len(design.bl_x_data) == 61
    assert len(design.side_leakage_data) == 100
