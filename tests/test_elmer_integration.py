"""Tests for Elmer integration API functions.

Covers: parse_elmer_output, run_elmer_simulation (mocked pipeline),
error handling, and bug-fix verification.

All subprocess and file-system calls are mocked — no Elmer installation required.
"""

import inspect
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from src.api import (
    create_design, run_elmer_simulation,
    parse_elmer_output,
)


def test_parse_elmer_output(tmp_path: Path):
    """TC-22: Parse Elmer Output — extracts b_at_zero, magnet B, sweep arrays."""
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
    result = parse_elmer_output(str(tmp_path))
    assert result["b_at_zero"] == pytest.approx(1.234, rel=1e-6)
    assert result["bmagnet"] == pytest.approx(0.987, rel=1e-6)
    assert len(result["vc_sweep"]) == 61
    assert len(result["side_leakage"]) == 100


def test_run_elmer_simulation_mocked(tmp_path: Path):
    """TC-02: Run Elmer Simulation — mocked pipeline; design fields populated."""
    design = create_design()
    design.working_directory = str(tmp_path)

    mock_vc_results = {
        "b_at_zero": 1.234,
        "data_points": 61,
        "bmagnet": 0.987,
        "bbuck": 0.0,
        "vc_sweep": [(float(i - 30), 1.234 + i * 0.001) for i in range(61)],
        "raw_b": [(float(i - 30), 1.234 + i * 0.001) for i in range(61)],
    }
    mock_side_leakage = [0.01 * i for i in range(100)]
    mock_parsed = {
        "b_at_zero": 1.234,
        "data_points": 61,
        "bmagnet": 0.987,
        "bbuck": 0.0,
        "vc_sweep": mock_vc_results["vc_sweep"],
        "raw_b": mock_vc_results["raw_b"],
        "side_leakage": mock_side_leakage,
    }

    with patch("src.elmer_integration.build_geometry") as mock_build_geometry, \
         patch("src.elmer_integration.build_and_solve") as mock_build_and_solve, \
         patch("src.elmer_integration.extract_vc_sweep") as mock_extract_vc_sweep, \
         patch("src.elmer_integration.extract_side_leakage") as mock_extract_side_leakage, \
         patch("src.elmer_integration.write_output_files") as mock_write_output_files, \
         patch("src.elmer_integration.generate_density_plot") as mock_density_plot, \
         patch("src.elmer_integration.parse_elmer_output") as mock_parse_output:

        mock_build_geometry.return_value = str(tmp_path / "motor.msh")
        mock_build_and_solve.return_value = tmp_path / "case.vtu"
        mock_extract_vc_sweep.return_value = mock_vc_results
        mock_extract_side_leakage.return_value = mock_side_leakage
        mock_parse_output.return_value = mock_parsed

        result = run_elmer_simulation(design, show_window=False)

    assert result.fea_b is not None
    assert len(result.bl_x_data) == 61
    assert len(result.side_leakage_data) == 100
    assert result.primary_magnet_avg_b is not None
    assert result.bl is not None
    assert result.bl > 0


def test_missing_elmer_executable_raises(tmp_path: Path):
    """TC-E06: run_elmer_simulation raises when solver executable is invalid."""
    design = create_design()
    design.elmer_solver_path = r"C:\NonExistent\ElmerSolver.exe"
    with patch("src.elmer_integration.build_geometry") as mock_build, \
         patch("src.elmer_integration.build_and_solve") as mock_solve:
        mock_build.return_value = str(tmp_path / "motor.msh")
        mock_solve.side_effect = FileNotFoundError("ElmerSolver not found")
        with pytest.raises((RuntimeError, FileNotFoundError)):
            run_elmer_simulation(design)


def test_missing_output_files_raises(tmp_path: Path):
    """TC-E07: parse_elmer_output raises when expected files are missing."""
    with pytest.raises(FileNotFoundError):
        parse_elmer_output(str(tmp_path))


def test_secondary_magnet_avg_b_is_na(tmp_path: Path):
    """TC-E08: Secondary magnet average B is N/A or 0 (no bucking magnet)."""
    design = create_design()
    assert design.secondary_magnet_avg_b in ("N/A", 0, 0.0)
    # After mocked simulation it should be "N/A"
    design.working_directory = str(tmp_path)

    mock_parsed = {
        "b_at_zero": 1.0,
        "data_points": 1,
        "bmagnet": 1.0,
        "bbuck": 0.0,
        "vc_sweep": [(0.0, 1.0)],
        "raw_b": [(0.0, 1.0)],
        "side_leakage": [0.01],
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

    assert design.secondary_magnet_avg_b == "N/A"


# ─── Bug-fix verification tests (wvc_20260524_175500) ────────────────────────


def test_no_fake_mesh_placeholders():
    """Verify the old fake-mesh placeholder (zero nodes/elements) is gone."""
    import src.elmer_integration as ei
    source = Path(ei.__file__).read_text(encoding="utf-8")
    # Old fake mesh wrote "0\n" to mesh.header, mesh.nodes, mesh.elements, mesh.boundary
    assert "mesh.header" not in source, "Fake mesh.header placeholder still present"
    assert "mesh.nodes" not in source, "Fake mesh.nodes placeholder still present"
    assert "mesh.elements" not in source, "Fake mesh.elements placeholder still present"
    assert "mesh.boundary" not in source, "Fake mesh.boundary placeholder still present"


def test_real_pipeline_modules_importable():
    """Verify geometry_builder, elmer_solver, post_processor, materials import."""
    import src.geometry_builder as gb
    import src.elmer_solver as es
    import src.post_processor as pp
    import src.materials as mat

    assert hasattr(gb, "build_geometry")
    assert hasattr(es, "build_and_solve")
    assert hasattr(es, "generate_sif")
    assert hasattr(pp, "extract_vc_sweep")
    assert hasattr(pp, "extract_side_leakage")
    assert hasattr(pp, "write_output_files")
    assert hasattr(pp, "generate_density_plot")
    assert hasattr(mat, "load_material")
    assert hasattr(mat, "_bh_to_mur_h")


def test_run_elmer_simulation_signature_preserved():
    """API contract: run_elmer_simulation(design, show_window=False) exists."""
    sig = inspect.signature(run_elmer_simulation)
    params = list(sig.parameters.keys())
    assert "design" in params
    assert "show_window" in params
    assert sig.parameters["show_window"].default is False


def test_run_elmer_simulation_calls_real_pipeline(tmp_path: Path):
    """Mock test: verify run_elmer_simulation calls the real pipeline functions."""
    design = create_design()
    design.working_directory = str(tmp_path)

    mock_vc_results = {
        "b_at_zero": 1.234,
        "data_points": 61,
        "bmagnet": 0.987,
        "bbuck": 0.0,
        "vc_sweep": [(float(i - 30), 1.234 + i * 0.001) for i in range(61)],
        "raw_b": [(float(i - 30), 1.234 + i * 0.001) for i in range(61)],
    }
    mock_side_leakage = [0.01 * i for i in range(100)]
    mock_parsed = {
        "b_at_zero": 1.234,
        "data_points": 61,
        "bmagnet": 0.987,
        "bbuck": 0.0,
        "vc_sweep": mock_vc_results["vc_sweep"],
        "raw_b": mock_vc_results["raw_b"],
        "side_leakage": mock_side_leakage,
    }

    with patch("src.elmer_integration.build_geometry") as mock_build_geometry, \
         patch("src.elmer_integration.build_and_solve") as mock_build_and_solve, \
         patch("src.elmer_integration.extract_vc_sweep") as mock_extract_vc_sweep, \
         patch("src.elmer_integration.extract_side_leakage") as mock_extract_side_leakage, \
         patch("src.elmer_integration.write_output_files") as mock_write_output_files, \
         patch("src.elmer_integration.generate_density_plot") as mock_density_plot, \
         patch("src.elmer_integration.parse_elmer_output") as mock_parse_output:

        mock_build_geometry.return_value = str(tmp_path / "motor.msh")
        mock_build_and_solve.return_value = tmp_path / "case.vtu"
        mock_extract_vc_sweep.return_value = mock_vc_results
        mock_extract_side_leakage.return_value = mock_side_leakage
        mock_parse_output.return_value = mock_parsed

        result = run_elmer_simulation(design, show_window=False)

        mock_build_geometry.assert_called_once()
        mock_build_and_solve.assert_called_once()
        mock_extract_vc_sweep.assert_called_once()
        mock_extract_side_leakage.assert_called_once()
        mock_write_output_files.assert_called_once()
        mock_density_plot.assert_called_once()
        mock_parse_output.assert_called_once()

        assert result.fea_b == 1.234
        assert len(result.bl_x_data) == 61
        assert len(result.side_leakage_data) == 100
        assert result.primary_magnet_avg_b == 0.987
        assert result.secondary_magnet_avg_b == "N/A"


# ─── TC-21: generate_elmer_input_files ───────────────────────────────────────


def test_generate_elmer_input_files(tmp_path: Path):
    """TC-21: generate_elmer_input_files writes SIF and creates mesh directory."""
    from src.api import generate_elmer_input_files, create_design
    design = create_design()
    design.working_directory = str(tmp_path)

    with patch("src.api.build_geometry") as mock_build, \
         patch("src.api.generate_sif") as mock_sif:
        mesh_path = tmp_path / "motor.msh"
        mesh_path.write_text("mock mesh")
        sif_path = tmp_path / "case.sif"
        sif_path.write_text("MagnetoDynamics2D\n")
        mock_build.return_value = str(mesh_path)

        def _mock_generate_sif(*args, **kwargs):
            # Real generate_sif creates mesh/ via ElmerGrid
            (tmp_path / "mesh").mkdir(parents=True, exist_ok=True)
            return sif_path

        mock_sif.side_effect = _mock_generate_sif

        result_sif, result_mesh = generate_elmer_input_files(design, str(tmp_path))

        assert Path(result_sif).exists()
        assert Path(result_mesh).exists()
        sif_text = Path(result_sif).read_text()
        assert "MagnetoDynamics2D" in sif_text
        mock_build.assert_called_once()
        mock_sif.assert_called_once()


# ─── Bug-fix verification tests (wvc_20260525_140552) ────────────────────────


def test_density_plot_uses_motor_bounds():
    """Bug fix 1: generate_density_plot uses motor geometry bounds for zoom."""
    import src.post_processor as pp
    source = Path(pp.__file__).read_text(encoding="utf-8")
    assert "r_max = max(design.top_plate_od, design.magnet_od, design.bp_od)" in source
    assert "z_min = -(design.bp_thickness + design.magnet_thickness + design.top_plate_thickness)" in source


@patch("src.post_processor.sample_point")
@patch("src.post_processor.average_b_on_line")
def test_extract_vc_sweep_raw_b_and_bmagnet(mock_avg, mock_sample, tmp_path: Path):
    """Bug fix 2: raw B point matches FEMM (no vc_offset), bmagnet across magnet cross-section."""
    from src.post_processor import extract_vc_sweep
    from src.api import create_design, recalculate_derived

    design = create_design()
    design = recalculate_derived(design)

    mock_sample.return_value = (1.0, 0.0, 0.0)
    mock_avg.return_value = 0.5

    vtu = tmp_path / "dummy.vtu"
    vtu.write_text("")

    result = extract_vc_sweep(vtu, design)

    # raw_b: 61 calls to sample_point at (vc_radius, pos) with NO vc_offset
    assert len(mock_sample.call_args_list) == 61
    vc_radius = design.vc_location_diameter / 2.0
    for i, call in enumerate(mock_sample.call_args_list):
        assert call.args[1] == pytest.approx(vc_radius, abs=1e-9)
        pos = -design.overhang * 1.15 + i * (2.0 * design.overhang * 1.15 / 60.0)
        assert call.args[2] == pytest.approx(pos, abs=1e-9)

    # bmagnet: last call to average_b_on_line spans magnet radial cross-section
    assert len(mock_avg.call_args_list) == 62  # 61 for vc_sweep + 1 for bmagnet
    bmagnet_call = mock_avg.call_args_list[-1]
    mag_center_y = -design.top_plate_thickness / 2.0 - design.magnet_thickness / 2.0
    assert bmagnet_call.args[1][0] == pytest.approx(design.magnet_id / 2.0, abs=1e-9)
    assert bmagnet_call.args[1][1] == pytest.approx(mag_center_y, abs=1e-9)
    assert bmagnet_call.args[2][0] == pytest.approx(design.magnet_od / 2.0, abs=1e-9)
    assert bmagnet_call.args[2][1] == pytest.approx(mag_center_y, abs=1e-9)

    assert result["bmagnet"] == 0.5
    assert len(result["raw_b"]) == 61


def test_button_busy_state_in_on_run_elmer():
    """Bug fix 3: _on_run_elmer disables button during simulation."""
    import src.main_window as mw
    source = Path(mw.__file__).read_text(encoding="utf-8")
    func_start = source.find("def _on_run_elmer(self):")
    assert func_start != -1
    func_end = source.find("\n    def ", func_start + 1)
    func_body = source[func_start:func_end]
    assert "setEnabled(False)" in func_body
    assert "setEnabled(True)" in func_body
    assert "finally:" in func_body


# ─── Bug-fix verification tests (wvc_20260525_154944) ────────────────────────


@patch("meshio.read")
@patch("matplotlib.pyplot.subplots")
@patch("matplotlib.pyplot.colorbar")
@patch("matplotlib.pyplot.tight_layout")
@patch("matplotlib.pyplot.savefig")
@patch("matplotlib.pyplot.close")
def test_density_plot_includes_geometry_overlays(
    mock_close, mock_savefig, mock_tight, mock_cbar, mock_subplots, mock_meshio_read, tmp_path: Path
):
    """Bug fix v0.1.6: generate_density_plot adds motor geometry overlay patches."""
    import numpy as np
    from matplotlib.patches import Rectangle
    from src.post_processor import generate_density_plot
    from src.api import create_design, recalculate_derived

    design = create_design()
    design = recalculate_derived(design)

    # Minimal synthetic mesh covering the plot grid
    pts = np.array([
        [0, -100], [200, -100], [200, 100], [0, 100],
    ], dtype=float)
    pts_3d = np.pad(pts, ((0, 0), (0, 1)))
    tris = np.array([[0, 1, 2], [0, 2, 3]])
    b_vec = np.ones((4, 3), dtype=float)

    mock_mesh = MagicMock()
    mock_mesh.points = pts_3d
    mock_mesh.cells_dict = {"triangle": tris}
    mock_mesh.point_data = {"magnetic flux density": b_vec}
    mock_meshio_read.return_value = mock_mesh

    mock_ax = MagicMock()
    mock_fig = MagicMock()
    mock_subplots.return_value = (mock_fig, mock_ax)
    mock_cbar.return_value = MagicMock()

    vtu = tmp_path / "case.vtu"
    vtu.write_text("dummy")
    output = tmp_path / "B-Field.png"

    generate_density_plot(vtu, design, output)

    # Verify all 5 overlay patches were added
    assert mock_ax.add_patch.call_count == 5

    labels = []
    for call in mock_ax.add_patch.call_args_list:
        rect = call.args[0]
        assert isinstance(rect, Rectangle)
        labels.append(rect.get_label())

    assert set(labels) == {"Top plate", "Magnet", "Back plate", "Pole piece", "Coil air"}

    # Verify coil air is centered on vc_offset with height == ww
    coil_rect = next(
        r for r in [c.args[0] for c in mock_ax.add_patch.call_args_list]
        if r.get_label() == "Coil air"
    )
    assert coil_rect.get_y() == pytest.approx(design.vc_offset - design.ww / 2.0, abs=1e-9)
    assert coil_rect.get_height() == pytest.approx(design.ww, abs=1e-9)
