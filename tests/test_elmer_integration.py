"""Tests for Elmer integration API functions.

Covers: generate_elmer_input_files, parse_elmer_output,
run_elmer_simulation (mocked), SIF content verification, error handling.

All subprocess and file-system calls are mocked — no Elmer installation required.
"""

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
