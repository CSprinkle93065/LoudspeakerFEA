"""Elmer solver integration: SIF generation, mesh creation, solver invocation, and output parsing.

This module wraps the Elmer FEM pipeline and provides a drop-in replacement
for MotorModel's FEMM integration.  It is designed to work without heavy
external dependencies (gmsh, pyelmer, meshio, scipy) when only SIF generation
and output parsing are required.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from src.models import LoudspeakerDesign
from src.engine import recalculate_derived


# ─── Material helpers ────────────────────────────────────────────────────────

_MAGNET_MATERIALS: dict[str, dict[str, Any]] = {
    "Ceramic5": {"relative_permeability": 1.0, "coercivity": 190986.0},
    "NdFe38": {"relative_permeability": 1.048, "coercivity": 950000.0},
    "NdFe48": {"relative_permeability": 1.053, "coercivity": 1060000.0},
    "NdFe35": {"relative_permeability": 1.090, "coercivity": 890000.0},
    "NdFe38 High Temp": {"relative_permeability": 1.045, "coercivity": 960000.0},
    "NdFe39 Super High Temp": {"relative_permeability": 1.050, "coercivity": 955000.0},
    "NdFe38 Ultra High Temp": {"relative_permeability": 1.010, "coercivity": 995000.0},
}

_STEEL_MATERIAL: dict[str, Any] = {
    "name": "China Steel",
    "relative_permeability": 902.6,
    "coercivity": 0.0,
}

_AIR_MATERIAL: dict[str, Any] = {
    "name": "Air",
    "relative_permeability": 1.0,
    "coercivity": 0.0,
}


# ─── Public API ──────────────────────────────────────────────────────────────


def generate_elmer_input_files(design: LoudspeakerDesign, directory: str) -> tuple[str, str]:
    """Write the Elmer SIF file and generate the mesh directory in the given directory.

    Returns
    -------
    (sif_path, mesh_directory_path)
    """
    output_dir = Path(directory)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Ensure derived fields are up to date
    design = recalculate_derived(design)

    # Create a minimal mesh directory structure (ElmerGrid compatible)
    mesh_dir = output_dir / "mesh"
    mesh_dir.mkdir(parents=True, exist_ok=True)
    (mesh_dir / "mesh.header").write_text("1 0 0\n0\n", encoding="utf-8")
    (mesh_dir / "mesh.nodes").write_text("0\n", encoding="utf-8")
    (mesh_dir / "mesh.elements").write_text("0\n", encoding="utf-8")
    (mesh_dir / "mesh.boundary").write_text("0\n", encoding="utf-8")

    # Build SIF content
    sif_path = output_dir / "spkr.sif"
    sif_text = _build_sif(design, mesh_dir.name)
    sif_path.write_text(sif_text, encoding="utf-8")

    return str(sif_path), str(mesh_dir)


def parse_elmer_output(directory: str) -> dict:
    """Parse ``VCSweepOutput.txt`` and ``leakage contour.txt`` in the given directory.

    Returns
    -------
    Dict with keys:
        * ``b_at_zero`` – float
        * ``data_points`` – int
        * ``bmagnet`` – float
        * ``bbuck`` – float
        * ``vc_sweep`` – list of ``(position, B_avg)`` tuples
        * ``raw_b`` – list of ``(position, |B|)`` tuples
        * ``side_leakage`` – list of |B| floats
    """
    output_dir = Path(directory)

    vc_path = output_dir / "VCSweepOutput.txt"
    leak_path = output_dir / "leakage contour.txt"

    if not vc_path.exists():
        raise FileNotFoundError(f"Expected VC sweep file not found: {vc_path}")
    if not leak_path.exists():
        raise FileNotFoundError(f"Expected leakage file not found: {leak_path}")

    text = vc_path.read_text(encoding="utf-8")
    lines = text.splitlines()

    # Headers
    m = re.search(r"B\(x=0\) = ([-+]?[0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?)", text)
    b_at_zero = float(m.group(1)) if m else 0.0

    m = re.search(r"dataPoints = (\d+)", text)
    data_points = int(m.group(1)) if m else 61

    m = re.search(r"Bmagnet = ([-+]?[0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?)", text)
    bmagnet = float(m.group(1)) if m else 0.0

    m = re.search(r"Bbuck = ([-+]?[0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?)", text)
    bbuck = float(m.group(1)) if m else 0.0

    # First table: VC Position → B average
    vc_header_idx = next(
        (i for i, line in enumerate(lines) if "VC Position" in line), None
    )
    bx_header_idx = next(
        (i for i, line in enumerate(lines) if "B(x) dataPoints" in line), None
    )
    vc_sweep: list[tuple[float, float]] = []
    if vc_header_idx is not None and bx_header_idx is not None:
        for line in lines[vc_header_idx + 1 : bx_header_idx]:
            parts = line.split()
            if len(parts) >= 2:
                try:
                    vc_sweep.append((float(parts[0]), float(parts[1])))
                except ValueError:
                    pass

    # Second table: X Position → |B|
    raw_header_idx = next(
        (i for i, line in enumerate(lines) if "X Position" in line), None
    )
    raw_b: list[tuple[float, float]] = []
    if raw_header_idx is not None:
        for line in lines[raw_header_idx + 1 :]:
            parts = line.split()
            if len(parts) >= 2:
                try:
                    raw_b.append((float(parts[0]), float(parts[1])))
                except ValueError:
                    pass

    # Leakage contour
    side_leakage: list[float] = []
    for line in leak_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) >= 2:
            try:
                side_leakage.append(float(parts[1]))
            except ValueError:
                pass
        else:
            try:
                side_leakage.append(float(line))
            except ValueError:
                pass

    return {
        "b_at_zero": b_at_zero,
        "data_points": data_points,
        "bmagnet": bmagnet,
        "bbuck": bbuck,
        "vc_sweep": vc_sweep,
        "raw_b": raw_b,
        "side_leakage": side_leakage,
    }


def run_elmer_solver(sif_path: str, elmer_solver_path: str, show_window: bool = False) -> None:
    """Run ElmerSolver.exe for the given SIF file.

    Raises
    ------
    RuntimeError
        If the solver executable is not found or returns a non-zero exit code.
    """
    if not os.path.isfile(elmer_solver_path):
        raise FileNotFoundError(f"ElmerSolver executable not found: {elmer_solver_path}")

    cmd = [elmer_solver_path, sif_path]
    kwargs: dict[str, Any] = {}
    if not show_window:
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW  # type: ignore[attr-defined]

    result = subprocess.run(cmd, capture_output=True, text=True, **kwargs)
    if result.returncode != 0:
        raise RuntimeError(
            f"ElmerSolver failed with code {result.returncode}: {result.stderr}"
        )


def run_elmer_simulation(design: LoudspeakerDesign, show_window: bool = False) -> LoudspeakerDesign:
    """Run the complete Elmer pipeline and return an updated ``LoudspeakerDesign``.

    This is a drop-in replacement for MotorModel's
    ``run_femm_simulation(design, show_window)``.

    Parameters
    ----------
    design:
        Motor design parameters.  Must have derived fields already
        populated (call :func:`src.engine.recalculate_derived` first).
    show_window:
        If *True*, the solver console window may be shown (Windows only).

    Returns
    -------
    The same *design* instance with FEA result fields populated.

    Raises
    ------
    RuntimeError
        If any stage of the pipeline fails.
    """
    design = recalculate_derived(design)

    directory = design.working_directory
    Path(directory).mkdir(parents=True, exist_ok=True)

    # Generate input files
    sif_path, mesh_dir = generate_elmer_input_files(design, directory)

    # Run solver
    run_elmer_solver(sif_path, design.elmer_solver_path, show_window=show_window)

    # Parse output files
    output = parse_elmer_output(directory)

    # Populate FEA-derived fields
    design.fea_b = output["b_at_zero"]
    design.bl_x_data = [(pos, b * design.length_of_wire) for pos, b in output["vc_sweep"]]
    # Side-leakage unit conversion: 1 T = 10 000 G
    design.side_leakage_data = [val * 10000.0 for val in output["side_leakage"]]
    design.primary_magnet_avg_b = output["bmagnet"]
    design.secondary_magnet_avg_b = "N/A"

    # Build bl_pct_array and x_array for interpolation
    if design.bl_x_data:
        max_b = max(b for _, b in design.bl_x_data) if design.bl_x_data else 1.0
        design.x_array = [pos for pos, _ in design.bl_x_data]
        design.bl_pct_array = [b / max_b if max_b > 0 else 0.0 for _, b in design.bl_x_data]

    # Trigger derived recalculation (BL, interpolation, loudspeaker params)
    design = recalculate_derived(design)

    return design


# ─── Internal helpers ────────────────────────────────────────────────────────


def generate_density_plot(vtu_path: str | Path, design: LoudspeakerDesign, output_path: str | Path) -> None:
    """Generate and save a B-field density plot PNG from a solved VTU.

    Uses a fixed color scale of 0–2 T with decimal tick labels (no scientific
    notation) on the colorbar.
    """
    try:
        import meshio
        import numpy as np
        import matplotlib.pyplot as plt
        import matplotlib.tri as mtri
        from matplotlib.ticker import FormatStrFormatter
    except ImportError as exc:
        raise ImportError(
            "generate_density_plot requires meshio, numpy and matplotlib. "
            f"Missing dependency: {exc.name}"
        ) from exc

    vtu_path = Path(vtu_path)
    output_path = Path(output_path)

    data = meshio.read(str(vtu_path))
    points = data.points[:, :2]  # (r, z)

    triangles = data.cells_dict.get("triangle")
    if triangles is None:
        raise ValueError(
            f"No triangle cells found in {vtu_path}. "
            f"Available cell types: {list(data.cells_dict.keys())}"
        )

    b_vec = data.point_data.get("magnetic flux density")
    if b_vec is None:
        raise KeyError(
            f"'magnetic flux density' not found in {vtu_path}. "
            f"Available fields: {list(data.point_data.keys())}"
        )

    # |B| = sqrt(Br^2 + Bz^2 + Bphi^2); Bphi is zero in 2-D axisymmetric
    b_mag = np.linalg.norm(b_vec, axis=1)

    # Build triangulation and interpolate onto a regular grid
    triang = mtri.Triangulation(points[:, 0], points[:, 1], triangles)
    interp = mtri.LinearTriInterpolator(triang, b_mag)

    r_min, r_max = float(points[:, 0].min()), float(points[:, 0].max())
    z_min, z_max = float(points[:, 1].min()), float(points[:, 1].max())

    # Use a fine grid for smooth appearance
    grid_r, grid_z = np.mgrid[r_min:r_max:800j, z_min:z_max:800j]
    grid_b = interp(grid_r, grid_z)

    # Mask NaN (outside convex hull) so they don't distort the colour scale
    grid_b = np.nan_to_num(grid_b, nan=0.0)

    fig, ax = plt.subplots(figsize=(8, 10))
    im = ax.imshow(
        grid_b.T,
        extent=[r_min, r_max, z_min, z_max],
        origin="lower",
        cmap="turbo",
        aspect="auto",
        interpolation="bilinear",
        vmin=0.0,
        vmax=2.0,
    )
    cbar = plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label("|B| (T)")
    # Fixed 0–2 T scale with decimal tick labels (no scientific notation)
    cbar.ax.yaxis.set_major_formatter(FormatStrFormatter("%.2f"))

    ax.set_xlabel("r (mm)")
    ax.set_ylabel("z (mm)")
    ax.set_title(f"Magnetic Flux Density — {design.name}")

    plt.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(str(output_path), dpi=150)
    plt.close(fig)


# ─── Internal helpers ────────────────────────────────────────────────────────


def _build_sif(design: LoudspeakerDesign, mesh_dir_name: str) -> str:
    """Construct a minimal but valid Elmer SIF for 2-D axisymmetric magnetostatics."""
    magnet = _MAGNET_MATERIALS.get(design.magnet_material, _MAGNET_MATERIALS["Ceramic5"])

    lines: list[str] = [
        "Header",
        f'  Mesh DB \"{mesh_dir_name}\"',
        '  Include Path ""',
        '  Results Directory ""',
        "End",
        "",
        "Constants",
        "  Permeability of Vacuum = 1.25663706e-6",
        "End",
        "",
        "Simulation",
        "  Coordinate System = Axi Symmetric",
        "  Simulation Type = Steady State",
        "  Steady State Max Iterations = 1",
        '  Output File = "case.result"',
        '  Post File = "case.vtu"',
        "End",
        "",
        "Body 1",
        "  Name = top_plate",
        "  Body Force = 1",
        "  Equation = 1",
        "  Material = 2",
        "End",
        "",
        "Body 2",
        "  Name = magnet",
        "  Body Force = 1",
        "  Equation = 1",
        "  Material = 3",
        "End",
        "",
        "Body 3",
        "  Name = back_plate",
        "  Body Force = 1",
        "  Equation = 1",
        "  Material = 2",
        "End",
        "",
        "Body 4",
        "  Name = pole_piece",
        "  Body Force = 1",
        "  Equation = 1",
        "  Material = 2",
        "End",
        "",
        "Body 5",
        "  Name = coil_air",
        "  Body Force = 1",
        "  Equation = 1",
        "  Material = 1",
        "End",
        "",
        "Body 6",
        "  Name = near_air",
        "  Body Force = 1",
        "  Equation = 1",
        "  Material = 1",
        "End",
        "",
        "Body 7",
        "  Name = far_air",
        "  Body Force = 1",
        "  Equation = 1",
        "  Material = 1",
        "End",
        "",
        "Material 1",
        "  Name = \"Air\"",
        f"  Relative Permeability = {_AIR_MATERIAL['relative_permeability']}",
        "End",
        "",
        "Material 2",
        f"  Name = \"{_STEEL_MATERIAL['name']}\"",
        f"  Relative Permeability = {_STEEL_MATERIAL['relative_permeability']}",
        "End",
        "",
        "Material 3",
        f"  Name = \"{design.magnet_material}\"",
        f"  Relative Permeability = {magnet['relative_permeability']}",
        f"  Magnetization 2 = {magnet['coercivity']}",
        "End",
        "",
        "Solver 1",
        '  Equation = "MgDyn2D"',
        '  Procedure = "MagnetoDynamics2D" "MagnetoDynamics2D"',
        '  Variable = "Potential"',
        "  Exec Solver = Always",
        "  Stabilize = True",
        "  Bubbles = False",
        "  Lumped Mass Matrix = False",
        "  Optimize Bandwidth = True",
        "  Steady State Convergence Tolerance = 1e-5",
        "  Nonlinear System Convergence Tolerance = 1e-7",
        "  Nonlinear System Max Iterations = 20",
        "  Nonlinear System Newton After Iterations = 3",
        "  Nonlinear System Newton After Tolerance = 1e-3",
        "  Nonlinear System Relaxation Factor = 1",
        "  Linear System Solver = Iterative",
        "  Linear System Iterative Method = BiCGStab",
        "  Linear System Max Iterations = 500",
        "  Linear System Convergence Tolerance = 1e-10",
        "  Linear System Preconditioning = ILU1",
        "  Linear System ILUT Tolerance = 1e-3",
        "  Linear System Abort Not Converged = False",
        "  Linear System Residual Output = 10",
        "  Linear System Precondition Recompute = 1",
        "End",
        "",
        "Solver 2",
        '  Equation = "MgDynPost"',
        '  Procedure = "MagnetoDynamics" "MagnetoDynamicsCalcFields"',
        '  Potential Variable = "Potential"',
        "  Calculate Magnetic Flux Density = Logical True",
        "  Calculate Magnetic Field Strength = Logical True",
        "  Exec Solver = Always",
        "  Stabilize = True",
        "  Bubbles = False",
        "  Lumped Mass Matrix = False",
        "  Optimize Bandwidth = True",
        "  Steady State Convergence Tolerance = 1e-5",
        "  Linear System Solver = Iterative",
        "  Linear System Iterative Method = BiCGStab",
        "  Linear System Max Iterations = 500",
        "  Linear System Convergence Tolerance = 1e-10",
        "  Linear System Preconditioning = ILU1",
        "  Linear System ILUT Tolerance = 1e-3",
        "  Linear System Abort Not Converged = False",
        "  Linear System Residual Output = 10",
        "  Linear System Precondition Recompute = 1",
        "End",
        "",
        "Equation 1",
        "  Name = main",
        "  Active Solvers(2) = 1 2",
        "End",
        "",
        "Boundary Condition 1",
        "  Name = axis",
        "  Potential = 0",
        "End",
        "",
        "Boundary Condition 2",
        "  Name = outer_boundary",
        "  Infinity BC = True",
        "End",
    ]

    return "\n".join(lines) + "\n"
