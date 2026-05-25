# Assessment: Code Review (Stage 5)

**Verdict:** NO-GO

---

## Findings

- [PASS] **G5.1 — All API functions present and correctly named** — Every function listed in `docs/definition.md` Section 5 is present in `src/api.py` with matching names: `create_design`, `save_design`, `load_design`, `list_designs`, `delete_design`, `clone_design`, `switch_active_design`, `update_design_parameter`, `recalculate_derived`, `get_wire_properties`, `get_former_density`, `run_elmer_simulation`, `generate_elmer_input_files`, `parse_elmer_output`, `export_blx_csv`, `export_side_leakage_csv`, `export_results_json`, `compare_designs`, `init_database`, `set_elmer_executable_path`, `set_working_directory`, `get_default_values`.

- [PASS] **G5.2 — UI/logic separation** — `src/main_window.py` contains only PyQt6 widget code and presentation logic. All calculations, database operations, Elmer orchestration, and export logic are delegated to `src/api.py`. Input changes call `update_design_parameter()`; the Elmer button calls `run_elmer_simulation()`; save/load/delete call their respective API functions.

- [PASS] **G5.3 — No hardcoded credentials or dangerous magic numbers** — No credentials are present. The Elmer executable fallback paths (`C:\Program Files\ElmerFEM\bin\ElmerSolver.exe`) are standard Windows installation directories for an external dependency on a Windows-only application, matching the specification defaults. Formula constants (e.g., 57.37, 31.62, 5033) are verbatim Excel transcriptions required by the definition.

- [PASS] **G5.4 — No obvious security issues** — No `eval()` or `exec()` is used. Subprocess calls (`subprocess.run` in `src/elmer_integration.py` and pyelmer wrappers in `src/elmer_solver.py`) use argument lists, not shell strings, preventing shell injection. Export functions accept user-supplied paths via file dialogs; no unsafe path traversal is performed.

- [FAIL] **G5.5 — Error handling at system boundaries** — Several public API functions that cross system boundaries lack `try/except` wrappers for file I/O errors:
  - `src/api.py:generate_elmer_input_files` calls `out_dir.mkdir`, `build_geometry`, and `generate_sif` without catching `PermissionError`, `OSError`, or `ImportError`.
  - `src/elmer_integration.py:parse_elmer_output` checks `exists()` but calls `read_text()` without catching `PermissionError` or `OSError`.
  - `src/elmer_integration.py:generate_density_plot` calls `meshio.read` without catching file-read errors.
  - `src/elmer_integration.py:run_elmer_simulation` does not wrap the overall pipeline; a failure in `build_geometry`, `build_and_solve`, `extract_vc_sweep`, `generate_density_plot`, or `parse_elmer_output` propagates an unhandled exception instead of a meaningful `RuntimeError`.
  - `src/post_processor.py:write_output_files` writes text files without catching `OSError`.

- [PASS] **G5.6 — API reference accuracy** — `docs/api_reference.md` documents every exported function in `src/api.py` (`__all__`). Parameter names, types, and return types match the implementation. No documented function is missing from the implementation, and no implemented function is missing from the reference.

---

## Required Actions

1. **Wrap public API file-I/O functions in `try/except` with meaningful messages.**
   - In `src/api.py`, wrap `generate_elmer_input_files` in `try/except (OSError, PermissionError)` and re-raise as `RuntimeError` with a clear message.
   - In `src/elmer_integration.py`, wrap `parse_elmer_output` file reads in `try/except (OSError, PermissionError)`.
   - In `src/elmer_integration.py`, wrap `generate_density_plot` in `try/except (OSError, FileNotFoundError)` around `meshio.read`.
   - In `src/elmer_integration.py`, wrap the body of `run_elmer_simulation` in a `try/except Exception` that raises `RuntimeError(f"Elmer simulation failed: {e}")` so callers get a single, meaningful exception at the pipeline boundary.
   - In `src/post_processor.py`, wrap `write_output_files` file writes in `try/except OSError`.

2. **Re-run the code review after fixes to confirm G5.5 passes.**
