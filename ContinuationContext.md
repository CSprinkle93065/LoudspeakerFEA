# LoudspeakerFEA — Continuation Context

**Version:** 0.1.1 (bug fix attempted but unresolved)  
**Project Root:** `c:\Users\terav\WORKSPACE_MAOA_WinAppVibeCoder -Kimi\projects\LoudspeakerFEA`  
**GitHub:** https://github.com/teravolt/LoudspeakerFEA  
**Date:** 2026-05-24  
**Status:** Active bug — ElmerSolver STOP 1

---

## 1. Project Overview

LoudspeakerFEA is a standalone Windows desktop application (Python 3 + PyQt6 + SQLite + PyInstaller) that simulates traditional ceramic magnet woofer motors using Finite Element Analysis. It is functionally identical to **MotorModel** but replaces the proprietary **FEMM** solver with the open-source **ElmerFEM** engine.

The app replicates the `[FEMotor]` worksheet from a reference Excel workbook, including all parametric calculations, voice-coil characterization, motor geometry derivation, loudspeaker parameter estimation, BL-versus-displacement curves, and side-leakage analysis.

### Parent Projects
- **MotorModel** (`projects/MotorModel/`) — The original FEMM-based app. Source of truth for UI layout, data model, Excel formulas, and API surface.
- **Loudspeaker FEA** (`projects/Loudspeaker FEA/`) — The Elmer/Gmsh/VTK research project that produced the working pipeline. Contains a fully functional Elmer solver integration with passing integration tests (8/8). This is the **reference working code** for the Elmer pipeline.

---

## 2. Architecture

### Three-Layer Design
| Layer | Module | Responsibility |
|-------|--------|---------------|
| **Data** | `src/models.py` | `LoudspeakerDesign` dataclass |
| **Engine** | `src/engine.py` | Excel formula calculations, wire/former lookup tables |
| **Persistence** | `src/database.py` | SQLite designs/settings tables |
| **Elmer Pipeline** | `src/geometry_builder.py` | Gmsh geometry → `.msh` |
| | `src/elmer_solver.py` | pyelmer SIF generation + ElmerGrid + ElmerSolver |
| | `src/post_processor.py` | VTK VTU parsing: VC sweep, side leakage, density plot |
| | `src/materials.py` | Material definitions (Air, China Steel, magnets) |
| **Integration** | `src/elmer_integration.py` | Public facade: `run_elmer_simulation()` |
| **API** | `src/api.py` | Public API: design lifecycle, calculation, export |
| **UI** | `src/main_window.py` | PyQt6 GUI (left panel groups, right panel tabs) |
| **Entry** | `src/main.py` | Application launch point |

### File Inventory (11 modules)

| File | Lines | Purpose | Status |
|------|-------|---------|--------|
| `src/__init__.py` | 0 | Package init | OK |
| `src/models.py` | 166 | `LoudspeakerDesign` dataclass + `find_elmer_executable()` | OK |
| `src/engine.py` | 414 | All Excel formulas, JIS wire table, former densities | OK |
| `src/database.py` | 178 | SQLite persistence (designs table, settings table) | OK |
| `src/api.py` | 257 | Public API facade | OK |
| `src/main_window.py` | 592 | PyQt6 GUI | **Version string outdated** (says v0.1.0) |
| `src/main.py` | ~20 | Entry point | OK |
| `src/elmer_integration.py` | 548 | **BROKEN** — see Section 4 |
| `src/geometry_builder.py` | 336 | Copied from `Loudspeaker FEA/src/` | OK (import adapted) |
| `src/elmer_solver.py` | 456 | Copied from `Loudspeaker FEA/src/` | OK (import adapted) |
| `src/post_processor.py` | 465 | Copied from `Loudspeaker FEA/src/` | OK (import adapted) |
| `src/materials.py` | ~120 | Copied from `Loudspeaker FEA/src/` | OK |

---

## 3. Data Model (`LoudspeakerDesign`)

The dataclass in `src/models.py` contains **all** MotorModel fields (including hidden ones) plus Elmer-specific setup fields.

### Setup (Elmer)
| Field | Default | Notes |
|-------|---------|-------|
| `elmer_solver_path` | `"ElmerSolver.exe"` | Auto-detected from PATH or common install dirs |
| `working_directory` | `%TEMP%\ElmerFEA` | Temporary working dir for sim artifacts |
| `mesh_size_factor` | `1.0` | Maps to `accuracy` in geometry_builder (range 0.1–2.0) |
| `show_processor` | `0` | 0=hidden, 1=show console |
| `magnet_material` | `"Ceramic5"` | ComboBox in Motor Geometry group |

### Voice Coil (Group A — visible)
`wire_diameter`, `vc_wire_dcr`, `tinsel_wire_dcr`, `coil_id`, `coil_id_tolerance`, `former_thickness`, `former_length`, `number_of_layers`, `wire_type` (1=Cu, 2=CCA), `former_type` (1=Kapton, 2=Al, 3=Nomex, 4=Kraft), `overhang`

### Motor Geometry (Group B — visible)
`magnet_material`, `inside_gap`, `outside_gap`, `top_plate_id`, `top_plate_od`, `top_plate_thickness`, `magnet_id`, `magnet_od`, `magnet_thickness`, `pole_od`, `pole_vent_hole`, `pole_overhang`, `bp_od`, `bp_thickness`, `vc_offset`, `side_leakage_distance`

**NOT visible in UI** (removed per spec): `bucking_mag_id`, `bucking_mag_od`, `bucking_mag_thickness` — remain in dataclass with default `0.0`.

### Hidden Groups (dataclass fields, not in UI)
- Target Transducer: `target_bl`, `target_cms`, `target_mms`, `target_sd`, `target_xmax`
- Non-Coil Mass: `mass_diaphragm`, `mass_surround`, `mass_dome_coil`, `mass_spider_coil`, `mass_spider`, `diaphragm_thickness`, `diaphragm_density`
- Input Loudspeaker: `speaker_dia`, `qm`, `mms_minus_vcmass`, `cms_ls`

### Derived Fields (computed by `recalculate_derived`)
`total_vc_dcr`, `length_of_wire`, `number_of_turns`, `coil_winding_max_od`, `mass_of_former`, `mass_of_wire`, `mass_of_voice_coil`, `wire_dia_with_insulation`, `resistivity_ohms_per_m`, `length_of_wire_per_turn`, `ww`, `pole_height`, `vc_location_diameter`, `mechanical_xmax`, `bl`, `xmax_at_82bl`, `bl_at_threshold`, `max_side_leakage`, `splref`, `qes`, `qts`, `mms_total`, `fs`, `target_sens`, `interpolated_xmax`, etc.

### FEA Result Fields (populated by solver)
`fea_b`, `bl_x_data`, `side_leakage_data`, `primary_magnet_avg_b`, `secondary_magnet_avg_b`

---

## 4. The Unresolved Bug: ElmerSolver STOP 1

### Symptom
Clicking **"Calculate B (Run Elmer)"** in the GUI produces an error dialog:
```
ElmerSolver failed with code 1: STOP 1
```

### Root Cause (Confirmed)
The `src/elmer_integration.py` module has a **fatal design flaw**. Its `run_elmer_simulation()` function is wrapped in a `try/except ImportError`:

```python
def run_elmer_simulation(design, show_window=False):
    try:
        from src.geometry_builder import build_geometry
        from src.elmer_solver import build_and_solve
        from src.post_processor import extract_vc_sweep, extract_side_leakage, write_output_files
        # ... real pipeline ...
    except ImportError:
        # FALLBACK — this is what currently runs and fails
        directory = design.working_directory
        sif_path, mesh_dir = generate_elmer_input_files(design, directory)
        run_elmer_solver(sif_path, design.elmer_solver_path, show_window=show_window)
        # ...
```

The `generate_elmer_input_files()` function in the fallback path creates a **fake placeholder mesh** with **zero nodes and zero elements**:

```python
(mesh_dir / "mesh.header").write_text("1 0 0\n0\n", encoding="utf-8")
(mesh_dir / "mesh.nodes").write_text("0\n", encoding="utf-8")
(mesh_dir / "mesh.elements").write_text("0\n", encoding="utf-8")
(mesh_dir / "mesh.boundary").write_text("0\n", encoding="utf-8")
```

When ElmerSolver runs on this empty mesh, it fails with `STOP 1`.

### Why the "Fix" in v0.1.1 Did Not Work
The v0.1.1 bug fix **copied the working Elmer pipeline modules** from `projects/Loudspeaker FEA/src/` into `projects/LoudspeakerFEA/src/` and adapted their imports. However, the `run_elmer_simulation()` function in `elmer_integration.py` was rewritten to wrap the real pipeline in a `try/except ImportError` with the **same old fallback path**.

**The fallback path still contains the fake mesh.** If anything in the real pipeline raises `ImportError` (e.g., `gmsh` not found, `pyelmer` missing, `meshio` unavailable), the fallback runs and produces STOP 1.

Even worse: if the real pipeline modules ARE present but fail for ANY reason other than ImportError, the exception bubbles up to the GUI unhandled. The `except ImportError` only catches one specific exception type.

### What Should Happen
The `run_elmer_simulation()` function should:
1. **Unconditionally** call the real pipeline (no try/except ImportError fallback)
2. Let genuine errors (missing executables, solver failures, etc.) propagate with meaningful messages
3. The fake mesh placeholder code (`generate_elmer_input_files` with zero-node mesh) should be **removed entirely**

### Correct Pipeline Flow
The working flow (verified in `projects/Loudspeaker FEA/`) is:
```
1. build_geometry(design, workdir)          → Gmsh → motor.msh
2. build_and_solve(design, mesh_path, sim_dir) → ElmerGrid + ElmerSolver → case.vtu
3. extract_vc_sweep(vtu_path, design)       → 61-point BL(x) data
4. extract_side_leakage(vtu_path, design)   → 100-point leakage
5. write_output_files(workdir, ...)         → VCSweepOutput.txt + leakage contour.txt
6. generate_density_plot(vtu_path, ...)     → B-Field.png
```

### Files Involved in Fix
- **`src/elmer_integration.py`** — Must be rewritten to unconditionally call the real pipeline
- The fake mesh function `generate_elmer_input_files()` should be deleted or replaced with a wrapper that calls `build_geometry`
- The `_build_sif()` function (hand-crafted SIF) is dead code once the real pipeline is used

---

## 5. Working Reference Code

The **fully working Elmer pipeline** exists in `projects/Loudspeaker FEA/src/`. It has:
- 8/8 passing integration tests comparing Elmer against FEMM reference data
- Elmer runtime: ~184s (vs FEMM ~211s)
- Verified on the same machine/environment

Key reference files:
| File | Purpose |
|------|---------|
| `projects/Loudspeaker FEA/src/api.py` | Reference `run_elmer_simulation()` implementation |
| `projects/Loudspeaker FEA/src/geometry_builder.py` | Working Gmsh geometry builder |
| `projects/Loudspeaker FEA/src/elmer_solver.py` | Working SIF + solver runner |
| `projects/Loudspeaker FEA/src/post_processor.py` | Working VTK post-processing |
| `projects/Loudspeaker FEA/src/materials.py` | Working material definitions |
| `projects/Loudspeaker FEA/tests/test_integration.py` | 8 integration tests (all pass) |

The copied modules in `projects/LoudspeakerFEA/src/` are identical in content but with `MotorDesign` → `LoudspeakerDesign` import changes. They SHOULD work if called correctly.

### Environment
- **ElmerFEM** installed at `C:\Users\terav\ElmerFEM\bin\` (ElmerSolver.exe, ElmerGrid.exe)
- **Python venv** at `projects/Loudspeaker FEA/.venv/` with: gmsh, pyelmer, meshio, numpy, scipy, vtk, matplotlib, pytest
- The LoudspeakerFEA project does NOT have its own venv; it relies on the system Python or the user's environment

---

## 6. UI Structure

### Left Panel (QScrollArea, ~440px)
**Group A: Voice Coil** — 11 inputs + 10 derived outputs  
**Group B: Motor Geometry** — 16 inputs (no bucking magnet) + 3 derived outputs  
**Group C: Elmer FEA** — "Calculate B (Run Elmer)" button + FEA-derived outputs

### Right Panel (QTabWidget)
1. **BL(x) Curve** — matplotlib, y-axis starts at 0
2. **Side Leakage** — matplotlib
3. **FEA Geometry** — QLabel displaying `B-Field.png` (0–2 T, decimal colorbar)

### Menu Bar
- **File**: New, Open, Save, Delete, Export (BLx CSV, Leakage CSV, JSON)
- **Setup**: Elmer executable path, Working directory, Mesh size factor, Show processor
- **Help**: About

### Known UI Issue
`main_window.py` still shows version **"v0.1.0"** in window title and About dialog. Should be **"v0.1.1"** (or whatever the current version is).

---

## 7. API Surface (`src/api.py`)

All agent-accessible functions exported from `src.api`:

```python
# Design lifecycle
create_design(name="") -> LoudspeakerDesign
save_design(design) -> int
load_design(design_id) -> LoudspeakerDesign
list_designs() -> list[dict]
delete_design(design_id) -> None
clone_design(design_id, new_name="") -> LoudspeakerDesign
switch_active_design(slot) -> LoudspeakerDesign
get_default_values() -> LoudspeakerDesign

# Calculation
update_design_parameter(design, field_name, value) -> LoudspeakerDesign
recalculate_derived(design) -> LoudspeakerDesign
get_wire_properties(wire_diameter, wire_type) -> dict
get_former_density(former_type) -> float

# Elmer Simulation
run_elmer_simulation(design, show_window=False) -> LoudspeakerDesign
run_elmer_solver(sif_path, elmer_solver_path, show_window=False) -> None
generate_elmer_input_files(design, directory) -> tuple[str, str]
parse_elmer_output(directory) -> dict
generate_density_plot(vtu_path, design, output_path) -> None

# Export
export_blx_csv(design, filepath) -> None
export_side_leakage_csv(design, filepath) -> None
export_results_json(design, filepath) -> None

# Comparison
compare_designs(design_ids) -> dict

# Utility
init_database(db_path=None) -> None
set_elmer_executable_path(path) -> None
set_working_directory(path) -> None
```

---

## 8. Test Suite

5 test files, ~1026 total lines, 75 tests (all passing in v0.1.1):

| File | Lines | Tests |
|------|-------|-------|
| `tests/test_models.py` | 120 | Serialization, defaults, field access |
| `tests/test_engine.py` | 350 | Excel formula accuracy (Design 1 reference values) |
| `tests/test_api.py` | 210 | Design lifecycle, export, database |
| `tests/test_persistence.py` | 120 | SQLite CRUD |
| `tests/test_elmer_integration.py` | 226 | Mock-based Elmer tests, bug-fix verification |

**Test environments use mocking** — no live Elmer simulations during tests.

---

## 9. Packaging & Release

- **PyInstaller** in `onedir` mode
- **Spec file**: `LoudspeakerFEA.spec` (auto-generated)
- **Distribution**: `dist/LoudspeakerFEA_v{version}.zip`
- **GitHub**: Pre-releases for 0.x versions
- `.gitignore` excludes `dist/`, `build/`, `__pycache__/`

---

## 10. Known Issues & Blockers

### Blocker #1: ElmerSolver STOP 1 (ACTIVE)
- **File**: `src/elmer_integration.py`
- **Function**: `run_elmer_simulation()`
- **Problem**: `try/except ImportError` fallback contains fake mesh with zero nodes
- **Fix strategy**: Remove the try/except wrapper. Call the real pipeline unconditionally. Delete `generate_elmer_input_files()` fake mesh code. Delete `_build_sif()` dead code.

### Minor: Version String Stale
- **File**: `src/main_window.py` line 67 and line 513
- **Current**: `"LoudspeakerFEA v0.1.0"`
- **Should be**: `"LoudspeakerFEA v0.1.1"` (or current version)

### Historical: Orchestrator Protocol Violation
- Documented in `known_issues.md` — the Orchestrator initially tried to write code directly instead of spawning MAOA sub-agents. This pattern has been corrected.

---

## 11. Environment Details

| Component | Location / Version |
|-----------|-------------------|
| Python | 3.14.2 (system) |
| PyQt6 | 6.11.0 |
| ElmerFEM | V9.x at `C:\Users\terav\ElmerFEM\bin\` |
| Gmsh | Python package (`pip install gmsh`) |
| Working Python venv | `projects/Loudspeaker FEA/.venv/` (has all deps) |
| Database | `~/AppData/Local/LoudspeakerFEA/loudspeakerfea.db` |
| MAOA Workflow State | `.tmp/wvc_state_LoudspeakerFEA_*.json` |

---

## 12. Guidance for Next Agent

### To Fix the STOP 1 Bug
1. **Read** `src/elmer_integration.py` — understand the current broken `try/except ImportError` structure
2. **Read** `projects/Loudspeaker FEA/src/api.py` — see how `run_elmer_simulation()` works in the reference (unconditional pipeline)
3. **Rewrite** `src/elmer_integration.py`:
   - Remove the `try/except ImportError` wrapper around the real pipeline
   - Keep the real pipeline calls (build_geometry → build_and_solve → extract_vc_sweep → etc.)
   - Delete `generate_elmer_input_files()` or repurpose it to call `build_geometry`
   - Delete `_build_sif()` dead code
   - Keep `parse_elmer_output()` — it reads the text files correctly
   - Keep `generate_density_plot()` — it works
4. **Verify** imports: `from src.geometry_builder import build_geometry`, `from src.elmer_solver import build_and_solve`, etc.
5. **Update** `src/main_window.py` version strings to current version
6. **Run** `python -m pytest tests/` to ensure no regressions
7. **Do NOT** run live Elmer simulations during development (3+ min each)

### File Change Checklist
- [ ] `src/elmer_integration.py` — rewrite run_elmer_simulation(), remove fake mesh
- [ ] `src/main_window.py` — update version strings
- [ ] `tests/test_elmer_integration.py` — update mocks if needed
- [ ] `docs/qa_results.md` — update after test run
