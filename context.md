# LoudspeakerFEA — Project Context

**Version:** 0.1.0  
**GitHub Repository:** https://github.com/CSprinkle93065/LoudspeakerFEA  
**Release Stage:** Stage 8 — Release  
**Workflow ID:** wvc_20260524_140930  
**Date:** 2026-05-24  

---

## Overview

LoudspeakerFEA is a Finite Element Analysis (FEA) augmented desktop application that simulates traditional ceramic magnet woofer motors. It duplicates the functionality of the `[FEMotor]` worksheet in the reference Excel workbook, including all parametric calculations, voice-coil characterization, motor geometry derivation, loudspeaker parameter estimation, BL-versus-displacement curves, and side-leakage analysis.

The program drives the open-source **ElmerFEM** engine to perform the magnetic-field simulation and extracts results for display and further calculation.

## Derived From

- **MotorModel v0.1.12** — Base functionality and UI layout pattern
- **LoudspeakerDesigner** — UI pattern (left panel scrollable groups, right panel tabs)

## Key Changes from MotorModel

1. **Replaced FEMM with ElmerFEM** — Elmer SIF generation, mesh creation, solver invocation, and VTU/EP output parsing replace FEMM Lua macros and file formats.
2. **Setup menu updated for Elmer** — Controls: Elmer executable path, working directory, mesh size factor, show processor option.
3. **Removed bucking magnet inputs from UI** — Fields remain in data model (default `0.0`) for backward compatibility but are hidden.
4. **FEA Geometry plot scaling** — B-field density plot uses a fixed scale of 0–2 T with decimal tick labels (no scientific notation).

## Technology Stack

- Python 3.11+ (64-bit)
- PyQt6 6.6+
- SQLite 3.39+
- matplotlib 3.8+
- ElmerFEM (external dependency)
- pytest 8.0+
- PyInstaller 6.0+

## Project Structure

```
LoudspeakerFEA/
├── src/
│   ├── main_window.py      # PyQt6 UI
│   ├── models.py           # LoudspeakerDesign dataclass
│   ├── elmer_integration.py # Elmer SIF/mesh/solver interface
│   ├── engine.py           # Calculation engine (Excel formulas)
│   ├── api.py              # Public API surface
│   ├── database.py         # SQLite persistence
│   └── main.py             # Application entry point
├── tests/                  # Unit and integration tests
├── docs/                   # Definition, API reference, QA results
├── dist/                   # PyInstaller distribution (not in git)
└── build/                  # PyInstaller build artifacts (not in git)
```

## API Entry Points

All agent-accessible functions are exported from `src.api`:

- Design lifecycle: `create_design`, `save_design`, `load_design`, `list_designs`, `delete_design`, `clone_design`, `switch_active_design`
- Calculation: `update_design_parameter`, `recalculate_derived`, `get_wire_properties`, `get_former_density`
- Elmer Simulation: `run_elmer_simulation`, `generate_elmer_input_files`, `parse_elmer_output`
- Export: `export_blx_csv`, `export_side_leakage_csv`, `export_results_json`
- Comparison: `compare_designs`
- Utility: `init_database`, `set_elmer_executable_path`, `set_working_directory`, `get_default_values`

## Release Notes

This is a pre-release (v0.1.0). The distribution zip is attached to the GitHub release.

---

*Generated during Stage 8 — Release*
