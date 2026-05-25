"""Material property loader and Elmer SIF generator.

Loads material definitions from YAML files in ``data/materials/`` and converts
them to Elmer ``Material`` blocks.  For nonlinear materials the B–H curve is
converted to a relative-permeability vs. H table.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

# Absolute path to the bundled material files
_MATERIALS_DIR = Path(__file__).resolve().parent.parent / "data" / "materials"

MU0 = 4.0 * math.pi * 1e-7  # H/m


def load_material(name: str) -> dict[str, Any]:
    """Load a material definition from its YAML file.

    Parameters
    ----------
    name:
        Material identifier.  The file ``{name}.yaml`` is searched in
        ``data/materials/``.  Spaces in *name* are replaced with underscores
        for the filename lookup.

    Returns
    -------
    dict with the parsed YAML content.

    Raises
    ------
    FileNotFoundError: if the YAML file does not exist.
    ImportError: if PyYAML is not installed.
    """
    try:
        import yaml
    except ImportError as exc:
        raise ImportError(
            "materials requires PyYAML to be installed. "
            "Install it with: pip install PyYAML"
        ) from exc

    safe_name = name.replace(" ", "_").lower()
    path = _MATERIALS_DIR / f"{safe_name}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Material file not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _bh_to_mur_h(bh_curve: list[list[float]]) -> list[list[float]]:
    """Convert a B–H curve to a μr–H table for Elmer.

    Elmer's nonlinear magnetostatics solver expects ``Relative Permeability``
    as a function of |H|.  The conversion is:

        μr = B / (μ₀ · H)

    At H = 0 we use the initial slope (first two points) to avoid division by
    zero.

    Parameters
    ----------
    bh_curve:
        List of ``[H_A_m, B_T]`` pairs.

    Returns
    -------
    List of ``[H_A_m, mur]`` pairs.
    """
    if len(bh_curve) < 2:
        raise ValueError("B-H curve must contain at least two points")

    mur_h = []

    # H = 0 → use initial slope
    h0, b0 = bh_curve[0]
    h1, b1 = bh_curve[1]
    if h0 != 0.0:
        raise ValueError("First B-H point must be at H=0")

    if b0 == 0.0:
        initial_mur = (b1 - b0) / (MU0 * (h1 - h0))
    else:
        initial_mur = b0 / (MU0 * h0)  # should not happen if b0==0

    mur_h.append([0.0, initial_mur])

    # Remaining points
    for h, b in bh_curve[1:]:
        if h <= 0.0:
            continue
        mur = b / (MU0 * h)
        mur_h.append([h, mur])

    return mur_h


def to_elmer_sif(material: dict[str, Any]) -> str:
    """Return an Elmer SIF ``Material`` block for the given material dict.

    Parameters
    ----------
    material:
        Dictionary as returned by :func:`load_material`.

    Returns
    -------
    SIF snippet string.
    """
    name = material["name"]
    mat_type = material.get("type", "linear")
    lines = [f"Material {name}", f'  Name = "{name}"']

    if mat_type == "linear":
        lines.append(f"  Relative Permeability = {material['relative_permeability']}")
        if material.get("magnetization_A_m", 0) != 0:
            lines.append(f"  Magnetization 1 = {material['magnetization_A_m']}")

    elif mat_type == "linear_permanent_magnet":
        lines.append(f"  Relative Permeability = {material['relative_permeability']}")
        lines.append(f"  Magnetization 1 = {material['magnetization_A_m']}")

    elif mat_type == "nonlinear_bh_curve":
        mur_h = _bh_to_mur_h(material["bh_curve"])
        # Build the variable/real table
        h_vals = " ".join(str(round(pt[0], 6)) for pt in mur_h)
        mur_vals = " ".join(str(round(pt[1], 6)) for pt in mur_h)
        lines.append("  Relative Permeability = Variable magnetic field")
        lines.append(f"    Real LUT")
        lines.append(f"      {h_vals}")
        lines.append(f"      {mur_vals}")
        lines.append("    End")
        lines.append("  End")

    else:
        raise ValueError(f"Unknown material type: {mat_type}")

    lines.append("End")
    return "\n".join(lines)


# Convenience lookup for the materials used by LoudspeakerDesign
MATERIAL_NAMES = [
    "Air",
    "NdFe38",
    "NdFe48",
    "NdFe35",
    "NdFe38 High Temp",
    "NdFe39 Super High Temp",
    "NdFe38 Ultra High Temp",
    "China Steel",
    "Ceramic5",
]
