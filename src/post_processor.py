"""Post-processing: sampling of B-field from Elmer VTU output.

These functions reproduce FEMM behaviours:

* ``mo_lineintegral(0)`` → :func:`average_b_on_line`
* ``mo_getpointvalues(x, y)`` → :func:`sample_point`
"""

from __future__ import annotations

import warnings
from pathlib import Path

from src.models import LoudspeakerDesign


def _load_b_field(vtu_path: Path) -> tuple:
    """Load a VTU and return mesh points plus B-field components.

    Returns
    -------
    points : ndarray, shape (N, 2)
        Mesh node coordinates ``(r, z)``.
    b_mag : ndarray, shape (N,)
        |B| magnitude  ``√(Br² + Bz²)`` per node.
    br : ndarray, shape (N,)
        Radial component ``Br`` per node.
    bz : ndarray, shape (N,)
        Axial component ``Bz`` per node.
    """
    try:
        import meshio
        import numpy as np
    except ImportError as exc:
        raise ImportError(
            "post_processor requires meshio and numpy. "
            f"Missing dependency: {exc.name}"
        ) from exc

    data = meshio.read(str(vtu_path))
    points = data.points[:, :2]

    b_vec = data.point_data.get("magnetic flux density")
    if b_vec is None:
        raise KeyError(
            f"'magnetic flux density' not found in {vtu_path}. "
            f"Available fields: {list(data.point_data.keys())}"
        )

    br = b_vec[:, 0]
    bz = b_vec[:, 1]
    b_mag = np.sqrt(br ** 2 + bz ** 2)
    return points, b_mag, br, bz


def sample_line(
    vtu_path: Path,
    p1: tuple[float, float],
    p2: tuple[float, float],
    n_samples: int = 100,
) -> list[float]:
    """Return |B| values sampled along the line from *p1* to *p2*.

    Parameters
    ----------
    vtu_path:
        Path to the Elmer ``.vtu`` output file.
    p1, p2:
        Start and end points as ``(r, z)`` tuples (axisymmetric coordinates).
    n_samples:
        Number of evenly-spaced sample points along the line.

    Returns
    -------
    List of ``n_samples`` |B| magnitudes in teslas.  Points that fall
    outside the mesh are replaced by ``0.0`` and a warning is emitted.
    """
    try:
        import numpy as np
        from scipy.interpolate import LinearNDInterpolator
    except ImportError as exc:
        raise ImportError(
            "post_processor requires numpy and scipy. "
            f"Missing dependency: {exc.name}"
        ) from exc

    points, b_mag, _, _ = _load_b_field(vtu_path)
    interpolator = LinearNDInterpolator(points, b_mag)

    t = np.linspace(0.0, 1.0, n_samples)
    sample_pts = np.column_stack(
        [
            p1[0] + t * (p2[0] - p1[0]),
            p1[1] + t * (p2[1] - p1[1]),
        ]
    )

    values = interpolator(sample_pts)

    nan_mask = np.isnan(values)
    if nan_mask.any():
        n_nan = int(nan_mask.sum())
        warnings.warn(
            f"{n_nan}/{n_samples} sample points fall outside the mesh; "
            f"returning 0.0 for those points.",
            RuntimeWarning,
            stacklevel=2,
        )
        values = np.nan_to_num(values, nan=0.0)

    return values.tolist()


def average_b_on_line(
    vtu_path: Path,
    p1: tuple[float, float],
    p2: tuple[float, float],
) -> float:
    """Return the average |B| along the line (matches FEMM ``mo_lineintegral(0)``).

    Parameters
    ----------
    vtu_path:
        Path to the Elmer ``.vtu`` output file.
    p1, p2:
        Start and end points as ``(r, z)`` tuples.

    Returns
    -------
    Average |B| magnitude in teslas.
    """
    samples = sample_line(vtu_path, p1, p2, n_samples=100)
    import numpy as np
    return float(np.mean(samples))


def sample_point(
    vtu_path: Path,
    r: float,
    z: float,
) -> tuple[float, float, float]:
    """Return (|B|, Br, Bz) at a single point.

    Parameters
    ----------
    vtu_path:
        Path to the Elmer ``.vtu`` output file.
    r, z:
        Query coordinates in the axisymmetric plane.

    Returns
    -------
    Tuple ``(|B|, Br, Bz)`` in teslas.  If the point lies outside the
    mesh convex hull, a warning is emitted and ``(0.0, 0.0, 0.0)`` is
    returned.
    """
    try:
        import numpy as np
        from scipy.interpolate import LinearNDInterpolator
    except ImportError as exc:
        raise ImportError(
            "post_processor requires numpy and scipy. "
            f"Missing dependency: {exc.name}"
        ) from exc

    points, b_mag, br, bz = _load_b_field(vtu_path)

    interp_r = LinearNDInterpolator(points, br)
    interp_z = LinearNDInterpolator(points, bz)

    query = np.array([[r, z]])
    val_r = float(interp_r(query)[0])
    val_z = float(interp_z(query)[0])

    if np.isnan(val_r):
        warnings.warn(
            f"Point ({r}, {z}) falls outside the mesh; returning (0, 0, 0).",
            RuntimeWarning,
            stacklevel=2,
        )
        return (0.0, 0.0, 0.0)

    val_mag = float(np.sqrt(val_r ** 2 + val_z ** 2))
    return (val_mag, val_r, val_z)


def extract_vc_sweep(vtu_path: Path, design: LoudspeakerDesign) -> dict:
    """Extract the voice-coil sweep (BL(x) curve) from a solved VTU.

    This reproduces FEMM's logic: the coil is notionally moved through the
    air gap in 61 discrete steps, and the average |B| along the coil height
    is recorded at each position.

    Parameters
    ----------
    vtu_path:
        Path to the Elmer ``.vtu`` output file.
    design:
        Loudspeaker design parameters (must have derived fields populated by
        :func:`src.engine.recalculate_derived`).

    Returns
    -------
    dict with keys:
        * ``b_at_zero`` – B_avg at position 0 (mm).
        * ``data_points`` – always 61.
        * ``bmagnet`` – B_avg at ``+overhang`` (top of sweep).
        * ``bbuck`` – B_avg at ``-overhang`` (bottom of sweep).
        * ``vc_sweep`` – list of 61 ``(position_mm, B_avg_T)`` tuples.
        * ``raw_b`` – list of 61 ``(position_mm, |B|_T)`` point samples.
    """
    vtu_path = Path(vtu_path)

    # Design parameters are in mm (same unit system as the mesh)
    vc_radius = design.vc_location_diameter / 2.0
    vc_ww = design.ww
    vc_offset = design.vc_offset
    overhang = design.overhang

    # Sweep range: 61 points from -Xmax to +Xmax
    xmax = overhang * 1.15
    step = 2.0 * xmax / 60.0

    vc_sweep: list[tuple[float, float]] = []
    raw_b: list[tuple[float, float]] = []

    for k in range(61):
        pos = -xmax + k * step

        # Line through the coil height at this position
        z_top = vc_ww / 2.0 + pos + vc_offset
        z_bottom = -vc_ww / 2.0 + pos + vc_offset
        p1 = (vc_radius, z_top)
        p2 = (vc_radius, z_bottom)

        b_avg = average_b_on_line(vtu_path, p1, p2)
        vc_sweep.append((pos, b_avg))

        # Raw point at coil centre — FEMM reference samples at (VCdia/2, Xpos) with NO vc_offset
        b_mag, _, _ = sample_point(vtu_path, vc_radius, pos)
        raw_b.append((pos, b_mag))

    # b_at_zero: find the entry closest to position 0
    zero_idx = min(range(61), key=lambda i: abs(vc_sweep[i][0]))
    b_at_zero = vc_sweep[zero_idx][1]

    # bmagnet: average B across the magnet radial cross-section at the magnet center
    mag_center_y = -design.top_plate_thickness / 2.0 - design.magnet_thickness / 2.0
    bmagnet = average_b_on_line(
        vtu_path,
        (design.magnet_id / 2.0, mag_center_y),
        (design.magnet_od / 2.0, mag_center_y),
    )
    # LoudspeakerFEA does not have bucking magnets
    bbuck = 0.0

    return {
        "b_at_zero": b_at_zero,
        "data_points": 61,
        "bmagnet": bmagnet,
        "bbuck": bbuck,
        "vc_sweep": vc_sweep,
        "raw_b": raw_b,
    }


def extract_side_leakage(
    vtu_path: Path,
    design: LoudspeakerDesign,
    n_points: int = 100,
) -> list[float]:
    """Return |B| along the side-leakage contour (matches FEMM ``mo_makeplot()``).

    The contour is a vertical line located *outside* the magnet OD at a
    distance controlled by ``design.side_leakage_distance``.

    Parameters
    ----------
    vtu_path:
        Path to the Elmer ``.vtu`` output file.
    design:
        Loudspeaker design parameters (must have derived fields populated).
    n_points:
        Number of sample points along the leakage line (default 100).

    Returns
    -------
    List of ``n_points`` |B| magnitudes in teslas.
    """
    vtu_path = Path(vtu_path)

    # Design parameters are in mm (same unit system as the mesh)
    leak_r = design.magnet_od / 2.0 + design.side_leakage_distance

    # Vertical line from +2*leak_r to -2*leak_r at radius leak_r
    p1 = (leak_r, 2.0 * leak_r)
    p2 = (leak_r, -2.0 * leak_r)

    return sample_line(vtu_path, p1, p2, n_samples=n_points)


def generate_density_plot(
    vtu_path: Path,
    design: LoudspeakerDesign,
    output_path: Path,
) -> None:
    """Generate and save a B-field density plot PNG from a solved VTU.

    This replaces FEMM's ``mo_showdensityplot()`` + ``mo_savebitmap()``.

    Parameters
    ----------
    vtu_path:
        Path to the Elmer ``.vtu`` output file.
    design:
        Loudspeaker design parameters (used for title/annotation only).
    output_path:
        Destination path for the PNG image.
    """
    try:
        import meshio
        import numpy as np
        import matplotlib.pyplot as plt
        import matplotlib.tri as mtri
        from matplotlib.ticker import FormatStrFormatter
    except ImportError as exc:
        raise ImportError(
            "post_processor requires meshio, numpy and matplotlib. "
            f"Missing dependency: {exc.name}"
        ) from exc

    vtu_path = Path(vtu_path)
    output_path = Path(output_path)

    data = meshio.read(str(vtu_path))
    points = data.points[:, :2]  # (r, z)

    triangles = data.cells_dict.get("triangle")
    if triangles is None:
        raise ValueError(
            f"No triangle cells found in {vtu_path}. "
            f"Available cell types: {list(data.cells_dict.keys())}"
        )

    b_vec = data.point_data.get("magnetic flux density")
    if b_vec is None:
        raise KeyError(
            f"'magnetic flux density' not found in {vtu_path}. "
            f"Available fields: {list(data.point_data.keys())}"
        )

    # |B| = sqrt(Br^2 + Bz^2 + Bphi^2); Bphi is zero in 2-D axisymmetric
    b_mag = np.linalg.norm(b_vec, axis=1)

    # Build triangulation and interpolate onto a regular grid
    triang = mtri.Triangulation(points[:, 0], points[:, 1], triangles)
    interp = mtri.LinearTriInterpolator(triang, b_mag)

    # Motor-geometry bounds (same logic as FEMM reference) so the motor fills the frame
    r_min = 0.0
    r_max = max(design.top_plate_od, design.magnet_od, design.bp_od) / 2.0 + 20.0
    z_min = -(design.bp_thickness + design.magnet_thickness + design.top_plate_thickness) - 20.0
    z_max = design.top_plate_thickness / 2.0 + 20.0

    # Use a fine grid for smooth appearance
    grid_r, grid_z = np.mgrid[r_min:r_max:800j, z_min:z_max:800j]
    grid_b = interp(grid_r, grid_z)

    # Mask NaN (outside convex hull) so they don't distort the colour scale
    grid_b = np.nan_to_num(grid_b, nan=0.0)

    fig, ax = plt.subplots(figsize=(8, 10))
    im = ax.imshow(
        grid_b.T,
        extent=[r_min, r_max, z_min, z_max],
        origin="lower",
        cmap="turbo",
        aspect="auto",
        interpolation="bilinear",
        vmin=0.0,
        vmax=2.0,
    )
    cbar = plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label("|B| (T)")
    # Fixed 0–2 T scale with decimal tick labels (no scientific notation)
    cbar.ax.yaxis.set_major_formatter(FormatStrFormatter("%.2f"))

    ax.set_xlabel("r (mm)")
    ax.set_ylabel("z (mm)")
    ax.set_title(f"Magnetic Flux Density — {design.name}")

    plt.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(str(output_path), dpi=150)
    plt.close(fig)


def write_output_files(
    output_dir: Path,
    vc_results: dict,
    side_leakage: list[float],
    design: LoudspeakerDesign,
) -> None:
    """Write ``VCSweepOutput.txt`` and ``leakage contour.txt`` in FEMM-compatible format.

    The file structure is designed to be read by MotorModel's
    ``parse_femm_output()`` without modification.

    Parameters
    ----------
    output_dir:
        Directory where the two text files are written.
    vc_results:
        Dict returned by :func:`extract_vc_sweep`.
    side_leakage:
        List of |B| values returned by :func:`extract_side_leakage`.
    design:
        Loudspeaker design parameters (used for leakage-line geometry).
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # VCSweepOutput.txt
    # ------------------------------------------------------------------
    vc_path = output_dir / "VCSweepOutput.txt"
    lines: list[str] = []

    lines.append(f"B(x=0) = {vc_results['b_at_zero']:.6f}")
    lines.append(f"dataPoints = {vc_results['data_points']}")
    lines.append(f"Bmagnet = {vc_results['bmagnet']:.6f}")
    lines.append(f"Bbuck = {vc_results['bbuck']:.6f}")
    lines.append("VC Position\tB average over coil")

    for pos, b_avg in vc_results["vc_sweep"]:
        lines.append(f"{pos:.6f}\t{b_avg:.6f}")

    lines.append(f"B(x) dataPoints = {vc_results['data_points']}")
    lines.append("X Position \t|B| \tnot voice coil data, raw B point data")

    for pos, b_mag in vc_results["raw_b"]:
        lines.append(f"{pos:.6f}\t{b_mag:.6f}")

    try:
        vc_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except OSError as e:
        raise RuntimeError(f"Failed to write VC sweep output file {vc_path}: {e}") from e

    # ------------------------------------------------------------------
    # leakage contour.txt
    # ------------------------------------------------------------------
    leak_path = output_dir / "leakage contour.txt"

    # Leakage line geometry (same as extract_side_leakage)
    leak_r = design.magnet_od / 2.0 + design.side_leakage_distance
    z_top = 2.0 * leak_r
    z_bottom = -2.0 * leak_r
    n_points = len(side_leakage)

    leak_lines: list[str] = []
    for k, b_val in enumerate(side_leakage):
        # Vertical position along the line (z coordinate in mm)
        if n_points > 1:
            z = z_top + k * (z_bottom - z_top) / (n_points - 1)
        else:
            z = z_top
        leak_lines.append(f"{z:.6f}\t{b_val:.6f}")

    try:
        leak_path.write_text("\n".join(leak_lines) + "\n", encoding="utf-8")
    except OSError as e:
        raise RuntimeError(f"Failed to write leakage contour file {leak_path}: {e}") from e
