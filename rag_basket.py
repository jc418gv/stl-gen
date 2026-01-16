import os
import argparse
import cadquery as cq
from pathlib import Path

"""rag-basket.py

Modular rag basket generator compatible with the CadQuery MCP server.
- Exposes `make_rag_basket(...) -> cadquery.Workplane` for programmatic use
- Creates a module-level `result` variable and ends with `show_object(result)` per MCP requirements
- Provides a CLI to export to draft/final folders
"""

# --- Default Parameters (mm) ---
DEFAULT_WIDTH = 100.0
DEFAULT_DEPTH = 120.0
DEFAULT_HEIGHT = 150.0
DEFAULT_WALL = 2.0

DEFAULT_SLOT_WIDTH = 30.0
DEFAULT_SLOT_DEPTH_RATIO = 0.5

LATTICE_OFFSET_EDGE = 10.0
DIAMOND_WIDTH = 8.0
DIAMOND_HEIGHT = 12.0
DIAMOND_SPACING_X = 4.0
DIAMOND_SPACING_Y = 4.0


def make_rag_basket(
    width: float = DEFAULT_WIDTH,
    depth: float = DEFAULT_DEPTH,
    height: float = DEFAULT_HEIGHT,
    wall_thickness: float = DEFAULT_WALL,
    slot_width: float = DEFAULT_SLOT_WIDTH,
    slot_depth_ratio: float = DEFAULT_SLOT_DEPTH_RATIO,
    lattice_offset_edge: float = LATTICE_OFFSET_EDGE,
    diamond_width: float = DIAMOND_WIDTH,
    diamond_height: float = DIAMOND_HEIGHT,
    diamond_spacing_x: float = DIAMOND_SPACING_X,
    diamond_spacing_y: float = DIAMOND_SPACING_Y,
) -> cq.Workplane:
    """Build the rag basket cadquery object and return it.

    The bottom remains solid, the top is open, the front (+Y) has a slot
    that goes halfway down by default, and the back/left/right faces have
    a diamond lattice.
    """

    # Create base box and shell (leave top open)
    model = cq.Workplane("XY").box(width, depth, height)
    model = model.faces("+Z").shell(wall_thickness)

    # Slot: place the slot along the long edge of the footprint
    slot_cut_height = height * slot_depth_ratio
    margin = 5.0
    total_cut_h = slot_cut_height + margin
    cut_center_z = height / 2 - slot_cut_height / 2 + margin / 2

    # We'll compute slot bounds and use simple coordinate tests to decide
    # when to skip diamonds that would overlap the slot opening. Avoid
    # geometric intersection checks which can erroneously detect the
    # opposite face when cutters extrude through the part.

    if depth > width:
        # Long edge is along Y (depth). Place slot on +X face so slot width aligns with Y.
        cutter = (
            cq.Workplane("YZ")
            .rect(slot_width, total_cut_h)
            .extrude(-(width + 10))  # extrude through +X face
            .translate((width / 2, 0, cut_center_z))
        )
        # slot on +X face: define horizontal and vertical spans
        slot_face = "+X"
        slot_horiz_center = 0.0  # Y-axis center for the slot rect
        slot_horiz_half = slot_width / 2
        slot_min_z = cut_center_z - total_cut_h / 2
        slot_max_z = cut_center_z + total_cut_h / 2
    else:
        # Long edge is along X (width) or equal: place slot on +Y face (original behavior)
        cutter = (
            cq.Workplane("XZ")
            .rect(slot_width, total_cut_h)
            .extrude(-(depth + 10))  # long enough to cut fully through the front area
            .translate((0, depth / 2, cut_center_z))
        )
        # slot on +Y face: define horizontal and vertical spans
        slot_face = "+Y"
        slot_horiz_center = 0.0  # X-axis center for the slot rect
        slot_horiz_half = slot_width / 2
        slot_min_z = cut_center_z - total_cut_h / 2
        slot_max_z = cut_center_z + total_cut_h / 2
    model = model.cut(cutter)

    # Diamond profile defined inline per-face (no shared intermediate variable)

    def create_lattice_for_face(cad_obj: cq.Workplane, face_selector: str):
        """Create and apply diamond cutters positioned in world coordinates for the given face.

        This avoids selecting faces and using `.workplane()` which can fail when multiple
        coplanar or inner/outer faces are present.
        """
        # Build a list of cutters (TopoDS shapes) and return them. This keeps
        # the lattice generation consistent with diagnostic logic and avoids
        # applying cuts inside this helper (caller will apply them).
        if face_selector in ("-Y", "+Y"):
            face_w = width - 2 * wall_thickness
            face_h = height - wall_thickness
            plane = "XZ"
            depth_extra = depth + 10
        else:
            face_w = depth - 2 * wall_thickness
            face_h = height - wall_thickness
            plane = "YZ" if face_selector in ("+X", "-X") else "XZ"
            depth_extra = width + 10

        # Allow diamonds to reach side edges; keep vertical clearance from top/bottom
        usable_w = face_w
        usable_h = face_h - 2 * lattice_offset_edge
        nx = int(max(0, usable_w) / (diamond_width + diamond_spacing_x))
        ny = int(max(0, usable_h) / (diamond_height + diamond_spacing_y))

        cutters = []
        if nx <= 0 or ny <= 0:
            return cutters

        grid_total_w = nx * diamond_width + (nx - 1) * diamond_spacing_x
        grid_total_h = ny * diamond_height + (ny - 1) * diamond_spacing_y

        # Stagger rows so diamonds interlock
        for j in range(ny):
            row_offset = (diamond_width + diamond_spacing_x) / 2.0 if (j % 2) == 1 else 0.0
            for i in range(nx):
                lx = (
                    -grid_total_w / 2
                    + diamond_width / 2
                    + i * (diamond_width + diamond_spacing_x)
                    + row_offset
                )
                lz = -grid_total_h / 2 + diamond_height / 2 + j * (diamond_height + diamond_spacing_y)

                # Determine which face contains the slot (mirror of slot placement above)
                slot_face = "+X" if depth > width else "+Y"
                # We want to skip diamonds on the face opposite the slot face
                opposite_face = {"+X": "-X", "-X": "+X", "+Y": "-Y", "-Y": "+Y"}[slot_face]
                # Compute vertical bounds of the slot area so we can keep clearance
                slot_cut_height = height * slot_depth_ratio
                margin = 5.0
                total_cut_h = slot_cut_height + margin
                cut_center_z = height / 2 - slot_cut_height / 2 + margin / 2
                slot_min_z = cut_center_z - total_cut_h / 2
                slot_max_z = cut_center_z + total_cut_h / 2

                # Skip diamonds overlapping the slot region on the face opposite
                # the slot face (user requested). Use `lattice_offset_edge` as horizontal/vertical clearance.
                horiz_clear = slot_width / 2 + lattice_offset_edge
                # Compute global center coordinates for this diamond on the model
                if face_selector == "-Y":
                    center = (lx, -depth / 2, lz)
                elif face_selector == "+Y":
                    center = (lx, depth / 2, lz)
                elif face_selector == "+X":
                    center = (width / 2, lx, lz)
                elif face_selector == "-X":
                    center = (-width / 2, lx, lz)
                else:
                    center = (lx, 0, lz)

                cx, cy, cz = center
                # If this face is the opposite face to the slot, test the appropriate
                # horizontal coordinate (Y for X-facing slot, X for Y-facing slot)
                # and the vertical (Z) span before skipping.
                # Use a short symmetric extrusion length for diamonds
                extrude_len = wall_thickness + 2.0

                # Use coordinate tests against the computed slot bounding area
                # to decide skipping. This avoids false positives from full
                # through-thickness geometric cutters intersecting opposite faces.
                if face_selector == opposite_face:
                    if slot_face.endswith("X"):
                        within_horiz = abs(cy - slot_horiz_center) < (slot_horiz_half + lattice_offset_edge)
                    else:
                        within_horiz = abs(cx - slot_horiz_center) < (slot_horiz_half + lattice_offset_edge)
                    within_vert = (cz > (slot_min_z - lattice_offset_edge)) and (cz < (slot_max_z + lattice_offset_edge))
                    if within_horiz and within_vert:
                        continue

                # Use a short symmetric extrusion so cutter only penetrates the
                # wall thickness (with a small margin) and align it on the face
                # plane before moving into place.
                extrude_len = wall_thickness + 2.0
                if face_selector == "-Y":
                    cutter = (
                        cq.Workplane("XZ")
                        .polyline([
                            (0, diamond_height / 2),
                            (diamond_width / 2, 0),
                            (0, -diamond_height / 2),
                            (-diamond_width / 2, 0),
                        ])
                        .close()
                        .extrude(extrude_len, both=True)
                        .val()
                        .moved(cq.Location(cq.Vector(cx, cy, cz)))
                    )
                elif face_selector == "+X":
                    cutter = (
                        cq.Workplane("YZ")
                        .polyline([
                            (0, diamond_height / 2),
                            (diamond_width / 2, 0),
                            (0, -diamond_height / 2),
                            (-diamond_width / 2, 0),
                        ])
                        .close()
                        .extrude(extrude_len, both=True)
                        .val()
                        .moved(cq.Location(cq.Vector(cx, cy, cz)))
                    )
                elif face_selector == "-X":
                    cutter = (
                        cq.Workplane("YZ")
                        .polyline([
                            (0, diamond_height / 2),
                            (diamond_width / 2, 0),
                            (0, -diamond_height / 2),
                            (-diamond_width / 2, 0),
                        ])
                        .close()
                        .extrude(extrude_len, both=True)
                        .val()
                        .moved(cq.Location(cq.Vector(cx, cy, cz)))
                    )
                else:  # +Y or others
                    cutter = (
                        cq.Workplane("XZ")
                        .polyline([
                            (0, diamond_height / 2),
                            (diamond_width / 2, 0),
                            (0, -diamond_height / 2),
                            (-diamond_width / 2, 0),
                        ])
                        .close()
                        .extrude(extrude_len, both=True)
                        .val()
                        .moved(cq.Location(cq.Vector(cx, cy, cz)))
                    )

                cutters.append(cutter)

        return cutters

    # Apply cutters returned from the helper (iterate per-cutter for clarity).
    # Include both perpendicular walls (-Y and +Y) so both are cut.
    for side in ["-Y", "+Y", "+X", "-X"]:
        cutters = create_lattice_for_face(model, side)
        for c in cutters:
            model = model.cut(c)

    return model


# Build a default model at import-time for tools that expect `result` to exist
result = make_rag_basket()


def export_stl(cq_obj: cq.Workplane, out_dir: str, filename: str) -> str:
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, filename)
    cq.exporters.export(cq_obj, path)
    return path


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Generate rag-basket STL")
    # If not specified, resolve to a directory next to this script (prevents using process CWD)
    p.add_argument("--out-dir", default=None, help="Output directory (relative to script if unspecified)")
    p.add_argument("--filename", default="rag_basket.stl", help="Output filename")
    p.add_argument("--final", action="store_true", help="Place output into stl-final instead of stl-draft")
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    script_dir = Path(__file__).parent

    if args.final:
        out_dir = script_dir / "stl-final"
    else:
        if args.out_dir:
            out_dir = Path(args.out_dir)
            if not out_dir.is_absolute():
                out_dir = (Path.cwd() / out_dir).resolve()
        else:
            out_dir = script_dir / "stl-draft"

    out_path = export_stl(result, str(out_dir), args.filename)
    print(f"Generated {out_path}")
    print("Tip: move validated prints into `stl-final/` to track them in Git.")


# Ensure compatibility with CadQuery MCP server: provide a safe show_object
try:
    from cadquery import show_object  # type: ignore
except Exception:
    def show_object(_):
        """Dummy fallback for environments without CQ-editor"""
        return None

# Required for processing (some tools inspect files for this line)
# Use `.val()` to expose the underlying TopoDS shape to CQGI/ cq-cli
# Expose the TopoDS shape directly for cq-cli / CQGI
show_object(result.val())


