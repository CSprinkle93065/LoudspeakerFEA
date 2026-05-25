"""Integration smoke tests for the real Elmer pipeline.

These tests exercise live dependencies (gmsh, pyelmer, meshio, scipy, vtk,
ElmerSolver.exe) and are designed to catch missing-dependency bugs that
mock-based tests cannot detect.

Run all tests::
    pytest tests/test_integration_smoke.py -v

Skip the slow end-to-end test::
    pytest tests/test_integration_smoke.py -v -m "not slow"

"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from src.api import create_design, run_elmer_simulation
from src.geometry_builder import build_geometry
from src.models import find_elmer_executable


# ---------------------------------------------------------------------------
# TC-I01: gmsh importability when build_geometry is called
# ---------------------------------------------------------------------------

def test_gmsh_importable_when_build_geometry_called(tmp_path: Path):
    """TC-I01: build_geometry() must not raise ImportError for gmsh.

    Purpose: Catches missing gmsh installation BEFORE running a full simulation.
    Timeout: 30 seconds max.
    Skip condition: None — test FAILS with a clear message if gmsh is missing.
    """
    design = create_design()
    design.working_directory = str(tmp_path)

    # This call imports gmsh lazily inside build_geometry().
    # If gmsh is missing, the function raises ImportError with a clear message.
    msh_path = build_geometry(design, str(tmp_path))

    assert isinstance(msh_path, Path)
    assert msh_path.exists()


# ---------------------------------------------------------------------------
# TC-I02: pyelmer and meshio importability
# ---------------------------------------------------------------------------

def test_pyelmer_and_meshio_importable_for_solve():
    """TC-I02: pyelmer and meshio must import without error.

    Purpose: Catches missing pyelmer/meshio before the solver stage.
    """
    import pyelmer as pyelmer_module  # noqa: F401
    import meshio as meshio_module  # noqa: F401

    assert pyelmer_module is not None
    assert meshio_module is not None


# ---------------------------------------------------------------------------
# TC-I03: real mesh generation
# ---------------------------------------------------------------------------

def test_real_build_geometry_creates_mesh_file(tmp_path: Path):
    """TC-I03: build_geometry() with Design 1 defaults must create a non-empty mesh.

    Purpose: Verifies Gmsh can actually generate a mesh (not just import).
    Timeout: 60 seconds max.
    Skip: Only if gmsh is not installed.
    """
    pytest.importorskip("gmsh")

    design = create_design()
    design.working_directory = str(tmp_path)

    msh_path = build_geometry(design, str(tmp_path))

    assert msh_path.exists(), f"Mesh file not created: {msh_path}"
    assert msh_path.stat().st_size > 0, f"Mesh file is empty: {msh_path}"


# ---------------------------------------------------------------------------
# TC-I04: ElmerSolver executable discovery
# ---------------------------------------------------------------------------

def test_real_elmer_solver_executable_found():
    """TC-I04: find_elmer_executable() must locate an existing, readable executable.

    Purpose: Catches missing ElmerFEM installation.
    """
    exe_path = find_elmer_executable()

    assert os.path.isfile(exe_path), f"ElmerSolver executable not found: {exe_path}"
    assert os.access(exe_path, os.R_OK), f"ElmerSolver executable not readable: {exe_path}"


# ---------------------------------------------------------------------------
# Bug-fix verification (wvc_20260525_154944) — coil_air bounds
# ---------------------------------------------------------------------------


def test_build_geometry_coil_air_bounds(tmp_path: Path):
    """Bug fix v0.1.6: coil_air mesh region is centered on vc_offset ± ww/2."""
    pytest.importorskip("gmsh")
    import meshio
    import numpy as np

    from src.geometry_builder import build_geometry
    from src.api import create_design, recalculate_derived

    design = create_design()
    design = recalculate_derived(design)

    msh_path = build_geometry(design, str(tmp_path))

    mesh = meshio.read(str(msh_path))

    # Find coil_air physical group tag
    coil_air_tag = None
    for name, (tag, dim) in mesh.field_data.items():
        if name == "coil_air" and dim == 2:
            coil_air_tag = int(tag)
            break
    assert coil_air_tag is not None, "coil_air physical group not found in mesh"

    # Collect all nodes belonging to coil_air triangles
    coil_air_nodes = set()
    for cell_block, physical_arr in zip(mesh.cells, mesh.cell_data["gmsh:physical"]):
        if cell_block.type == "triangle":
            mask = physical_arr == coil_air_tag
            for tri in cell_block.data[mask]:
                coil_air_nodes.update(tri)

    assert len(coil_air_nodes) > 0, "No nodes in coil_air region"

    coords = mesh.points[list(coil_air_nodes)]
    y_min = coords[:, 1].min()
    y_max = coords[:, 1].max()

    expected_y_min = design.vc_offset - design.ww / 2.0
    expected_y_max = design.vc_offset + design.ww / 2.0

    # Allow small tolerance for mesh discretization at rectangle edges
    assert y_min == pytest.approx(expected_y_min, abs=0.1)
    assert y_max == pytest.approx(expected_y_max, abs=0.1)


# ---------------------------------------------------------------------------
# TC-I05: end-to-end integration smoke test
# ---------------------------------------------------------------------------

@pytest.mark.slow
def test_run_elmer_simulation_integration_smoke(tmp_path: Path):
    """TC-I05: Full pipeline integration test with real ElmerSolver.

    API: run_elmer_simulation(design, show_window=False) with Design 1 defaults.
    Assert: Returns updated design with fea_b > 0 and len(bl_x_data) == 61.
    Purpose: End-to-end integration test of the FULL pipeline.
    Timeout: 300 seconds (5 minutes) max.
    Requirements: gmsh, pyelmer, meshio, scipy, vtk, ElmerSolver.exe must all be present.
    Skip: Marked pytest.mark.slow; skipped in fast CI, but MANDATORY for release validation.
    """
    design = create_design()
    design.working_directory = str(tmp_path)

    result = run_elmer_simulation(design, show_window=False)

    assert result.fea_b > 0, f"Expected fea_b > 0, got {result.fea_b}"
    assert len(result.bl_x_data) == 61, f"Expected 61 BL(x) points, got {len(result.bl_x_data)}"
