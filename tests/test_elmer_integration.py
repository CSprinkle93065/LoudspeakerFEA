"""Tests for Elmer integration API functions.

Covers: generate_elmer_input_files, parse_elmer_output,
run_elmer_simulation (mocked), SIF content verification, error handling.

All subprocess and file-system calls are mocked — no Elmer installation required.
"""

import inspect
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from src.api import (
    create_design, run_elmer_simulation,
    generate_elmer_input_files, parse_elmer_output,
)


def test_generate_elmer_input_files(tmp_path: Path):
    """TC-21: Generate Elmer Input Files — SIF and mesh directory written."""
    design = create_design()
    sif_path, mesh_dir = generate_elmer_input_files(design, str(tmp_path))
    assert Path(sif_path).exists()
    assert Path(mesh_dir).exists()
    sif_text = Path(sif_path).read_text()
    assert "MagnetoDynamics2D" in sif_text


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
    """TC-02: Run Elmer Simulation — mocked solver; design fields populated."""
    design = create_design()
    design.working_directory = str(tmp_path)
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
    with patch("src.elmer_integration.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        design = run_elmer_simulation(design, show_window=False)
    assert design.fea_b is not None
    assert len(design.bl_x_data) == 61
    assert len(design.side_leakage_data) == 100
    assert design.primary_magnet_avg_b is not None
    assert design.bl is not None
    assert design.bl > 0


def test_sif_contains_correct_materials(tmp_path: Path):
    """TC-E04: SIF contains Air, China Steel, and selected magnet material definitions."""
    design = create_design()
    design.magnet_material = "Ceramic5"
    sif_path, _ = generate_elmer_input_files(design, str(tmp_path))
    sif_text = Path(sif_path).read_text()
    assert "Material 1" in sif_text
    assert "China Steel" in sif_text
    assert "Ceramic5" in sif_text


def test_sif_no_bucking_magnet(tmp_path: Path):
    """TC-E05: SIF does not contain bucking magnet geometry or material."""
    design = create_design()
    sif_path, _ = generate_elmer_input_files(design, str(tmp_path))
    sif_text = Path(sif_path).read_text()
    assert "Bucking" not in sif_text
    assert "secondary_magnet" not in sif_text.lower()


def test_missing_elmer_executable_raises():
    """TC-E06: run_elmer_simulation raises when executable path is invalid."""
    design = create_design()
    design.elmer_solver_path = r"C:\NonExistent\ElmerSolver.exe"
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
    vc_file = tmp_path / "VCSweepOutput.txt"
    vc_file.write_text(
        "B(x=0) = 1.0\ndataPoints = 1\nBmagnet = 1.0\n0  1.0\n"
    )
    leak_file = tmp_path / "leakage contour.txt"
    leak_file.write_text("0.01")
    with patch("src.elmer_integration.run_elmer_solver") as mock_solver:
        mock_solver.return_value = None
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

    with patch("src.geometry_builder.build_geometry") as mock_build_geometry, \
         patch("src.elmer_solver.build_and_solve") as mock_build_and_solve, \
         patch("src.post_processor.extract_vc_sweep") as mock_extract_vc_sweep, \
         patch("src.post_processor.extract_side_leakage") as mock_extract_side_leakage, \
         patch("src.post_processor.write_output_files") as mock_write_output_files, \
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
