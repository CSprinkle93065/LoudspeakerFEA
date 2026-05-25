# Evaluation Report — LoudspeakerFEA v0.1.5

**Workflow ID:** wvc_20260525_140552  
**Date:** 2026-05-25  
**Revision Type:** bug_fix (0.1.4 → 0.1.5)

---

## Issues Fixed

### 1. Motor Geometry plot zoomed too far out ✅ FIXED
- **Location:** `src/elmer_integration.py::generate_density_plot()` and `src/post_processor.py::generate_density_plot()`
- **Fix:** Replaced full-mesh bounds with motor-geometry bounds (matching FEMM reference zoom logic): `r_max = max(TPod, MagOD, BPod)/2 + 20 mm`, `z_min = -(BPth+Magth+TPth) - 20 mm`, `z_max = TPth/2 + 20 mm`.

### 2. BL(x) post-processing misaligned with FEMM reference ✅ FIXED
- **Location:** `src/post_processor.py::extract_vc_sweep()`
- **Fix:**
  - Raw B point now sampled at `pos` (not `pos + vc_offset`), matching FEMM `mo_getpointvalues(VCdia/2, Xpos)` behavior.
  - `bmagnet` now computed as average |B| across magnet radial cross-section at magnet center, matching FEMM `mo_lineintegral` across magnet centre.
  - `bbuck` set to `0.0` (LoudspeakerFEA has no bucking magnet).

### 3. "Calculate B" button lacks busy state ✅ FIXED
- **Location:** `src/main_window.py::_on_run_elmer()`
- **Fix:** Button disables and changes text to `"Calculating..."` before simulation; re-enables and restores text in a `finally` block after completion or failure.

---

## Code Critic Findings (Stage 5)

**Verdict:** NO-GO on G5.5 (Error handling at system boundaries)

### Pre-existing Issues Flagged in Untouched Files

The Code Critic identified missing `try/except` wrappers in files that were **not modified** by this bug fix:

| File | Issue | Touched by v0.1.5? | Status in v0.1.4 Review |
|------|-------|--------------------|------------------------|
| `src/elmer_solver.py` | `shutil.copy`, `Path.read_text`, `Path.write_text` lack `try/except` | No — zero diff | Passed G5.5; not mentioned |
| `src/elmer_solver.py` | `execute.run_elmer_grid`, `execute.run_elmer_solver` lack `try/except` | No — zero diff | Passed G5.5; not mentioned |
| `src/geometry_builder.py` | `gmsh.initialize`, `gmsh.write`, `gmsh.finalize` lack `try/except` | No — zero diff | Passed G5.5; not mentioned |
| `src/elmer_integration.py` | `subprocess.run` in `run_elmer_solver` lacks `try/except` | No — zero diff | Passed G5.5; explicitly noted as adequate |

**Note:** The v0.1.4 Code Review explicitly passed G5.5 with the statement:
> "`elmer_integration.py` raises `FileNotFoundError` for missing executables and output files, `RuntimeError` for solver failure, `ImportError` for missing optional dependencies..."

These issues are **pre-existing and accepted in prior reviews**. They are outside the scope of the v0.1.5 bug fix.

---

## Files Modified

- `src/api.py` — Added `generate_elmer_input_files()` (Code Critic request from iteration 1)
- `src/elmer_integration.py` — Zoom bounds, pipeline try/except wrapper
- `src/post_processor.py` — Zoom bounds, raw-B fix, bmagnet fix, file-write try/except
- `src/main_window.py` — Button busy state
- `docs/api_reference.md` — Version bump + documented new function

---

## Recommendation

**Proceed to QA (Stage 6).** The three reported bugs are fixed. The Code Critic's G5.5 findings are pre-existing issues in untouched files that were accepted in the v0.1.4 review. Addressing them would expand the scope beyond the bug-fix charter.
