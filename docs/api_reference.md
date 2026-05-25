# LoudspeakerFEA — API Reference

**Version:** 0.1.2  
**Module:** `src.api`

All public functions are exported from `src.api`.  These are the only entry points that AI agents and the UI should use.

---

## Data Class

### `LoudspeakerDesign`

Primary design entity — one column in the FEMotor spreadsheet.  A `@dataclass` with all input, derived, and array fields.  See `src.models` for the full field list.

---

## Design Lifecycle

### `create_design(name: str = "") -> LoudspeakerDesign`

Create a new `LoudspeakerDesign` with default values matching Design 1 of the reference spreadsheet.  Formula-default inputs (overhang, top_plate_id, pole_od, speaker_dia, mms_minus_vcmass, cms_ls) are computed automatically.

**Parameters:**
- `name` — Optional design name.

**Returns:**
- A fully-initialised `LoudspeakerDesign` instance.

**Example:**
```python
from src.api import create_design
d = create_design(name="MyDesign")
print(d.wire_diameter)  # 0.5
```

---

### `get_default_values() -> LoudspeakerDesign`

Return a `LoudspeakerDesign` instance populated with the exact default values from Design 1 of the reference spreadsheet.  Equivalent to `create_design(name="")`.

**Example:**
```python
from src.api import get_default_values
d = get_default_values()
assert d.magnet_material == "Ceramic5"
```

---

### `save_design(design: LoudspeakerDesign) -> int`

Serialize `design` to JSON and store in SQLite.  Returns the design ID (primary key).

**Parameters:**
- `design` — The design to persist.

**Returns:**
- `int` — Database primary key of the saved design.

**Example:**
```python
from src.api import create_design, save_design
d = create_design(name="Test")
d_id = save_design(d)
```

---

### `load_design(design_id: int) -> LoudspeakerDesign`

Retrieve a design from SQLite by ID.

**Parameters:**
- `design_id` — Primary key of the saved design.

**Returns:**
- A populated `LoudspeakerDesign`.

**Raises:**
- `ValueError` — If the ID does not exist.

**Example:**
```python
from src.api import load_design
d = load_design(1)
```

---

### `list_designs() -> list[dict]`

Return a list of all saved designs.

**Returns:**
- `list[dict]` — Each dict has keys `id`, `name`, `updated_at`.

**Example:**
```python
from src.api import list_designs
designs = list_designs()
for d in designs:
    print(d["id"], d["name"])
```

---

### `delete_design(design_id: int) -> None`

Delete the design from SQLite.

**Parameters:**
- `design_id` — Primary key of the design to delete.

**Raises:**
- `ValueError` — If the ID does not exist.

**Example:**
```python
from src.api import delete_design
delete_design(1)
```

---

### `clone_design(design_id: int, new_name: str = "") -> LoudspeakerDesign`

Deep-copy an existing design, assign a new name, and return the copy (not yet saved).

**Parameters:**
- `design_id` — Primary key of the design to clone.
- `new_name` — Name for the cloned design.

**Returns:**
- A new `LoudspeakerDesign` with `id=None`.

**Example:**
```python
from src.api import clone_design
cloned = clone_design(1, new_name="Copy")
```

---

### `switch_active_design(slot: int) -> LoudspeakerDesign`

Switch the active in-memory design to the specified slot (1–8).

**Parameters:**
- `slot` — Slot number (1–8).

**Returns:**
- The `LoudspeakerDesign` now active in that slot.  If the slot is empty, initialises it with default values.

**Example:**
```python
from src.api import switch_active_design
d = switch_active_design(slot=2)
```

---

## Calculation (No Elmer)

### `update_design_parameter(design: LoudspeakerDesign, field_name: str, value: float | int | str) -> LoudspeakerDesign`

Set a single input field on the design by name and trigger `recalculate_derived()`.

**Parameters:**
- `design` — The design to modify.
- `field_name` — Attribute name (e.g. `"wire_diameter"`, `"top_plate_thickness"`).
- `value` — New value.

**Returns:**
- The updated design.

**Raises:**
- `AttributeError` — If the field does not exist.

**Example:**
```python
from src.api import create_design, update_design_parameter
d = create_design()
d = update_design_parameter(d, "top_plate_thickness", 15.0)
print(d.pole_height)  # 68.0
```

---

### `recalculate_derived(design: LoudspeakerDesign) -> LoudspeakerDesign`

Recompute every derived field in the design (all groups, including hidden ones) using the exact Excel formulas.  Does **not** call Elmer.

**Parameters:**
- `design` — The design to recalculate.

**Returns:**
- The updated design.

**Example:**
```python
from src.api import create_design, recalculate_derived
d = create_design()
d = recalculate_derived(d)
print(d.total_vc_dcr)  # 3.5
```

---

### `get_wire_properties(wire_diameter: float, wire_type: int) -> dict`

Look up the JIS wire gauge table and return wire properties.

**Parameters:**
- `wire_diameter` — Wire diameter in mm.
- `wire_type` — `1` = Copper, `2` = CCA.

**Returns:**
- `dict` with keys:
  - `max_od_with_insulation` — mm
  - `resistance_ohm_per_km` — Ω/km
  - `mass_kg_per_km` — kg/km

**Example:**
```python
from src.api import get_wire_properties
props = get_wire_properties(0.5, 1)
print(props["max_od_with_insulation"])  # 0.542
```

---

### `get_former_density(former_type: int) -> float`

Return the density (g/cm³) for the given former type ID.

**Parameters:**
- `former_type` — `1`=Kapton, `2`=Aluminum, `3`=Nomex, `4`=Kraft.

**Returns:**
- Density in g/cm³.

**Example:**
```python
from src.api import get_former_density
print(get_former_density(1))  # 1.43
```

---

## Elmer Simulation

### `run_elmer_simulation(design: LoudspeakerDesign, show_window: bool = False) -> LoudspeakerDesign`

Generate Elmer SIF and mesh from the design parameters, launch `ElmerSolver.exe`, execute the analysis, parse output files, and populate `design.fea_b`, `design.bl`, `design.bl_x_data`, `design.side_leakage_data`, `design.primary_magnet_avg_b`, and all dependent derived fields.

**Parameters:**
- `design` — The design to simulate.
- `show_window` — If `True`, show the solver console window (Windows only).

**Returns:**
- The updated design with FEA results.

**Raises:**
- `RuntimeError` — If the solver fails.
- `FileNotFoundError` — If the executable or output files are missing.

**Example:**
```python
from src.api import create_design, run_elmer_simulation
d = create_design()
d = run_elmer_simulation(d)
print(d.bl)
```

---



### `generate_density_plot(vtu_path: str | Path, design: LoudspeakerDesign, output_path: str | Path) -> None`

Generate and save a B-field density plot PNG from a solved Elmer VTU file.

Uses a **fixed color scale of 0–2 T** with **decimal tick labels** (no scientific notation) on the colorbar.

**Parameters:**
- `vtu_path` — Path to the Elmer `.vtu` output file.
- `design` — Design parameters (used for title/annotation).
- `output_path` — Destination path for the PNG image.

**Raises:**
- `ImportError` — If `meshio`, `numpy`, or `matplotlib` are not installed.

**Example:**
```python
from src.api import generate_density_plot, create_design
from pathlib import Path
d = create_design()
generate_density_plot(Path("case.vtu"), d, Path("B-Field.png"))
```

---

### `parse_elmer_output(directory: str) -> dict`

Parse `VCSweepOutput.txt` and `leakage contour.txt` in the given directory.

**Parameters:**
- `directory` — Directory containing the output files.

**Returns:**
- `dict` with keys:
  - `b_at_zero` — float
  - `data_points` — int
  - `bmagnet` — float
  - `bbuck` — float
  - `vc_sweep` — list of `(position, B_avg)` tuples
  - `raw_b` — list of `(position, |B|)` tuples
  - `side_leakage` — list of |B| floats

**Raises:**
- `FileNotFoundError` — If expected files are missing.

**Example:**
```python
from src.api import parse_elmer_output
result = parse_elmer_output(r"C:\ElmerFEA")
print(result["b_at_zero"])
```

---

## Export

### `export_blx_csv(design: LoudspeakerDesign, filepath: str) -> None`

Write the BL(x) data to a CSV file with columns `x_mm`, `BL_Tm`.

**Parameters:**
- `design` — Design containing `bl_x_data`.
- `filepath` — Destination file path.

**Example:**
```python
from src.api import create_design, export_blx_csv
d = create_design()
d.bl_x_data = [(-10.0, 6.5), (0.0, 8.0), (10.0, 6.5)]
export_blx_csv(d, "blx.csv")
```

---

### `export_side_leakage_csv(design: LoudspeakerDesign, filepath: str) -> None`

Write the side leakage data to a CSV file with columns `index`, `leakage_G`.

**Parameters:**
- `design` — Design containing `side_leakage_data`.
- `filepath` — Destination file path.

**Example:**
```python
from src.api import create_design, export_side_leakage_csv
d = create_design()
d.side_leakage_data = [0.1, 0.2, 0.3]
export_side_leakage_csv(d, "leakage.csv")
```

---

### `export_results_json(design: LoudspeakerDesign, filepath: str) -> None`

Write a JSON file containing all input and output fields of the design.

**Parameters:**
- `design` — Design to export.
- `filepath` — Destination file path.

**Example:**
```python
from src.api import create_design, export_results_json
d = create_design(name="ExportTest")
export_results_json(d, "results.json")
```

---

## Comparison

### `compare_designs(design_ids: list[int]) -> dict`

Load the specified designs and return a comparison dict.

**Parameters:**
- `design_ids` — List of design primary keys to compare.

**Returns:**
- `dict[int, dict[str, Any]]` — Outer dict keyed by design ID; inner dict contains metrics (`Name`, `Bl`, `Xmax`, `SPLref`, `Qts`, `Fs`, `Qes`, `Mms`, `TargetSens`, `MaxSideLeakage`, `PrimaryMagnetB`, `SecondaryMagnetB`).

**Example:**
```python
from src.api import compare_designs
result = compare_designs([1, 2])
print(result[1]["Bl"])
```

---

## Utility

### `init_database(db_path: str | None = None) -> None`

Create the SQLite database and `designs` / `settings` tables if they do not exist.

**Parameters:**
- `db_path` — Optional custom database path.  Uses default (`~/AppData/Local/LoudspeakerFEA/loudspeakerfea.db`) if `None`.

**Example:**
```python
from src.api import init_database
init_database()
```

---

### `set_elmer_executable_path(path: str) -> None`

Update the application's global setting for the ElmerSolver executable path.  Persisted in the SQLite settings table.

**Parameters:**
- `path` — Absolute path to `ElmerSolver.exe`.

**Example:**
```python
from src.api import set_elmer_executable_path
set_elmer_executable_path(r"C:\Users\terav\ElmerFEM\bin\ElmerSolver.exe")
```

---

### `set_working_directory(path: str) -> None`

Update the application's global setting for the working directory.  Persisted in the SQLite settings table.

**Parameters:**
- `path` — Working directory path.

**Example:**
```python
from src.api import set_working_directory
set_working_directory(r"C:\ElmerFEA")
```

---

### `set_setting(key: str, value: str) -> None`

Persist a global setting to the SQLite settings table.

**Parameters:**
- `key` — Setting key.
- `value` — Setting value.

**Example:**
```python
from src.api import set_setting
set_setting("elmer_solver_path", r"C:\ElmerFEM\bin\ElmerSolver.exe")
```

---

### `get_setting(key: str, default: str = "") -> str`

Retrieve a global setting from the SQLite settings table.

**Parameters:**
- `key` — Setting key.
- `default` — Default value if the key is not found.

**Returns:**
- The stored value or `default`.

**Example:**
```python
from src.api import get_setting
path = get_setting("elmer_solver_path", r"C:\ElmerFEM\bin\ElmerSolver.exe")
```

---

### `run_elmer_solver(sif_path: str, elmer_solver_path: str, show_window: bool = False) -> None`

Run ElmerSolver.exe for the given SIF file.

**Parameters:**
- `sif_path` — Path to the Elmer SIF file.
- `elmer_solver_path` — Path to the ElmerSolver executable.
- `show_window` — If `True`, show the solver console window (Windows only).

**Raises:**
- `RuntimeError` — If the solver returns a non-zero exit code.
- `FileNotFoundError` — If the executable is not found.

**Example:**
```python
from src.api import run_elmer_solver
run_elmer_solver(r"C:\ElmerFEA\spkr.sif", r"C:\ElmerFEM\bin\ElmerSolver.exe")
```

---

### `initialize_formula_defaults(design: LoudspeakerDesign) -> LoudspeakerDesign`

Set formula-default input fields to their computed values.  Called internally by `create_design()`.

**Parameters:**
- `design` — The design to initialise.

**Returns:**
- The updated design.

**Example:**
```python
from src.api import LoudspeakerDesign, initialize_formula_defaults
d = LoudspeakerDesign()
d = initialize_formula_defaults(d)
```

---

## Module Exports

```python
__all__ = [
    "LoudspeakerDesign",
    "create_design",
    "get_default_values",
    "save_design",
    "load_design",
    "list_designs",
    "delete_design",
    "clone_design",
    "switch_active_design",
    "update_design_parameter",
    "recalculate_derived",
    "get_wire_properties",
    "get_former_density",
    "run_elmer_simulation",
    "run_elmer_solver",

    "parse_elmer_output",
    "generate_density_plot",
    "export_blx_csv",
    "export_side_leakage_csv",
    "export_results_json",
    "compare_designs",
    "init_database",
    "set_elmer_executable_path",
    "set_working_directory",
    "get_setting",
    "set_setting",
]
```
