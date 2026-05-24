# LoudspeakerFEA — Stage 2 Definition Assessment

**Workflow ID:** wvc_20260524_140930  
**Project:** LoudspeakerFEA v0.1.0  
**Reviewer:** Definition Critic Agent  
**Date:** 2026-05-24

---

## Verdict: **GO**

The definition document is complete, testable, and ready for Stage 3 (Architecture Design). All required sections are present with sufficient detail to write code and automated tests without further clarification.

---

## Gate Results

### G2.1 — Required Sections Present and Sufficient
**PASS**

All 6 required sections are present and contain detail sufficient for deterministic implementation:

| Section | Status | Notes |
|---------|--------|-------|
| 1. Application Overview | ✓ | Purpose, user, platform, and 12 explicit inferences documented. Elmer axisymmetric magnetostatics inference is critical and present. |
| 2. UI Layout | ✓ | Menu bar (File/Setup/Help), left panel groups (A, B, C), hidden groups (F, G, H, I, J), right panel tabs (BL(x), Side Leakage, FEA Geometry, Sensitivity Analysis), and design selector all specified. |
| 3. User Actions | ✓ | 14 actions with triggers mapped. Action 3.14 (View About) correctly flagged as UI-only. |
| 4. Data Model | ✓ | `LoudspeakerDesign` dataclass with 42+ input fields, 25+ derived fields, 4 arrays, 3 reference lookup tables, and Elmer output file specifications. |
| 5. API Function List | ✓ | 22 functions with full parameter signatures and return types, organized by lifecycle, calculation, simulation, export, comparison, and utility. |
| 6. Toolchain | ✓ | Python 3.11+, PyQt6, matplotlib, SQLite, ElmerFEM, pytest, PyInstaller. Elmer integration method (SIF + subprocess) specified. Testing strategy includes unit, mock, and formula-regression tests. |

---

### G2.2 — Every User Action Has API Coverage
**PASS**

All 14 User Actions are covered by the API Function List:

| User Action | API Function |
|-------------|--------------|
| 3.1 Change any input parameter | `update_design_parameter` (3.1a is the explicit API entry) |
| 3.2 Run Elmer Simulation | `run_elmer_simulation` |
| 3.3 New Design | `create_design` / `get_default_values` |
| 3.4 Save Design | `save_design` |
| 3.5 Load Design | `load_design` |
| 3.6 Delete Design | `delete_design` |
| 3.7 Export BL(x) CSV | `export_blx_csv` |
| 3.8 Export Side Leakage CSV | `export_side_leakage_csv` |
| 3.9 Export Results Summary | `export_results_json` |
| 3.10 Switch Active Design | `switch_active_design` |
| 3.11 Compare Designs | `compare_designs` |
| 3.12 Set Elmer Path | `set_elmer_executable_path` |
| 3.13 Set Working Directory | `set_working_directory` |
| 3.14 View About | UI-only (explicitly noted, no API required) |

---

### G2.3 — API Functions Have Deterministic pytest Signatures
**PASS**

All 22 API functions include name, typed parameters, and return types sufficient for deterministic pytest assertions:

- Return types are explicit (`LoudspeakerDesign`, `int`, `None`, `list[dict]`, `dict`, `tuple[str, str]`, `float`).
- `list_designs()` return dict keys are documented (`id`, `name`, `updated_at`).
- `get_wire_properties()` return dict keys are documented (`max_od_with_insulation`, `resistance_ohm_per_km`, `mass_kg_per_km`).
- `parse_elmer_output()` return dict keys are documented (`b_at_zero`, `data_points`, `bmagnet`, `vc_sweep`, `side_leakage`).
- `compare_designs()` comparison metrics are enumerated (Bl, Xmax, SPLref, Qts, Fs, etc.).

---

## Special Attention Findings

### 1. Formula Transcription Fidelity
**PASS**

All mathematical formulas for derived fields are present with exact cell references. Cross-checked against MotorModel `definition.md` Appendix A:

- **A.1 Voice Coil (10 formulas)**: C14, C15, C22, C24, C26, C27, C28, C29, C30, C31, C32, C33, C34 — all match MotorModel reference exactly.
- **A.2 Motor Geometry (5 formulas)**: C40, C47, C59, C60, C61 — all match reference exactly.
- **A.3 FEA-Derived Outputs (4 formulas)**: C65, C67, C68, C69 — all match reference exactly (C64 renamed to `fea_b` for Elmer).
- **A.4 Loudspeaker Parameters (6 formulas)**: C73, C75, C76, C79, C80, C81, C82, C83, C84 — all match reference exactly.
- **A.5 Xmax Interpolation (3 formulas)**: C86, C87, C88 — all match reference exactly.
- **A.6 Non-Coil Mass (4 formulas)**: M3, M8, P4, P7, P8 — all match reference exactly.

All overridable inputs with formula defaults are correctly classified as inputs (not derived outputs): `overhang` (C24), `top_plate_id` (C40), `pole_od` (C47), `speaker_dia` (C73), `mms_minus_vcmass` (C75), `cms_ls` (C76).

No formula omissions detected.

### 2. Elmer Adaptation Completeness
**PASS**

The FEMM→Elmer switch is fully specified across all required dimensions:

| Aspect | Specification Location | Detail |
|--------|----------------------|--------|
| Setup menu controls | §2.1 | Elmer executable path, working directory, mesh size factor, show processor `[0,1]` |
| Solver integration | §6.1, Appendix B | SIF generation, `subprocess.Popen`, `MagnetoDynamics2D`, mesh generation, VTU/EP parsing |
| Output file formats | §4.4 | `spkr.sif`, `mesh/`, `VCSweepOutput.txt`, `leakage contour.txt`, `B-Field.png` |
| B-field plot scale | §2.4, §6.1, Appendix B.3 | Fixed 0–2 T, `vmin=0`, `vmax=2`, `ScalarFormatter(useMathText=False)` for decimal notation |

Appendix B provides geometry-to-Elmer mapping, SIF structure outline, and post-processing extraction steps. No gaps identified.

### 3. Bucking Magnet Removal
**PASS**

Bucking magnet inputs are explicitly removed from the UI and noted in the data model:

- **UI Section 2.2 Group B**: No `Bucking mag ID`, `Bucking mag OD`, or `Bucking mag thickness` inputs present.
- **Data Model §4.2**: `bucking_mag_id`, `bucking_mag_od`, `bucking_mag_thickness` listed with default `0.0`, marked **Hidden *(removed from UI)***.
- **Appendix B.1**: "No bucking magnet region — skip all bucking-magnet nodes and segments."
- **Inference 11**: "No bucking magnet support" documented.
- **API/FEA outputs**: `secondary_magnet_avg_b` always `"N/A"` or `0`.

### 4. No Formula Substitutions Prohibition
**PASS**

An explicit prohibition on algebraic substitutions is present in **Appendix A header**:

> **CRITICAL CONSTRAINT**: All formulas below must be implemented **exactly** as shown. No algebraic substitution, no simplification, no "correction" of apparent typos. Implement character-for-character and flag any concerns in a code comment.

This directly addresses the known issue "Coding Agent substitutes simplified formula variants" and is reinforced by the testing requirement (§6.3): "Unit tests for every Excel formula: given the Design 1 inputs, the Python calculation must match the spreadsheet outputs to within `1e-6` relative tolerance."

---

## Minor Observations (Non-Blocking)

1. **Symbolic names in Data Model vs. cell references in Appendix A**: The `interpolated_xmax` and `pct_bl_at_xmax` formulas in the Data Model table use symbolic names (`bl_at_xmax`, `x_first`, `x_last`, `first_bl_pct`, `last_bl_pct`) that are not explicitly defined as standalone fields. Appendix A uses the exact Excel cell references (C154, C91, C151, C214), which are unambiguous. Coding Agent should implement using Appendix A as the authoritative source.

2. **`bl_pct_array` computation**: The definition describes `bl_pct_array` as "BL/BLmax ratio at each x position" but does not explicitly state the per-element formula (`BL[i] / BL_max`). This is inferable from the description and the interpolation formula context; consistent with MotorModel reference.

3. **SQLite `settings` table**: The API functions `set_elmer_executable_path` and `set_working_directory` reference a SQLite `settings` table, but §4.1 only documents the `designs` table. The table structure is implicit from the API signatures; consistent with MotorModel reference.

---

## Conclusion

The LoudspeakerFEA definition document passes all Stage 2 quality gates. It is a complete, testable adaptation of the MotorModel reference with the FEMM→Elmer switch fully specified, bucking magnets correctly removed, and all formulas preserved exactly.

**Recommendation: Proceed to Stage 3 (Architecture Design).**
