# Project Context: LoudspeakerFEA

**Current Version:** 0.1.5
**GitHub Repository:** https://github.com/CSprinkle93065/LoudspeakerFEA
**Release Stage:** release
**Git Branch:** main
**Last Updated:** 2026-05-25T13:37:26+08:00

## What This Version Contains

LoudspeakerFEA is a Finite Element Analysis (FEA) augmented desktop application that simulates traditional ceramic magnet woofer motors. It duplicates the functionality of the `[FEMotor]` worksheet in the reference Excel workbook, including all parametric calculations, voice-coil characterization, motor geometry derivation, loudspeaker parameter estimation, BL-versus-displacement curves, and side-leakage analysis.

The program drives the open-source **ElmerFEM** engine to perform the magnetic-field simulation and extracts results for display and further calculation. In v0.1.4, the FEA Geometry tab now correctly displays the B-Field density plot after running Elmer simulation by saving the image to the working directory instead of a temporary folder.

## Version History

| Version | Type | Date | Summary |
|---------|------|------|---------|
| 0.1.5 | bug_fix | 2026-05-25 | Fix motor geometry zoom, BL(x) sweep alignment, button busy state |
| 0.1.4 | bug_fix | 2026-05-25 | Fix FEA Geometry image display — use working_directory instead of temp folder |
| 0.1.3 | bug_fix | 2026-05-25 | Fix Elmer/Gmsh integration — install dependencies, add integration smoke tests, bundle material data |
| 0.1.2 | bug_fix | 2026-05-25 | Fix ElmerSolver STOP 1 — remove fake mesh fallback, unconditionally call real pipeline |
| 0.1.1 | bug_fix | 2026-05-24 | Attempted Elmer pipeline integration (bug unresolved) |
| 0.1.0 | new_project | 2026-05-24 | Initial pre-release |

## Open Work Items
None

## Definition Summary

All agent-accessible functions are exported from `src.api`:

- **Design lifecycle:** `create_design`, `save_design`, `load_design`, `list_designs`, `delete_design`, `clone_design`, `switch_active_design`
- **Calculation:** `update_design_parameter`, `recalculate_derived`, `get_wire_properties`, `get_former_density`
- **Elmer Simulation:** `run_elmer_simulation`, `generate_elmer_input_files`, `parse_elmer_output`
- **Export:** `export_blx_csv`, `export_side_leakage_csv`, `export_results_json`
- **Comparison:** `compare_designs`
- **Utility:** `init_database`, `set_elmer_executable_path`, `set_working_directory`, `get_default_values`

**Technology Stack:** Python 3.11+, PyQt6 6.6+, SQLite 3.39+, matplotlib 3.8+, ElmerFEM (external), pytest 8.0+, PyInstaller 6.0+.
