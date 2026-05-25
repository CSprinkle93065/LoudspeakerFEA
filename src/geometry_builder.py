"""Gmsh geometry builder for axisymmetric loudspeaker motor.

Reproduces MotorModel's FEMM geometry using Gmsh's OpenCASCADE kernel.
All dimensions are in **millimetres** (same unit convention as FEMM).
"""

from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import List, Tuple

from src.models import LoudspeakerDesign
from src.engine import recalculate_derived

# ─── Helper: point-in-rectangle ───────────────────────────────────────────────


def _in_rect(x: float, y: float, x_min: float, y_min: float, x_max: float, y_max: float) -> bool:
    """True if (x, y) lies inside or on the closed rectangle."""
    return x_min <= x <= x_max and y_min <= y <= y_max


# ─── Main geometry builder ────────────────────────────────────────────────────


def build_geometry(design: LoudspeakerDesign, directory: str) -> Path:
    """Create a Gmsh model, generate a 2-D axisymmetric mesh, and save ``.msh``.

    Parameters
    ----------
    design:
        Loudspeaker design parameters.  Derived fields (*ww*, *pole_height*, …) are
        recomputed automatically if they are zero.
    directory:
        Output directory for the mesh file.  Created if it does not exist.

    Returns
    -------
    Path to the generated ``.msh`` file.
    """
    try:
        import gmsh
    except ImportError as exc:
        raise ImportError(
            "geometry_builder requires gmsh to be installed. "
            "Install it with: pip install gmsh"
        ) from exc

    # ── Ensure derived fields are populated ──
    design = recalculate_derived(design)

    # ── Short variable names (match original FEMM macro) ──
    tpid = design.top_plate_id
    tpod = design.top_plate_od
    tpth = design.top_plate_thickness
    magid = design.magnet_id
    magod = design.magnet_od
    magth = design.magnet_thickness
    ppod = design.pole_od
    ppvent = design.pole_vent_hole
    ppht = design.pole_height
    bpod = design.bp_od
    bpth = design.bp_thickness
    mesh_size_factor = design.mesh_size_factor
    leak = design.side_leakage_distance

    # ── Air-bubble parameters ──
    delta_y = -tpth / 2.0 - magth / 2.0
    rad_1 = 2.5 * magod / 2.0
    rad_2 = max(2.0 * leak, 5.0 * magod)

    # ── Mesh-size scaling from mesh_size_factor (FEMM convention → Gmsh char. length) ──
    # Target: ~5 000–20 000 triangles for the default design (mesh_size_factor = 0.24).
    # mesh_size_factor ranges 0.1 (very fine) → 1.0 (very coarse).
    accuracy = mesh_size_factor
    fine_size = max(0.3, 2.0 * accuracy)      # air gap / coil region
    medium_size = max(0.8, 5.0 * accuracy)    # magnet / steel nearby
    coarse_size = max(5.0, 50.0 * accuracy)   # far air

    # ── Initialise Gmsh ──
    gmsh.initialize()
    gmsh.model.add("loudspeaker_motor")
    occ = gmsh.model.occ

    # We keep the GUI quiet unless explicitly requested
    gmsh.option.setNumber("General.Terminal", 1)

    # ── Build motor parts as rectangles (r, z) ──
    # y = 0 is the top-plate mid-plane, same as FEMM

    # 1. Top plate
    top_plate = occ.addRectangle(tpid / 2.0, -tpth / 2.0, 0.0, (tpod - tpid) / 2.0, tpth)

    # 2. Magnet
    magnet = occ.addRectangle(magid / 2.0, -tpth / 2.0 - magth, 0.0, (magod - magid) / 2.0, magth)

    # 3. Back plate
    bp_y_bottom = -tpth / 2.0 - magth - bpth
    back_plate = occ.addRectangle(0.0, bp_y_bottom, 0.0, bpod / 2.0, bpth)

    # 4. Pole piece (full height, from bottom of BP to above top plate)
    pole_piece = occ.addRectangle(0.0, bp_y_bottom, 0.0, ppod / 2.0, ppht + bpth)

    # 5. Vent hole (cut out from pole-piece / back-plate union)
    vent = occ.addRectangle(0.0, bp_y_bottom, 0.0, ppvent / 2.0, ppht + bpth)

    # 6. Coil air (voice-coil winding window)
    #    The FEMM macro draws a polygon whose bottom is implicitly bounded by
    #    the pole piece and top plate.  We create a rectangle that overlaps
    #    those parts; fragment() will leave only the true air pocket.
    coil_r_min = ppod / 2.0 - tpth
    coil_r_max = tpid / 2.0 + tpth
    coil_y_bottom = -tpth / 2.0 - magth + ppht
    coil_y_top = -tpth / 2.0 - magth + 2.0 * ppht
    coil_air = occ.addRectangle(coil_r_min, coil_y_bottom, 0.0,
                                coil_r_max - coil_r_min, coil_y_top - coil_y_bottom)

    # ── Air domain (semicircle, r ≥ 0) ──
    # We build a full disk and intersect with a rectangle covering r ≥ 0.
    far_air_rect = occ.addRectangle(0.0, delta_y - rad_2, 0.0, rad_2, 2.0 * rad_2)
    far_air_disk = occ.addDisk(0.0, delta_y, 0.0, rad_2, rad_2)
    far_air, _ = occ.intersect([(2, far_air_rect)], [(2, far_air_disk)])

    # ── Collect all solid shapes for fragmentation ──
    all_shapes = [
        (2, top_plate),
        (2, magnet),
        (2, back_plate),
        (2, pole_piece),
        (2, vent),
        (2, coil_air),
    ]
    all_shapes.extend(far_air)

    # ── Fragment everything ──
    # After this call every overlapping region is split into non-overlapping
    # surfaces.  The returned *fragments* list contains the surviving surfaces.
    fragments, _ = occ.fragment(all_shapes, [])
    occ.synchronize()

    # ── Classify fragments by centroid ──
    def get_centroid(dim: int, tag: int) -> Tuple[float, float]:
        """Return (r, z) centroid of a 2-D entity."""
        cx, cy, _ = gmsh.model.occ.getCenterOfMass(dim, tag)
        return cx, cy

    groups = {
        "top_plate": [],
        "magnet": [],
        "back_plate": [],
        "pole_piece": [],
        "coil_air": [],
        "near_air": [],
        "far_air": [],
    }

    for dim, tag in fragments:
        if dim != 2:
            continue

        cx, cy = get_centroid(dim, tag)

        # ---- Motor parts (checked first — they take priority over air) ----
        if _in_rect(cx, cy, tpid / 2.0, -tpth / 2.0, tpod / 2.0, tpth / 2.0):
            groups["top_plate"].append(tag)
            continue

        if _in_rect(cx, cy, magid / 2.0, -tpth / 2.0 - magth, magod / 2.0, -tpth / 2.0):
            groups["magnet"].append(tag)
            continue

        # Back plate vs pole piece: both come from the fused BP+PP-vent shape.
        # Anything with centroid below the magnet bottom → back plate;
        # anything at or above → pole piece.
        # We also require it to be inside the original BP or PP bounding box.
        in_bp = _in_rect(cx, cy, 0.0, bp_y_bottom, bpod / 2.0, bp_y_bottom + bpth)
        in_pp = _in_rect(cx, cy, 0.0, bp_y_bottom, ppod / 2.0, bp_y_bottom + ppht + bpth)
        in_vent = _in_rect(cx, cy, 0.0, bp_y_bottom, ppvent / 2.0, bp_y_bottom + ppht + bpth)

        if (in_bp or in_pp) and not in_vent:
            if cy < -tpth / 2.0 - magth:
                groups["back_plate"].append(tag)
            else:
                groups["pole_piece"].append(tag)
            continue

        # Coil air (must be outside motor parts already checked above)
        if _in_rect(cx, cy, coil_r_min, coil_y_bottom, coil_r_max, coil_y_top):
            groups["coil_air"].append(tag)
            continue

        # ---- Air regions ----
        dist_from_centre = math.hypot(cx, cy - delta_y)
        if dist_from_centre < rad_1:
            groups["near_air"].append(tag)
        else:
            groups["far_air"].append(tag)

    # ── Assign Physical Groups ──
    # Curves (1-D) — axis and outer boundary
    axis_tags = []
    outer_arc_tags = []
    for dim, tag in gmsh.model.getEntities(1):
        bbox = gmsh.model.getBoundingBox(dim, tag)
        x_min, y_min, z_min, x_max, y_max, z_max = bbox
        # Axis: line on r = 0 (tolerant — fragmented axis segments may have tiny rounding errors)
        if abs(x_min) < 1e-5 and abs(x_max) < 1e-5:
            axis_tags.append(tag)
        # Outer boundary: arc at approximately r = rad_2
        elif x_max > rad_2 * 0.99 and y_min > delta_y - rad_2 * 1.01 and y_max < delta_y + rad_2 * 1.01:
            outer_arc_tags.append(tag)

    if axis_tags:
        pg_axis = gmsh.model.addPhysicalGroup(1, axis_tags)
        gmsh.model.setPhysicalName(1, pg_axis, "axis")
    if outer_arc_tags:
        pg_outer = gmsh.model.addPhysicalGroup(1, outer_arc_tags)
        gmsh.model.setPhysicalName(1, pg_outer, "outer_boundary")

    # Surfaces (2-D)
    for name, tags in groups.items():
        if not tags:
            continue
        pg = gmsh.model.addPhysicalGroup(2, tags)
        gmsh.model.setPhysicalName(2, pg, name)

    # ── Mesh-size fields ──
    gmsh.option.setNumber("Mesh.CharacteristicLengthMax", coarse_size)
    gmsh.option.setNumber("Mesh.CharacteristicLengthMin", fine_size)

    # Use a Threshold field driven by distance from the air-gap centre.
    # This gives fine elements at the gap and grades smoothly to coarse
    # elements in the far field without producing an explosion of triangles.
    gap_cx = (ppod / 2.0 + tpid / 2.0) / 2.0
    gap_cy = 0.0

    # 1. Distance from a point in the air gap
    dist_field = gmsh.model.mesh.field.add("Distance")
    # We use a list of curves that bound the air gap.
    # After fragmentation these curves have been recreated; we identify them
    # below by their bounding boxes.
    air_gap_curves = []
    for dim, tag in gmsh.model.getEntities(1):
        bbox = gmsh.model.getBoundingBox(dim, tag)
        x_min, y_min, z_min, x_max, y_max, z_max = bbox
        # Curves that lie in the air-gap annulus (pole OD … top plate ID)
        if x_min >= ppod / 2.0 - 0.1 and x_max <= tpid / 2.0 + 0.1:
            if y_min >= -tpth / 2.0 - magth - 0.1 and y_max <= tpth / 2.0 + 0.1:
                air_gap_curves.append(tag)

    if air_gap_curves:
        gmsh.model.mesh.field.setNumbers(dist_field, "CurvesList", air_gap_curves)
    else:
        # Fallback: distance from the gap centre point
        pt = occ.addPoint(gap_cx, gap_cy, 0.0)
        occ.synchronize()
        gmsh.model.mesh.field.setNumbers(dist_field, "PointsList", [pt])

    # 2. Threshold: fine near the gap, coarse far away
    thresh_field = gmsh.model.mesh.field.add("Threshold")
    gmsh.model.mesh.field.setNumber(thresh_field, "IField", dist_field)
    gmsh.model.mesh.field.setNumber(thresh_field, "LcMin", fine_size)
    gmsh.model.mesh.field.setNumber(thresh_field, "LcMax", coarse_size)
    gmsh.model.mesh.field.setNumber(thresh_field, "DistMin", 3.0)
    gmsh.model.mesh.field.setNumber(thresh_field, "DistMax", 60.0)

    # 3. Cap steel / magnet regions at medium_size so they do not blow
    #    up to coarse_size far from the air gap (back plate, magnet …).
    const_field = gmsh.model.mesh.field.add("MathEval")
    gmsh.model.mesh.field.setString(const_field, "F", str(medium_size))

    restrict_field = gmsh.model.mesh.field.add("Restrict")
    gmsh.model.mesh.field.setNumber(restrict_field, "IField", const_field)
    steel_magnet_surfaces: List[int] = []
    for pg_dim, pg_tag in gmsh.model.getPhysicalGroups(2):
        name = gmsh.model.getPhysicalName(pg_dim, pg_tag)
        if name in ("back_plate", "magnet", "pole_piece", "top_plate"):
            for surf_tag in gmsh.model.getEntitiesForPhysicalGroup(pg_dim, pg_tag):
                steel_magnet_surfaces.append(int(surf_tag))
    gmsh.model.mesh.field.setNumbers(restrict_field, "SurfacesList", steel_magnet_surfaces)

    # 4. Take the minimum of the threshold and the restricted cap
    min_field = gmsh.model.mesh.field.add("Min")
    gmsh.model.mesh.field.setNumbers(min_field, "FieldsList", [thresh_field, restrict_field])
    gmsh.model.mesh.field.setAsBackgroundMesh(min_field)

    # ── Generate mesh ──
    gmsh.model.mesh.generate(2)

    # ── Save ──
    out_dir = Path(directory)
    out_dir.mkdir(parents=True, exist_ok=True)
    msh_path = out_dir / "motor.msh"
    gmsh.write(str(msh_path))

    # Also write an unrolled GEO for visual inspection
    geo_path = out_dir / "motor.geo_unrolled"
    gmsh.write(str(geo_path))

    # ── Statistics ──
    num_nodes = gmsh.model.mesh.getNodes()[0].shape[0]
    num_elems = len(gmsh.model.mesh.getElementsByType(2)[0])  # triangles
    print(f"[geometry_builder] Mesh saved to {msh_path}")
    print(f"[geometry_builder] Nodes: {num_nodes}, Triangles: {num_elems}")
    for name, tags in groups.items():
        if tags:
            elem_count = 0
            for t in tags:
                etypes, etags, _ = gmsh.model.mesh.getElements(2, t)
                for tag_list in etags:
                    elem_count += len(tag_list)
            print(f"[geometry_builder]   {name}: {len(tags)} surface(s), {elem_count} element(s)")

    gmsh.finalize()
    return msh_path


# ─── CLI / self-test ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    from src.models import LoudspeakerDesign
    from src.engine import initialize_formula_defaults

    # Default design (same defaults as MotorModel)
    design = LoudspeakerDesign()
    design = initialize_formula_defaults(design)

    # Allow overriding mesh_size_factor from command line
    if len(sys.argv) > 1:
        design.mesh_size_factor = float(sys.argv[1])

    workdir = Path(".tmp/test_mesh")
    msh_path = build_geometry(design, str(workdir))
    print(f"\nOutput: {msh_path.resolve()}")
