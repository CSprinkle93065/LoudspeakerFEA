# LoudspeakerFEA — QA Results

**Version:** 0.1.7  
**Workflow ID:** wvc_20260525_103543  
**Stage:** 6 — Automated Testing  
**Date:** 2026-05-25  
**Tester:** QA Agent  

---

## 1. Executive Summary

| Metric | Value |
|--------|-------|
| Total tests collected | 84 |
| Passed | 84 |
| Failed | 0 |
| Skipped | 0 |
| Collection errors | 0 |
| **Verdict** | **GO** |

The only code change in v0.1.7 is the default `mesh_size_factor` reduced from `1.0` to `0.24` in `src/models.py`, plus version-string updates in `src/main_window.py` and `docs/api_reference.md`. A new regression test (`TC-M06`) was added to `tests/test_models.py` to lock in the corrected default. All 84 existing tests continue to pass, including the live end-to-end Elmer pipeline smoke test.

---

## 2. Test Environment

| Item | Value |
|------|-------|
| Platform | win32 |
| Python | 3.14.2 |
| pytest | 9.0.3 |
| ElmerSolver.exe | `C:\Users\terav\ElmerFEM\bin\ElmerSolver.exe` (found and readable) |
| gmsh | installed (integration smoke tests exercised real mesh generation) |
| pyelmer / meshio | installed |

---

## 3. Test Results by File

### 3.1 `tests/test_api.py` — 18 tests

| Test Case | Status | TC ID |
|-----------|--------|-------|
| `test_update_design_parameter` | **PASS** | TC-01 |
| `test_create_design` | **PASS** | TC-03 |
| `test_save_design` | **PASS** | TC-04 |
| `test_load_design` | **PASS** | TC-05 |
| `test_delete_design` | **PASS** | TC-06 |
| `test_clone_design` | **PASS** | TC-16 |
| `test_list_designs` | **PASS** | TC-17 |
| `test_switch_active_design` | **PASS** | TC-10 |
| `test_compare_designs` | **PASS** | TC-11 |
| `test_export_blx_csv` | **PASS** | TC-07 |
| `test_export_side_leakage_csv` | **PASS** | TC-08 |
| `test_export_results_json` | **PASS** | TC-09 |
| `test_set_elmer_executable_path` | **PASS** | TC-12 |
| `test_set_working_directory` | **PASS** | TC-13 |
| `test_view_about_has_no_api` | **PASS** | TC-14 |
| `test_recalculate_derived` | **PASS** | TC-15 |
| `test_get_default_values` | **PASS** | TC-18 |
| `test_run_elmer_simulation_mocked` | **PASS** | TC-02 |

### 3.2 `tests/test_elmer_integration.py` — 11 tests

| Test Case | Status | TC ID |
|-----------|--------|-------|
| `test_parse_elmer_output` | **PASS** | TC-22 |
| `test_run_elmer_simulation_mocked` | **PASS** | TC-E03 |
| `test_missing_elmer_executable_raises` | **PASS** | TC-E06 |
| `test_missing_output_files_raises` | **PASS** | TC-E07 |
| `test_secondary_magnet_avg_b_is_na` | **PASS** | TC-E08 |
| `test_no_fake_mesh_placeholders` | **PASS** | — |
| `test_real_pipeline_modules_importable` | **PASS** | — |
| `test_run_elmer_simulation_signature_preserved` | **PASS** | — |
| `test_run_elmer_simulation_calls_real_pipeline` | **PASS** | — |
| `test_generate_elmer_input_files` | **PASS** | TC-21 |
| `test_density_plot_uses_motor_bounds` | **PASS** | — |
| `test_extract_vc_sweep_raw_b_and_bmagnet` | **PASS** | — |
| `test_button_busy_state_in_on_run_elmer` | **PASS** | — |
| `test_density_plot_includes_geometry_overlays` | **PASS** | — |

### 3.3 `tests/test_engine.py` — 29 tests

| Test Case | Status | TC ID |
|-----------|--------|-------|
| `test_total_vc_dcr_formula_c14` | **PASS** | TC-F01 |
| `test_ww_formula_c15` | **PASS** | TC-F02 |
| `test_selected_wire_type_formula_c22` | **PASS** | TC-F03 |
| `test_length_of_wire_formula_c26` | **PASS** | TC-F04 |
| `test_number_of_turns_formula_c27` | **PASS** | TC-F05 |
| `test_coil_winding_max_od_formula_c28` | **PASS** | TC-F06 |
| `test_mass_of_former_formula_c29` | **PASS** | TC-F07 |
| `test_mass_of_wire_formula_c30` | **PASS** | TC-F08 |
| `test_mass_of_voice_coil_formula_c31` | **PASS** | TC-F09 |
| `test_wire_dia_with_insulation_lookup_c32` | **PASS** | TC-F10 |
| `test_resistivity_ohms_per_m_formula_c33` | **PASS** | TC-F11 |
| `test_length_of_wire_per_turn_formula_c34` | **PASS** | TC-F12 |
| `test_top_plate_id_formula_c40` | **PASS** | TC-F13 |
| `test_pole_od_formula_c47` | **PASS** | TC-F14 |
| `test_pole_height_formula_c59` | **PASS** | TC-F15 |
| `test_vc_location_diameter_formula_c60` | **PASS** | TC-F16 |
| `test_mechanical_xmax_formula_c61` | **PASS** | TC-F17 |
| `test_bl_formula_c65` | **PASS** | TC-F18 |
| `test_bl_at_threshold_formula_c68` | **PASS** | TC-F19 |
| `test_splref_formula_c79` | **PASS** | TC-F20 |
| `test_qes_formula_c80` | **PASS** | TC-F21 |
| `test_qts_formula_c81` | **PASS** | TC-F22 |
| `test_mms_total_formula_c82` | **PASS** | TC-F23 |
| `test_fs_formula_c83` | **PASS** | TC-F24 |
| `test_target_sens_formula_c84` | **PASS** | TC-F25 |
| `test_non_coil_total_formula_m8` | **PASS** | TC-F26 |
| `test_diaphragm_mass_calc_formula_p8` | **PASS** | TC-F27 |
| `test_diaphragm_area_formula_p7` | **PASS** | TC-F28 |
| `test_wire_properties_copper` | **PASS** | TC-19 |
| `test_wire_properties_cca` | **PASS** | TC-19b |
| `test_former_densities` | **PASS** | TC-20 |
| `test_recalculate_derived` | **PASS** | TC-15 |

### 3.4 `tests/test_integration_smoke.py` — 5 tests

| Test Case | Status | TC ID |
|-----------|--------|-------|
| `test_gmsh_importable_when_build_geometry_called` | **PASS** | TC-I01 |
| `test_pyelmer_and_meshio_importable_for_solve` | **PASS** | TC-I02 |
| `test_real_build_geometry_creates_mesh_file` | **PASS** | TC-I03 |
| `test_real_elmer_solver_executable_found` | **PASS** | TC-I04 |
| `test_build_geometry_coil_air_bounds` | **PASS** | — |
| `test_run_elmer_simulation_integration_smoke` | **PASS** | TC-I05 |

### 3.5 `tests/test_models.py` — 6 tests

| Test Case | Status | TC ID |
|-----------|--------|-------|
| `test_loudspeaker_design_dataclass_exists` | **PASS** | TC-M01 |
| `test_mesh_size_factor_default` | **PASS** | **TC-M06** *(new for v0.1.7)* |
| `test_default_values_match_design1` | **PASS** | TC-M02 |
| `test_all_visible_fields_present` | **PASS** | TC-M03 |
| `test_hidden_fields_present_for_backward_compatibility` | **PASS** | TC-M04 |
| `test_json_serialization_roundtrip` | **PASS** | TC-M05 |

### 3.6 `tests/test_persistence.py` — 8 tests

| Test Case | Status | TC ID |
|-----------|--------|-------|
| `test_init_database_creates_file` | **PASS** | TC-23 |
| `test_init_database_creates_designs_table` | **PASS** | TC-P02 |
| `test_init_database_creates_settings_table` | **PASS** | TC-P03 |
| `test_save_design_persists_json` | **PASS** | TC-P04 |
| `test_load_design_retrieves_all_fields` | **PASS** | TC-P05 |
| `test_delete_design_removes_record` | **PASS** | TC-P06 |
| `test_settings_persist_elmer_path` | **PASS** | TC-P07 |
| `test_settings_persist_working_directory` | **PASS** | TC-P08 |

---

## 4. API Verification

All 28 symbols exported in `src.api.__all__` were verified as importable and callable:

- `LoudspeakerDesign`
- `create_design`, `get_default_values`, `save_design`, `load_design`, `list_designs`, `delete_design`, `clone_design`, `switch_active_design`
- `update_design_parameter`, `recalculate_derived`, `get_wire_properties`, `get_former_density`
- `run_elmer_simulation`, `run_elmer_solver`, `find_elmer_executable`, `parse_elmer_output`, `generate_density_plot`, `generate_elmer_input_files`
- `export_blx_csv`, `export_side_leakage_csv`, `export_results_json`
- `compare_designs`
- `init_database`, `set_elmer_executable_path`, `set_working_directory`, `get_setting`, `set_setting`

No `AttributeError` or missing-function exceptions occurred during test execution.

---

## 5. Quality Gate Assessment

| Gate | Criterion | Result | Evidence |
|------|-----------|--------|----------|
| **G6.1** | All test cases in the test plan have a corresponding passing pytest assertion. Zero test failures. Zero collection errors. | **PASS** | 84/84 passed; 0 failed; 0 collection errors. New TC-M06 asserts `mesh_size_factor == 0.24`. |
| **G6.2** | All API functions called in the tests exist and behave as defined in the API Function List. No AttributeError or missing function exceptions during test execution. | **PASS** | All 28 API exports verified importable and callable. Test suite executed with zero attribute errors. |

---

## 6. Bug-Fix Specific Verification

| Check | Result |
|-------|--------|
| `src/models.py` line 50: `mesh_size_factor: float = 0.24` | **Confirmed** |
| `src/main_window.py` version string updated to `0.1.7` | **Confirmed** |
| `docs/api_reference.md` version string updated to `0.1.7` | **Confirmed** |
| New regression test `test_mesh_size_factor_default` added to `tests/test_models.py` | **Confirmed** |
| No new slow integration tests added for this one-line default change | **Confirmed** |

---

## 7. Conclusion

**GO** — All quality gates pass. The v0.1.7 bug fix (mesh size factor default reduced from 1.0 to 0.24) is correctly implemented, covered by a new regression test, and does not break any existing functionality.

---

*End of QA Results*
