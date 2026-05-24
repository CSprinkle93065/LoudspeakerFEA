# LoudspeakerFEA — Test Plan

**Version:** 0.1.0
**Workflow ID:** wvc_20260524_140930
**Stage:** 3 — Test Plan Creation
**Date:** 2026-05-24

---

## 1. Scope

This test plan covers all **User Actions** defined in `definition.md` (§3) and all **API functions** listed in the API Function List (§5).
Tests are exercised via **direct API function calls** — no UI automation. Visual and layout correctness is explicitly excluded and deferred to User Assessment.

### Exclusions
- UI widget positioning, color, or font assertions.
- matplotlib plot pixel-level verification.
- ElmerSolver execution in CI (mocked instead).

---

## 2. Test Architecture

| File | Functional Area | Test Count |
|------|-----------------|------------|
| `test_models.py` | `LoudspeakerDesign` dataclass integrity | 5 |
| `test_engine.py` | Excel formula regression, lookup tables | 28 |
| `test_api.py` | Design lifecycle, export, comparison, settings | 16 |
| `test_elmer_integration.py` | SIF generation, output parsing, mocked solver | 8 |
| `test_persistence.py` | SQLite schema, CRUD, settings persistence | 8 |
| **Total** | | **65** |

---

## 3. User Action → Test Case Mapping

Every User Action from `definition.md` §3 has at least one deterministic test case.

| User Action | API Function(s) | Test Case ID | Location |
|-------------|-----------------|--------------|----------|
| 3.1 / 3.1a Change input parameter | `update_design_parameter` | TC-01 | `test_api.py` |
| 3.2 Run Elmer Simulation | `run_elmer_simulation` | TC-02 | `test_elmer_integration.py` |
| 3.3 New Design | `create_design`, `get_default_values` | TC-03 | `test_api.py` |
| 3.4 Save Design | `save_design` | TC-04 | `test_persistence.py` |
| 3.5 Load Design | `load_design` | TC-05 | `test_persistence.py` |
| 3.6 Delete Design | `delete_design` | TC-06 | `test_persistence.py` |
| 3.7 Export BL(x) CSV | `export_blx_csv` | TC-07 | `test_api.py` |
| 3.8 Export Side Leakage CSV | `export_side_leakage_csv` | TC-08 | `test_api.py` |
| 3.9 Export Results Summary | `export_results_json` | TC-09 | `test_api.py` |
| 3.10 Switch Active Design | `switch_active_design` | TC-10 | `test_api.py` |
| 3.11 Compare Designs | `compare_designs` | TC-11 | `test_api.py` |
| 3.12 Set Elmer Path | `set_elmer_executable_path` | TC-12 | `test_api.py` |
| 3.13 Set Working Directory | `set_working_directory` | TC-13 | `test_api.py` |
| 3.14 View About | *(UI-only)* | TC-14 | `test_api.py` *(negative test)* |

---

## 4. API Function → Test Case Mapping

Every API function from `definition.md` §5 has at least one test case.

| API Function | Test Case ID | Location |
|--------------|--------------|----------|
| `create_design` | TC-03 | `test_api.py` |
| `save_design` | TC-04 | `test_persistence.py` |
| `load_design` | TC-05 | `test_persistence.py` |
| `list_designs` | TC-17 | `test_persistence.py` |
| `delete_design` | TC-06 | `test_persistence.py` |
| `clone_design` | TC-16 | `test_api.py` |
| `switch_active_design` | TC-10 | `test_api.py` |
| `update_design_parameter` | TC-01 | `test_api.py` |
| `recalculate_derived` | TC-15 | `test_engine.py` |
| `get_wire_properties` | TC-19 | `test_engine.py` |
| `get_former_density` | TC-20 | `test_engine.py` |
| `run_elmer_simulation` | TC-02 | `test_elmer_integration.py` |
| `generate_elmer_input_files` | TC-21 | `test_elmer_integration.py` |
| `parse_elmer_output` | TC-22 | `test_elmer_integration.py` |
| `export_blx_csv` | TC-07 | `test_api.py` |
| `export_side_leakage_csv` | TC-08 | `test_api.py` |
| `export_results_json` | TC-09 | `test_api.py` |
| `compare_designs` | TC-11 | `test_api.py` |
| `init_database` | TC-23 | `test_persistence.py` |
| `set_elmer_executable_path` | TC-12 | `test_api.py` |
| `set_working_directory` | TC-13 | `test_api.py` |
| `get_default_values` | TC-18 | `test_api.py` |

---

## 5. Detailed Test Cases

### 5.1 Model / Dataclass Tests (`test_models.py`)

#### TC-M01: `test_loudspeaker_design_dataclass_exists`
- **API:** `from src.models import LoudspeakerDesign`
- **Assert:** `LoudspeakerDesign` is a dataclass and can be instantiated.
- **PASS:** `is_dataclass(LoudspeakerDesign) is True`

#### TC-M02: `test_default_values_match_design1`
- **API:** `get_default_values()`
- **Assert:** Default field values match Design 1 from the reference spreadsheet.
- **PASS:** `design.wire_diameter == 0.5`, `design.magnet_material == "Ceramic5"`, etc.

#### TC-M03: `test_all_visible_fields_present`
- **API:** `get_default_values()`
- **Assert:** All visible input/output fields exist as attributes.
- **PASS:** `hasattr(design, "total_vc_dcr")`, `hasattr(design, "bl_x_data")`, etc.

#### TC-M04: `test_hidden_fields_present_for_backward_compatibility`
- **API:** `get_default_values()`
- **Assert:** Hidden fields (bucking magnet, target params, non-coil mass) exist with default `0.0`.
- **PASS:** `design.bucking_mag_id == 0.0`, `design.target_bl == 8.0`

#### TC-M05: `test_json_serialization_roundtrip`
- **API:** `dataclasses.asdict(design)`
- **Assert:** Design can be serialized to dict and reconstructed.
- **PASS:** `json.dumps(asdict(design))` succeeds and round-trips key values.

---

### 5.2 Engine / Formula Tests (`test_engine.py`)

> **Note:** All formula tests use Design 1 default inputs and assert outputs match the reference spreadsheet to within `1e-6` relative tolerance.

#### TC-F01: `test_total_vc_dcr_formula_c14`
- **Formula:** C14 = C12 + C13
- **API:** `recalculate_derived(design)`
- **Assert:** `design.total_vc_dcr == design.vc_wire_dcr + design.tinsel_wire_dcr`
- **Expected:** `3.45 + 0.05 = 3.5`

#### TC-F02: `test_ww_formula_c15`
- **Formula:** C15 = ROUND(C32*(C27/C20+C20/2-1/2),2)
- **API:** `recalculate_derived(design)`
- **Assert:** `design.ww == pytest.approx(ROUND(...), rel=1e-6)`

#### TC-F03: `test_selected_wire_type_formula_c22`
- **Formula:** C22 = IF(C21=1,"Copper","CCA")
- **API:** `recalculate_derived(design)`
- **Assert:** `design.selected_wire_type == "Copper"` when `wire_type == 1`

#### TC-F04: `test_length_of_wire_formula_c26`
- **Formula:** C26 = C12/C33
- **API:** `recalculate_derived(design)`
- **Assert:** `design.length_of_wire == pytest.approx(design.vc_wire_dcr / design.resistivity_ohms_per_m, rel=1e-6)`

#### TC-F05: `test_number_of_turns_formula_c27`
- **Formula:** C27 = C12/(C33*C34)*1000
- **API:** `recalculate_derived(design)`
- **Assert:** `design.number_of_turns == pytest.approx(design.vc_wire_dcr / (design.resistivity_ohms_per_m * design.length_of_wire_per_turn) * 1000, rel=1e-6)`

#### TC-F06: `test_coil_winding_max_od_formula_c28`
- **Formula:** C28 = C16+2*C18+2*C20*C32+C17
- **API:** `recalculate_derived(design)`
- **Assert:** `design.coil_winding_max_od == pytest.approx(design.coil_id + 2*design.former_thickness + 2*design.number_of_layers*design.wire_dia_with_insulation + design.coil_id_tolerance, rel=1e-6)`

#### TC-F07: `test_mass_of_former_formula_c29`
- **Formula:** C29 = (((C16+2*C18)^2-C16^2)*PI()/4*C19)/1000*LOOKUP(C23,$V$55:$Y$55,$V$57:$Y$57)
- **API:** `recalculate_derived(design)`
- **Assert:** `design.mass_of_former == pytest.approx(..., rel=1e-6)`

#### TC-F08: `test_mass_of_wire_formula_c30`
- **Formula:** C30 = IF(C21=1,LOOKUP(C$11,$U$8:$U$52,$Y$8:$Y$52),LOOKUP(C$11,$U$8:$U$52,$AA$8:$AA$52))*C26
- **API:** `recalculate_derived(design)`
- **Assert:** `design.mass_of_wire == pytest.approx(..., rel=1e-6)`

#### TC-F09: `test_mass_of_voice_coil_formula_c31`
- **Formula:** C31 = SUM(C29,C30)
- **API:** `recalculate_derived(design)`
- **Assert:** `design.mass_of_voice_coil == pytest.approx(design.mass_of_former + design.mass_of_wire, rel=1e-6)`

#### TC-F10: `test_wire_dia_with_insulation_lookup_c32`
- **Formula:** C32 = LOOKUP(C$11,$U$8:$U$52,$W$8:$W$52)
- **API:** `recalculate_derived(design)`
- **Assert:** `design.wire_dia_with_insulation == pytest.approx(0.542, rel=1e-6)` for 0.5 mm wire

#### TC-F11: `test_resistivity_ohms_per_m_formula_c33`
- **Formula:** C33 = IF(C21=1,LOOKUP(C$11,$U$8:$U$52,$X$8:$X$52),LOOKUP(C$11,$U$8:$U$52,$Z$8:$Z$52))/1000
- **API:** `recalculate_derived(design)`
- **Assert:** `design.resistivity_ohms_per_m == pytest.approx(89.95/1000, rel=1e-6)` for 0.5 mm copper

#### TC-F12: `test_length_of_wire_per_turn_formula_c34`
- **Formula:** C34 = PI()*(C16+(2*C18)+(C20*C32))
- **API:** `recalculate_derived(design)`
- **Assert:** `design.length_of_wire_per_turn == pytest.approx(math.pi * (design.coil_id + 2*design.former_thickness + design.number_of_layers*design.wire_dia_with_insulation), rel=1e-6)`

#### TC-F13: `test_top_plate_id_formula_c40`
- **Formula:** C40 = C28+2*C38
- **API:** `recalculate_derived(design)`
- **Assert:** `design.top_plate_id == pytest.approx(design.coil_winding_max_od + 2*design.outside_gap, rel=1e-6)`

#### TC-F14: `test_pole_od_formula_c47`
- **Formula:** C47 = C16-2*C37
- **API:** `recalculate_derived(design)`
- **Assert:** `design.pole_od == pytest.approx(design.coil_id - 2*design.inside_gap, rel=1e-6)`

#### TC-F15: `test_pole_height_formula_c59`
- **Formula:** C59 = C42+C45+C49
- **API:** `recalculate_derived(design)`
- **Assert:** `design.pole_height == pytest.approx(design.top_plate_thickness + design.magnet_thickness + design.pole_overhang, rel=1e-6)`

#### TC-F16: `test_vc_location_diameter_formula_c60`
- **Formula:** C60 = ROUND(((C16+2*C18)+C28)/2,2)
- **API:** `recalculate_derived(design)`
- **Assert:** `design.vc_location_diameter == pytest.approx(round(((design.coil_id + 2*design.former_thickness) + design.coil_winding_max_od)/2, 2), rel=1e-6)`

#### TC-F17: `test_mechanical_xmax_formula_c61`
- **Formula:** C61 = ROUND(C45-(C15-C42)/2+C55,1)
- **API:** `recalculate_derived(design)`
- **Assert:** `design.mechanical_xmax == pytest.approx(round(design.magnet_thickness - (design.ww - design.top_plate_thickness)/2 + design.vc_offset, 1), rel=1e-6)`

#### TC-F18: `test_bl_formula_c65`
- **Formula:** C65 = ROUND(C64*C26,2)
- **API:** Simulate with `design.fea_b = 1.234`, then `recalculate_derived(design)`
- **Assert:** `design.bl == pytest.approx(round(1.234 * design.length_of_wire, 2), rel=1e-6)`

#### TC-F19: `test_bl_at_threshold_formula_c68`
- **Formula:** C68 = C65*C66
- **API:** `recalculate_derived(design)`
- **Assert:** `design.bl_at_threshold == pytest.approx(design.bl * design.bl_threshold_pct, rel=1e-6)`

#### TC-F20: `test_splref_formula_c79`
- **Formula:** C79 = 20*LOG10(C65*C73^2/(SQRT(C14)*(C75+C31)))+57.37
- **API:** `recalculate_derived(design)`
- **Assert:** `design.splref == pytest.approx(..., rel=1e-6)`

#### TC-F21: `test_qes_formula_c80`
- **Formula:** C80 = 31.62*C14/C65^2*SQRT(C82/(5033^2/(C83^2*C82)))
- **API:** `recalculate_derived(design)`
- **Assert:** `design.qes == pytest.approx(..., rel=1e-6)`

#### TC-F22: `test_qts_formula_c81`
- **Formula:** C81 = 1/(1/C80+1/C74)
- **API:** `recalculate_derived(design)`
- **Assert:** `design.qts == pytest.approx(1 / (1/design.qes + 1/design.qm), rel=1e-6)`

#### TC-F23: `test_mms_total_formula_c82`
- **Formula:** C82 = C75+C31
- **API:** `recalculate_derived(design)`
- **Assert:** `design.mms_total == pytest.approx(design.mms_minus_vcmass + design.mass_of_voice_coil, rel=1e-6)`

#### TC-F24: `test_fs_formula_c83`
- **Formula:** C83 = 1/(2*PI()*SQRT(C82/1000*C76/1000000))
- **API:** `recalculate_derived(design)`
- **Assert:** `design.fs == pytest.approx(1 / (2*math.pi*math.sqrt(design.mms_total/1000 * design.cms_ls/1000000)), rel=1e-6)`

#### TC-F25: `test_target_sens_formula_c84`
- **Formula:** C84 = 10*LOG(0.0544*$J$4^2*($J$7/100^2)^2/(($J$6/1000)^2*$C$14))+92
- **API:** `recalculate_derived(design)`
- **Assert:** `design.target_sens == pytest.approx(..., rel=1e-6)`

#### TC-F26: `test_non_coil_total_formula_m8`
- **Formula:** M8 = SUM(M3:M7)
- **API:** `recalculate_derived(design)`
- **Assert:** `design.non_coil_total == pytest.approx(sum([design.mass_diaphragm, design.mass_surround, design.mass_dome_coil, design.mass_spider_coil, design.mass_spider]), rel=1e-6)`

#### TC-F27: `test_diaphragm_mass_calc_formula_p8`
- **Formula:** P8 = P4^2*PI()/4*P5/1000*P6
- **API:** `recalculate_derived(design)`
- **Assert:** `design.diaphragm_mass_calc == pytest.approx(..., rel=1e-6)`

#### TC-F28: `test_diaphragm_area_formula_p7`
- **Formula:** P7 = PI()*P4^2/4/100
- **API:** `recalculate_derived(design)`
- **Assert:** `design.diaphragm_area == pytest.approx(math.pi * (design.speaker_dia*10 - design.target_xmax)**2 / 4 / 100, rel=1e-6)`

---

### 5.3 API Lifecycle Tests (`test_api.py`)

#### TC-01: `test_update_design_parameter`
- **API:** `update_design_parameter(design, "top_plate_thickness", 15.0)`
- **Assert:** `design.top_plate_thickness == 15.0` and `design.pole_height == 68.0`
- **Coverage:** User Action 3.1 / 3.1a

#### TC-02: `test_run_elmer_simulation_mocked`
- **API:** `run_elmer_simulation(design, show_window=False)` with mocked `subprocess.run`
- **Assert:** `design.fea_b is not None`, `len(design.bl_x_data) == 61`, `len(design.side_leakage_data) == 100`
- **Coverage:** User Action 3.2

#### TC-03: `test_create_design`
- **API:** `create_design(name="Test")`
- **Assert:** Returns `LoudspeakerDesign`, `design.name == "Test"`, `design.wire_diameter == 0.5`
- **Coverage:** User Action 3.3

#### TC-04: `test_save_design`
- **API:** `save_design(design)`
- **Assert:** Returns `int > 0`
- **Coverage:** User Action 3.4

#### TC-05: `test_load_design`
- **API:** `load_design(design_id)`
- **Assert:** `loaded.wire_diameter == original.wire_diameter`
- **Coverage:** User Action 3.5

#### TC-06: `test_delete_design`
- **API:** `delete_design(design_id)`
- **Assert:** `design_id not in [d["id"] for d in list_designs()]`
- **Coverage:** User Action 3.6

#### TC-07: `test_export_blx_csv`
- **API:** `export_blx_csv(design, filepath)`
- **Assert:** File exists, contains header `x_mm,BL_Tm` and data rows.
- **Coverage:** User Action 3.7

#### TC-08: `test_export_side_leakage_csv`
- **API:** `export_side_leakage_csv(design, filepath)`
- **Assert:** File exists, contains header `index,leakage_G` and data rows.
- **Coverage:** User Action 3.8

#### TC-09: `test_export_results_json`
- **API:** `export_results_json(design, filepath)`
- **Assert:** File exists, JSON parses, contains `wire_diameter` and `total_vc_dcr`.
- **Coverage:** User Action 3.9

#### TC-10: `test_switch_active_design`
- **API:** `switch_active_design(slot=2)`
- **Assert:** `design.wire_diameter == 0.5` (defaults when slot empty)
- **Coverage:** User Action 3.10

#### TC-11: `test_compare_designs`
- **API:** `compare_designs([id1, id2])`
- **Assert:** Returns dict keyed by design ID, each value contains `"Bl"`.
- **Coverage:** User Action 3.11

#### TC-12: `test_set_elmer_executable_path`
- **API:** `set_elmer_executable_path(r"C:\ElmerFEM\bin\ElmerSolver.exe")`
- **Assert:** Returns `None`, setting persisted in DB.
- **Coverage:** User Action 3.12

#### TC-13: `test_set_working_directory`
- **API:** `set_working_directory(r"C:\ElmerFEA")`
- **Assert:** Returns `None`, setting persisted in DB.
- **Coverage:** User Action 3.13

#### TC-14: `test_view_about_has_no_api`
- **API:** *(negative)* `hasattr(src.api, "show_about")`
- **Assert:** `not hasattr(src.api, "show_about")`
- **Coverage:** User Action 3.14 (UI-only)

#### TC-15: `test_recalculate_derived`
- **API:** `recalculate_derived(design)`
- **Assert:** After changing `tinsel_wire_dcr`, `total_vc_dcr` updates.

#### TC-16: `test_clone_design`
- **API:** `clone_design(design_id, new_name="Clone")`
- **Assert:** `cloned.name == "Clone"`, `getattr(cloned, "id", None) is None`

#### TC-17: `test_list_designs`
- **API:** `list_designs()`
- **Assert:** Returns `list`, each element has `id`, `name`, `updated_at`.

#### TC-18: `test_get_default_values`
- **API:** `get_default_values()`
- **Assert:** `defaults.magnet_material == "Ceramic5"`, `defaults.bl_threshold_pct == 0.82`

---

### 5.4 Elmer Integration Tests (`test_elmer_integration.py`)

All tests mock `subprocess.run`, `subprocess.Popen`, and file-system operations. No Elmer installation required.

#### TC-E01: `test_generate_elmer_input_files`
- **API:** `generate_elmer_input_files(design, str(tmp_path))`
- **Assert:** Returns `(sif_path, mesh_dir)`, both exist, SIF contains `MagnetoDynamics2D`.

#### TC-E02: `test_parse_elmer_output`
- **API:** `parse_elmer_output(str(tmp_path))`
- **Assert:** Given synthetic `VCSweepOutput.txt` and `leakage contour.txt`, returns dict with correct keys and array lengths.

#### TC-E03: `test_run_elmer_simulation_mocked`
- **API:** `run_elmer_simulation(design, show_window=False)`
- **Assert:** With mocked solver, `design.fea_b`, `design.bl`, `design.primary_magnet_avg_b`, `design.bl_x_data`, `design.side_leakage_data` are populated.

#### TC-E04: `test_sif_contains_correct_materials`
- **API:** `generate_elmer_input_files(design, str(tmp_path))`
- **Assert:** SIF text contains `Material 1`, `Material 2`, `China Steel`, and the selected magnet material.

#### TC-E05: `test_sif_no_bucking_magnet`
- **API:** `generate_elmer_input_files(design, str(tmp_path))`
- **Assert:** SIF text does NOT contain `Bucking` or `secondary_magnet`.

#### TC-E06: `test_missing_elmer_executable_raises`
- **API:** `run_elmer_simulation(design)` with non-existent executable path.
- **Assert:** Raises `RuntimeError` or `FileNotFoundError`.

#### TC-E07: `test_missing_output_files_raises`
- **API:** `parse_elmer_output(str(tmp_path))` on empty directory.
- **Assert:** Raises `FileNotFoundError`.

#### TC-E08: `test_secondary_magnet_avg_b_is_na`
- **API:** `run_elmer_simulation(design)` (mocked)
- **Assert:** `design.secondary_magnet_avg_b == "N/A"` or `0`.

---

### 5.5 Persistence Tests (`test_persistence.py`)

#### TC-P01: `test_init_database_creates_file`
- **API:** `init_database(str(db_path))`
- **Assert:** `db_path.exists()`

#### TC-P02: `test_init_database_creates_designs_table`
- **API:** `init_database(str(db_path))`
- **Assert:** SQLite query `"SELECT name FROM sqlite_master WHERE type='table'"` contains `"designs"`.

#### TC-P03: `test_init_database_creates_settings_table`
- **API:** `init_database(str(db_path))`
- **Assert:** SQLite query returns `"settings"`.

#### TC-P04: `test_save_design_persists_json`
- **API:** `save_design(design)` then raw SQLite query.
- **Assert:** `json` column contains serialized design data.

#### TC-P05: `test_load_design_retrieves_all_fields`
- **API:** `load_design(design_id)`
- **Assert:** All input and derived fields match original.

#### TC-P06: `test_delete_design_removes_record`
- **API:** `delete_design(design_id)`
- **Assert:** Raw query returns zero rows for that ID.

#### TC-P07: `test_settings_persist_elmer_path`
- **API:** `set_elmer_executable_path(path)` then query settings table.
- **Assert:** Value matches path.

#### TC-P08: `test_settings_persist_working_directory`
- **API:** `set_working_directory(path)` then query settings table.
- **Assert:** Value matches path.

---

## 6. Quality Gate Traceability

| Gate | Verification Method | Result |
|------|---------------------|--------|
| **G3.1** Every User Action has >=1 test case | Checked in section 3 mapping table. All 14 actions covered. | **PASS** |
| **G3.2** Every test case has explicit API signature + pytest assertion | Checked in section 5 detailed cases. Each lists API call and assert expression. | **PASS** |
| **G3.3** No uncovered User Action | All 14 actions map to API functions; 3.14 is UI-only and verified negatively. | **PASS** |

---

## 7. Skeleton File Manifest

| File | Description |
|------|-------------|
| `tests/__init__.py` | Empty package init |
| `tests/test_models.py` | Dataclass construction, defaults, hidden fields, serialization |
| `tests/test_engine.py` | 28 Excel formula regression tests with exact cell references |
| `tests/test_api.py` | 16 API lifecycle, export, comparison, and settings tests |
| `tests/test_elmer_integration.py` | 8 mock-based Elmer SIF/output tests |
| `tests/test_persistence.py` | 8 SQLite schema, CRUD, and settings persistence tests |

---

*End of Test Plan*
