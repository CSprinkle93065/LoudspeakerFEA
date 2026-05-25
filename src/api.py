"""Public API facade for LoudspeakerFEA.

All functions are exported from src.api and are the only entry points
that AI agents and the UI should use.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.models import LoudspeakerDesign, find_elmer_executable
from src.database import (
    init_database,
    save_design as _save_design,
    load_design as _load_design,
    list_designs as _list_designs,
    delete_design as _delete_design,
    set_setting,
    get_setting,
)
from src.engine import (
    recalculate_derived,
    initialize_formula_defaults,
    get_wire_properties,
    get_former_density,
)
from src.elmer_integration import (
    generate_density_plot,
    parse_elmer_output,
    run_elmer_simulation,
    run_elmer_solver,
)

# ─── Active Design Slots (1–8) ───────────────────────────────────────────────
_active_slots: dict[int, LoudspeakerDesign] = {}


# ─── Design Lifecycle ────────────────────────────────────────────────────────

def create_design(name: str = "") -> LoudspeakerDesign:
    """Create a new LoudspeakerDesign with default values matching Design 1 of the reference spreadsheet.

    Returns the design object.
    """
    design = LoudspeakerDesign(name=name)
    design = initialize_formula_defaults(design)
    # Prefer persisted paths; if none exist, auto-detect and persist discovery
    try:
        persisted_solver = get_setting("elmer_solver_path", "")
        if persisted_solver:
            design.elmer_solver_path = persisted_solver
        else:
            detected = find_elmer_executable()
            design.elmer_solver_path = detected
            set_elmer_executable_path(detected)

        persisted_wd = get_setting("working_directory", "")
        if persisted_wd:
            design.working_directory = persisted_wd
        else:
            set_working_directory(design.working_directory)
    except RuntimeError:
        # Database not initialized yet — ignore persistence
        pass
    return design


def get_default_values() -> LoudspeakerDesign:
    """Return a LoudspeakerDesign instance populated with the exact default values from Design 1."""
    return create_design(name="")


def save_design(design: LoudspeakerDesign) -> int:
    """Serialize design to JSON and store in SQLite. Returns the design ID (primary key)."""
    return _save_design(design)


def load_design(design_id: int) -> LoudspeakerDesign:
    """Retrieve a design from SQLite by ID. Returns a populated LoudspeakerDesign."""
    return _load_design(design_id)


def list_designs() -> list[dict]:
    """Return a list of all saved designs as dicts with keys id, name, updated_at."""
    return _list_designs()


def delete_design(design_id: int) -> None:
    """Delete the design from SQLite. Raises ValueError if ID not found."""
    _delete_design(design_id)


def clone_design(design_id: int, new_name: str = "") -> LoudspeakerDesign:
    """Deep-copy an existing design, assign a new name, and return the copy (not yet saved)."""
    original = _load_design(design_id)
    data = original.to_dict()
    data["id"] = None
    data["name"] = new_name
    return LoudspeakerDesign.from_dict(data)


def switch_active_design(slot: int) -> LoudspeakerDesign:
    """Switch the active in-memory design to the specified slot (1–8).

    Returns the LoudspeakerDesign now active in that slot. If the slot is empty,
    initializes it with default values.
    """
    if slot not in _active_slots:
        _active_slots[slot] = create_design(name=f"Design{slot}")
    return _active_slots[slot]


# ─── Calculation (No Elmer) ──────────────────────────────────────────────────

def update_design_parameter(design: LoudspeakerDesign, field_name: str, value: float | int | str) -> LoudspeakerDesign:
    """Set a single input field on the design by name and trigger recalculate_derived().

    Returns the updated design.
    """
    if not hasattr(design, field_name):
        raise AttributeError(f"LoudspeakerDesign has no field '{field_name}'")
    # Type coercion: match the dataclass field type if possible
    field_type = type(getattr(design, field_name))
    if field_type in (int,) and isinstance(value, float):
        value = int(value)
    elif field_type in (float,) and isinstance(value, int):
        value = float(value)
    setattr(design, field_name, value)
    design = recalculate_derived(design)
    return design


# ─── Elmer Simulation ────────────────────────────────────────────────────────

# Re-export run_elmer_simulation from elmer_integration with the same signature
# so that tests can patch src.api.run_elmer_solver if needed.
run_elmer_solver = run_elmer_solver
run_elmer_simulation = run_elmer_simulation
parse_elmer_output = parse_elmer_output


# ─── Export ──────────────────────────────────────────────────────────────────

def export_blx_csv(design: LoudspeakerDesign, filepath: str) -> None:
    """Write the BL(x) data to a CSV file with columns x_mm, BL_Tm."""
    path = Path(filepath)
    lines = ["x_mm,BL_Tm"]
    for x_mm, bl_tm in design.bl_x_data:
        lines.append(f"{x_mm},{bl_tm}")
    try:
        path.write_text("\n".join(lines), encoding="utf-8")
    except OSError as e:
        raise RuntimeError(f"Failed to write BL(x) CSV to {filepath}: {e}") from e


def export_side_leakage_csv(design: LoudspeakerDesign, filepath: str) -> None:
    """Write the side leakage data to a CSV file with columns index, leakage_G."""
    path = Path(filepath)
    lines = ["index,leakage_G"]
    for idx, val in enumerate(design.side_leakage_data):
        lines.append(f"{idx},{val}")
    try:
        path.write_text("\n".join(lines), encoding="utf-8")
    except OSError as e:
        raise RuntimeError(f"Failed to write side leakage CSV to {filepath}: {e}") from e


def export_results_json(design: LoudspeakerDesign, filepath: str) -> None:
    """Write a JSON file containing all input and output fields of the design."""
    path = Path(filepath)
    data = design.to_dict()
    try:
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except OSError as e:
        raise RuntimeError(f"Failed to write results JSON to {filepath}: {e}") from e


# ─── Comparison ──────────────────────────────────────────────────────────────

def compare_designs(design_ids: list[int]) -> dict:
    """Load the specified designs and return a comparison dict.

    Result is keyed by design ID; each value is a dict of metrics
    (Bl, Xmax, SPLref, Qts, Fs, etc.).
    """
    result: dict[int, dict[str, Any]] = {}
    for did in design_ids:
        design = _load_design(did)
        result[did] = {
            "Name": design.name,
            "Bl": design.bl,
            "Xmax": design.xmax_at_82bl,
            "SPLref": design.splref,
            "Qts": design.qts,
            "Fs": design.fs,
            "Qes": design.qes,
            "Mms": design.mms_total,
            "TargetSens": design.target_sens,
            "MaxSideLeakage": design.max_side_leakage,
            "PrimaryMagnetB": design.primary_magnet_avg_b,
            "SecondaryMagnetB": design.secondary_magnet_avg_b,
        }
    return result


# ─── Utility ─────────────────────────────────────────────────────────────────

def set_elmer_executable_path(path: str) -> None:
    """Update the application's global setting for the ElmerSolver executable path."""
    set_setting("elmer_solver_path", path)


def set_working_directory(path: str) -> None:
    """Update the application's global setting for the working directory."""
    set_setting("working_directory", path)


__all__ = [
    # Data class
    "LoudspeakerDesign",
    # Design lifecycle
    "create_design",
    "get_default_values",
    "save_design",
    "load_design",
    "list_designs",
    "delete_design",
    "clone_design",
    "switch_active_design",
    # Calculation
    "update_design_parameter",
    "recalculate_derived",
    "get_wire_properties",
    "get_former_density",
    # Elmer
    "run_elmer_simulation",
    "run_elmer_solver",
    "find_elmer_executable",
    "parse_elmer_output",
    "generate_density_plot",
    # Export
    "export_blx_csv",
    "export_side_leakage_csv",
    "export_results_json",
    # Comparison
    "compare_designs",
    # Utility
    "init_database",
    "set_elmer_executable_path",
    "set_working_directory",
    "get_setting",
    "set_setting",
]
