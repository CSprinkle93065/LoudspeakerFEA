"""Elmer solver integration: SIF generation, mesh conversion, and execution.

This module bridges the Gmsh geometry builder and the Elmer FEM solver.
It generates a complete Elmer SIF file, converts the Gmsh mesh with
ElmerGrid, runs ElmerSolver, and returns the path to the VTU output.

.. note::
   The prompt asks for ``MgDyn`` (the 3D ``MagnetoDynamics`` solver).
   That procedure (``WhitneyAVSolver``) requires a 3-D mesh and fails on
   our 2-D axisymmetric mesh.  We therefore use ``MagnetoDynamics2D`` for
   the field solve and ``MagnetoDynamicsCalcFields`` for the post-process
   step – this is the only working combination for 2-D axisymmetric
   magnetostatics in the installed Elmer build.
"""

from __future__ import annotations

import os
import re
import shutil
from pathlib import Path
from typing import Any

from src.materials import _bh_to_mur_h, load_material
from src.models import LoudspeakerDesign

# ---------------------------------------------------------------------------
# Material mapping
# ---------------------------------------------------------------------------

_BODY_MATERIAL_CATEGORY: dict[str, str] = {
    "top_plate": "steel",
    "magnet": "magnet",
    "back_plate": "steel",
    "pole_piece": "steel",
    "coil_air": "air",
    "near_air": "air",
    "far_air": "air",
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_physical_groups(msh_path: Path) -> dict[str, int]:
    """Return ``name → tag`` for every physical group in a Gmsh ``.msh`` file."""
    try:
        import meshio
    except ImportError as exc:
        raise ImportError(
            "elmer_solver requires meshio to be installed. "
            "Install it with: pip install meshio"
        ) from exc
    mesh = meshio.read(str(msh_path))
    return {name: int(tag_dim[0]) for name, tag_dim in mesh.field_data.items()}


def _build_pyelmer_material_data(material: dict[str, Any]) -> dict[str, Any]:
    """Convert a material dict from :mod:`src.materials` to a pyelmer data dict."""
    mat_type = material.get("type", "linear")
    data: dict[str, Any] = {}

    if mat_type in ("linear", "linear_permanent_magnet"):
        data["Relative Permeability"] = material["relative_permeability"]
        if material.get("magnetization_A_m", 0) != 0:
            # In axisymmetric coordinates component 2 is the axial (z)
            # direction.  The original FEMM macro sets the magnet angle to
            # 90° (upward, +z) for the primary magnet.
            data["Magnetization 2"] = material["magnetization_A_m"]

    elif mat_type == "nonlinear_bh_curve":
        # For steels we will post-process the SIF to insert the H-B curve.
        # Until then keep the linear fallback so pyelmer writes a valid SIF.
        data["Relative Permeability"] = material.get(
            "linear_fallback_permeability", 1000.0
        )
        if material.get("magnetization_A_m", 0) != 0:
            data["Magnetization 2"] = material["magnetization_A_m"]

    return data


def _find_executable(name: str, fallback_paths: list[str]) -> str:
    """Locate *name* on ``PATH`` or fall back to known absolute paths."""
    exe = shutil.which(name)
    if exe:
        return exe
    for path in fallback_paths:
        if os.path.isfile(path):
            return path
    raise FileNotFoundError(
        f"{name} not found on PATH or at known locations: {fallback_paths}"
    )


def _parse_solver_log(log_path: Path) -> dict[str, Any]:
    """Scan an ElmerSolver log for convergence and fatal errors."""
    info: dict[str, Any] = {
        "converged": False,
        "iterations": 0,
        "errors": [],
    }
    if not log_path.exists():
        return info

    text = log_path.read_text()
    for line in text.splitlines():
        if line.startswith("ERROR::") or line.startswith("STOP"):
            info["errors"].append(line.strip())
        if match := re.search(r"NS \(ITER=(\d+)\)", line):
            info["iterations"] = max(info["iterations"], int(match.group(1)))
        if match := re.search(r"SS \(ITER=(\d+)\)", line):
            info["iterations"] = max(info["iterations"], int(match.group(1)))

    info["converged"] = not info["errors"] and (
        "ALL DONE" in text or "Finished solver" in text
    )
    return info


# ---------------------------------------------------------------------------
# Main API
# ---------------------------------------------------------------------------


def generate_sif(
    design: LoudspeakerDesign,
    mesh_path: Path,
    output_dir: Path,
    steel_material: str = "China Steel",
    elmergrid: str | None = None,
) -> Path:
    """Convert mesh and write the Elmer SIF (does **not** run the solver).

    Parameters
    ----------
    design:
        Loudspeaker design parameters.
    mesh_path:
        Path to the Gmsh ``.msh`` file.
    output_dir:
        Working directory for the simulation.
    steel_material:
        Name of the steel material for top / back plate and pole piece.
    elmergrid:
        Path to the ``ElmerGrid`` executable.  Auto-detected when *None*.

    Returns
    -------
    Path to the written ``case.sif`` file.
    """
    try:
        from pyelmer import elmer, execute
    except ImportError as exc:
        raise ImportError(
            "elmer_solver requires pyelmer to be installed. "
            "Install it with: pip install pyelmer"
        ) from exc

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if elmergrid is None:
        elmergrid = _find_executable(
            "ElmerGrid",
            [
                r"C:\Program Files\ElmerFEM\bin\ElmerGrid.exe",
                r"C:\Program Files (x86)\ElmerFEM\bin\ElmerGrid.exe",
            ],
        )

    # Mesh conversion
    mesh_name = mesh_path.name
    shutil.copy(str(mesh_path), str(output_dir / mesh_name))
    execute.run_elmer_grid(str(output_dir), mesh_name, elmergrid=elmergrid)

    # Physical groups
    groups = _get_physical_groups(mesh_path)
    body_tags = {
        name: tag
        for name, tag in groups.items()
        if name not in ("axis", "outer_boundary")
    }
    boundary_tags = {
        name: tag
        for name, tag in groups.items()
        if name in ("axis", "outer_boundary")
    }

    # Build pyelmer simulation
    sim = elmer.Simulation()
    sim.settings.update(
        {
            "Coordinate System": "Axi Symmetric",
            "Simulation Type": "Steady State",
            "Steady State Max Iterations": 1,
            "Output File": '"case.result"',
            "Post File": '"case.vtu"',
        }
    )
    sim.constants.update(
        {
            "Permeability Of Vacuum": 1.25663706e-6,
        }
    )

    solver1 = elmer.Solver(
        sim,
        "MgDyn2D",
        data={
            "Equation": "MgDyn2D",
            "Procedure": '"MagnetoDynamics2D" "MagnetoDynamics2D"',
            "Variable": "Potential",
            "Exec Solver": "Always",
            "Stabilize": True,
            "Bubbles": False,
            "Lumped Mass Matrix": False,
            "Optimize Bandwidth": True,
            "Steady State Convergence Tolerance": 1e-5,
            "Nonlinear System Convergence Tolerance": 1e-7,
            "Nonlinear System Max Iterations": 20,
            "Nonlinear System Newton After Iterations": 3,
            "Nonlinear System Newton After Tolerance": 1e-3,
            "Nonlinear System Relaxation Factor": 1,
            "Linear System Solver": "Iterative",
            "Linear System Iterative Method": "BiCGStab",
            "Linear System Max Iterations": 500,
            "Linear System Convergence Tolerance": 1e-10,
            "Linear System Preconditioning": "ILU1",
            "Linear System ILUT Tolerance": 1e-3,
            "Linear System Abort Not Converged": False,
            "Linear System Residual Output": 10,
            "Linear System Precondition Recompute": 1,
        },
    )

    solver2 = elmer.Solver(
        sim,
        "MgDynPost",
        data={
            "Equation": "MgDynPost",
            "Procedure": '"MagnetoDynamics" "MagnetoDynamicsCalcFields"',
            "Potential Variable": "Potential",
            "Calculate Magnetic Flux Density": "Logical True",
            "Calculate Magnetic Field Strength": "Logical True",
            "Exec Solver": "Always",
            "Stabilize": True,
            "Bubbles": False,
            "Lumped Mass Matrix": False,
            "Optimize Bandwidth": True,
            "Steady State Convergence Tolerance": 1e-5,
            "Linear System Solver": "Iterative",
            "Linear System Iterative Method": "BiCGStab",
            "Linear System Max Iterations": 500,
            "Linear System Convergence Tolerance": 1e-10,
            "Linear System Preconditioning": "ILU1",
            "Linear System ILUT Tolerance": 1e-3,
            "Linear System Abort Not Converged": False,
            "Linear System Residual Output": 10,
            "Linear System Precondition Recompute": 1,
        },
    )

    eqn = elmer.Equation(sim, "main", [solver1, solver2])

    air_data = _build_pyelmer_material_data(load_material("Air"))
    magnet_data = _build_pyelmer_material_data(load_material(design.magnet_material))
    steel_data = _build_pyelmer_material_data(load_material(steel_material))

    air_mat = elmer.Material(sim, "Air", data=air_data)
    magnet_mat = elmer.Material(sim, design.magnet_material, data=magnet_data)
    steel_mat = elmer.Material(sim, steel_material, data=steel_data)

    material_lookup = {
        "air": air_mat,
        "magnet": magnet_mat,
        "steel": steel_mat,
    }

    for body_name, tag in body_tags.items():
        category = _BODY_MATERIAL_CATEGORY.get(body_name)
        if category is None:
            continue
        body = elmer.Body(sim, body_name, [tag])
        body.equation = eqn
        body.material = material_lookup[category]

    if "axis" in boundary_tags:
        elmer.Boundary(
            sim,
            "axis",
            [boundary_tags["axis"]],
            data={"Potential": 0},
        )

    if "outer_boundary" in boundary_tags:
        elmer.Boundary(
            sim,
            "outer_boundary",
            [boundary_tags["outer_boundary"]],
            data={"Infinity BC": True},
        )

    sim.write_sif(str(output_dir))
    sim.write_startinfo(str(output_dir))

    # ------------------------------------------------------------------
    # Post-process the SIF: replace linear fallback with H-B curve
    # for ALL nonlinear materials (steel AND magnet).
    # pyelmer cannot emit nested Variable/Real/End blocks cleanly, so
    # we edit the file after pyelmer writes it.
    #
    # IMPORTANT: Elmer's SIF parser for Material sections treats a
    # ``Variable ... Real ... End`` block as a single multi-line
    # property value.  Only ONE ``End`` is needed to close the ``Real``
    # block; the ``Variable`` block is implicitly closed.  pyelmer then
    # writes its own ``End`` for the Material.
    # ------------------------------------------------------------------
    sif_path = output_dir / "case.sif"

    materials_to_patch: list[tuple[Any, dict[str, Any]]] = []

    # Steel
    steel_mat_dict = load_material(steel_material)
    if steel_mat_dict.get("type") == "nonlinear_bh_curve" and "bh_curve" in steel_mat_dict:
        materials_to_patch.append((steel_mat, steel_mat_dict))

    # Magnet
    magnet_mat_dict = load_material(design.magnet_material)
    if magnet_mat_dict.get("type") == "nonlinear_bh_curve" and "bh_curve" in magnet_mat_dict:
        materials_to_patch.append((magnet_mat, magnet_mat_dict))

    for mat_obj, mat_dict in materials_to_patch:
        hb_name = f"HB_{mat_dict['name'].replace(' ', '_')}"
        hb_path = output_dir / hb_name
        rows = [f"{b} {h}" for h, b in mat_dict["bh_curve"]]
        hb_path.write_text("\n".join(rows) + "\n", encoding="utf-8")

        old_text = sif_path.read_text(encoding="utf-8")
        mat_id = mat_obj.id
        pattern = rf"(Material {mat_id}\b.*?)Relative Permeability = .*?\n"
        replacement = (
            r"\1"
            f"h-b curve = Variable \"dummy\"\n"
            f"  Real\n"
            f"    include {hb_name}\n"
            f"  End\n"
        )
        new_text = re.sub(pattern, replacement, old_text, count=1, flags=re.DOTALL)
        sif_path.write_text(new_text, encoding="utf-8")

    return output_dir / "case.sif"


def build_and_solve(
    design: LoudspeakerDesign,
    mesh_path: Path,
    output_dir: Path,
    steel_material: str = "China Steel",
    elmergrid: str | None = None,
    elmersolver: str | None = None,
) -> Path:
    """Generate SIF, run ElmerSolver, and return the VTU output path.

    Parameters
    ----------
    design:
        Loudspeaker design parameters (used for material selection).
    mesh_path:
        Path to the Gmsh ``.msh`` file produced by
        :func:`src.geometry_builder.build_geometry`.
    output_dir:
        Working directory for the Elmer simulation.  Created if it does
        not exist.
    steel_material:
        Name of the steel material assigned to top plate, back plate, and
        pole piece (e.g. ``"China Steel"`` or ``"Ceramic5"``).
    elmergrid:
        Path to the ``ElmerGrid`` executable.  Auto-detected when *None*.
    elmersolver:
        Path to the ``ElmerSolver`` executable.  Auto-detected when *None*.

    Returns
    -------
    Path to the generated VTU file (usually ``output_dir / "case.vtu"``).

    Raises
    ------
    RuntimeError
        If ElmerSolver fails or the expected VTU output is not produced.
    FileNotFoundError
        If Elmer executables cannot be found.
    """
    try:
        from pyelmer import execute
    except ImportError as exc:
        raise ImportError(
            "elmer_solver requires pyelmer to be installed. "
            "Install it with: pip install pyelmer"
        ) from exc

    output_dir = Path(output_dir)

    if elmersolver is None:
        elmersolver = _find_executable(
            "ElmerSolver",
            [
                r"C:\Program Files\ElmerFEM\bin\ElmerSolver.exe",
                r"C:\Program Files (x86)\ElmerFEM\bin\ElmerSolver.exe",
            ],
        )

    # Generate SIF + mesh files
    generate_sif(design, mesh_path, output_dir, steel_material, elmergrid)

    # Run ElmerSolver
    execute.run_elmer_solver(str(output_dir), elmersolver=elmersolver)

    log_path = output_dir / "elmersolver.log"
    log_info = _parse_solver_log(log_path)
    if log_info["errors"]:
        raise RuntimeError(
            f"ElmerSolver failed with errors: {log_info['errors']}"
        )

    # Locate VTU output
    vtu_candidates = [
        output_dir / "case.vtu",
        output_dir / "case_t0001.vtu",
    ]
    vtu_path: Path | None = None
    for candidate in vtu_candidates:
        if candidate.exists():
            vtu_path = candidate
            break

    if vtu_path is None:
        files = [f.name for f in output_dir.iterdir()]
        raise RuntimeError(
            f"VTU output not found in {output_dir}. Files: {files}"
        )

    # Verify VTU contents
    try:
        import meshio
        vtu_mesh = meshio.read(str(vtu_path))
        has_b = "magnetic flux density" in vtu_mesh.point_data
        has_h = "magnetic field strength" in vtu_mesh.point_data
        if not (has_b and has_h):
            raise RuntimeError(
                f"VTU missing expected fields.  Point data: {list(vtu_mesh.point_data.keys())}"
            )
    except ImportError as exc:
        raise ImportError(
            "elmer_solver requires meshio to verify VTU output. "
            "Install it with: pip install meshio"
        ) from exc
    except Exception as exc:
        raise RuntimeError(f"Failed to verify VTU output: {exc}")

    return vtu_path
