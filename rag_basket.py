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

    # Slot on front (+Y): create an explicit cutter on a global XZ workplane
    slot_cut_height = height * slot_depth_ratio
    margin = 5.0
    total_cut_h = slot_cut_height + margin
    cut_center_z = height / 2 - slot_cut_height / 2 + margin / 2

    # Build a rectangular cutter and place it so it starts at the outer front face and extrudes inward
    cutter = (
        cq.Workplane("XZ")
        .rect(slot_width, total_cut_h)
        .extrude(-(depth + 10))  # long enough to cut fully through the front area
        .translate((0, depth / 2, cut_center_z))
    )
    model = model.cut(cutter)

    # Diamond profile defined inline per-face (no shared intermediate variable)

    def create_lattice_for_face(cad_obj: cq.Workplane, face_selector: str):
        """Create and apply diamond cutters positioned in world coordinates for the given face.

        This avoids selecting faces and using `.workplane()` which can fail when multiple
        coplanar or inner/outer faces are present.
        """
        # Determine usable face sizes based on outer dims and wall thickness
        if face_selector in ("-Y", "+Y"):
            face_w = width - 2 * wall_thickness
            face_h = height - wall_thickness  # top is open
        else:  # X-facing
            face_w = depth - 2 * wall_thickness
            face_h = height - wall_thickness

        usable_w = face_w - 2 * lattice_offset_edge
        usable_h = face_h - 2 * lattice_offset_edge

        nx = int(usable_w / (diamond_width + diamond_spacing_x))
        ny = int(usable_h / (diamond_height + diamond_spacing_y))

        if nx <= 0 or ny <= 0:
            return cad_obj

        grid_total_w = nx * diamond_width + (nx - 1) * diamond_spacing_x
        grid_total_h = ny * diamond_height + (ny - 1) * diamond_spacing_y

        points = []
        for j in range(ny):
            for i in range(nx):
                lx = -grid_total_w / 2 + diamond_width / 2 + i * (
                    diamond_width + diamond_spacing_x
                )
                lz = -grid_total_h / 2 + diamond_height / 2 + j * (
                    diamond_height + diamond_spacing_y
                )
                points.append((lx, lz))

        # For each face, create diamond cutters in the correct plane and translate them to face coordinate
        for (px, pz) in points:
            if face_selector == "-Y":
                # plane XZ, face y = -depth/2
                cutter = (
                    cq.Workplane("XZ")
                    .polyline([
                        (0, diamond_height / 2),
                        (diamond_width / 2, 0),
                        (0, -diamond_height / 2),
                        (-diamond_width / 2, 0),
                    ])
                    .close()
                    .extrude(depth + 10)
                    .val()
                    .moved(cq.Location(cq.Vector(px, -depth / 2, pz)))
                )
            elif face_selector == "+X":
                # plane YZ, face x = width/2
                cutter = (
                    cq.Workplane("YZ")
                    .polyline([
                        (0, diamond_height / 2),
                        (diamond_width / 2, 0),
                        (0, -diamond_height / 2),
                        (-diamond_width / 2, 0),
                    ])
                    .close()
                    .extrude(width + 10)
                    .val()
                    .moved(cq.Location(cq.Vector(width / 2, px, pz)))
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
                    .extrude(width + 10)
                    .val()
                    .moved(cq.Location(cq.Vector(-width / 2, px, pz)))
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
                    .extrude(depth + 10)
                    .val()
                    .moved(cq.Location(cq.Vector(px, depth / 2, pz)))
                )

            cad_obj = cad_obj.cut(cutter)

        return cad_obj

    for side in ["-Y", "+X", "-X"]:
        cutters = create_lattice_for_face(model, side)
        if cutters:
            model = model.cut(cutters)

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
        out_dir = Path(args.out_dir) if args.out_dir else script_dir / "stl-draft"
        # If passed a relative path, resolve it relative to script dir
        if not out_dir.is_absolute():
            out_dir = script_dir / out_dir

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


