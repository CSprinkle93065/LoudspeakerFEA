"""Elmer solver integration: mesh creation, solver invocation, and output parsing.

This module wraps the Elmer FEM pipeline and provides a drop-in replacement
for MotorModel's FEMM integration.
"""

from __future__ import annotations

import os
import re
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

from src.geometry_builder import build_geometry
from src.elmer_solver import build_and_solve
from src.post_processor import extract_vc_sweep, extract_side_leakage, write_output_files
from src.models import LoudspeakerDesign
from src.engine import recalculate_derived


# ─── Public API ──────────────────────────────────────────────────────────────


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
        Ignored — kept for API compatibility with FEMM (Elmer is headless).

    Returns
    -------
    The same *design* instance with FEA result fields populated.

    Raises
    ------
    RuntimeError
        If any stage of the pipeline fails.
    """
    design = recalculate_derived(design)

    workdir = Path(tempfile.mkdtemp(prefix=f"elmer_run_{int(time.time())}_"))

    # 1. Build geometry (Gmsh)
    mesh_path = build_geometry(design, str(workdir))

    # 2. Run solver (Elmer)
    sim_dir = workdir / "sim"
    vtu_path = build_and_solve(design, Path(mesh_path), sim_dir, elmersolver=design.elmer_solver_path)

    # 3. Post-process
    vc_results = extract_vc_sweep(vtu_path, design)
    side_leakage = extract_side_leakage(vtu_path, design, n_points=100)

    # 4. Write output files (FEMM-compatible format)
    write_output_files(workdir, vc_results, side_leakage, design)

    # 5. Density plot
    plot_path = workdir / "B-Field.png"
    generate_density_plot(vtu_path, design, plot_path)

    # 6. Parse outputs and populate design
    parsed = parse_elmer_output(workdir)
    design.fea_b = parsed["b_at_zero"]
    design.bl_x_data = [(pos, b * design.length_of_wire) for pos, b in parsed["vc_sweep"]]
    design.side_leakage_data = [val * 10000.0 for val in parsed["side_leakage"]]
    design.primary_magnet_avg_b = parsed["bmagnet"]
    design.secondary_magnet_avg_b = "N/A"

    # 7. Build bl_pct_array and x_array for interpolation
    if design.bl_x_data:
        max_b = max(b for _, b in design.bl_x_data) if design.bl_x_data else 1.0
        design.x_array = [pos for pos, _ in design.bl_x_data]
        design.bl_pct_array = [b / max_b if max_b > 0 else 0.0 for _, b in design.bl_x_data]

    # 8. Recalculate derived
    design = recalculate_derived(design)
    return design


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
