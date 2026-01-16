"""Prototype board case generator (25×50 mm board)

Generates a two-piece case (base + lid) with a slot on one short side
for a wiring connector. Adjustable parameters at top.
"""
from pathlib import Path
import cadquery as cq

# Board inner dimensions (mm)
INNER_X = 25.0  # board length (X)
INNER_Y = 50.0  # board width (Y)
INNER_Z = 12.0  # board thickness + clearance (Z)

WALL = 2.0
LID_THICK = 2.0

# Connector slot on short side (-Y face)
SLOT_W = 6.0  # along X (slot width)
SLOT_CLEAR_BOTTOM = 1.5  # gap from base bottom to slot bottom
SLOT_MARGIN = 0.5  # extra cut margin

OUT_DIR = Path(__file__).parent / "stl-draft"
OUT_DIR.mkdir(exist_ok=True)


def build_base():
    outer_x = INNER_X + 2 * WALL
    outer_y = INNER_Y + 2 * WALL
    outer_z = INNER_Z + WALL

    base = cq.Workplane("XY").box(outer_x, outer_y, outer_z)
    base = base.faces("+Z").shell(-WALL)

    # Connector slot on short (-Y) face: build cutter on XZ workplane
    # Create a rectangular top portion and a semicircular bottom, then
    # extrude in Y (both directions) by the wall thickness so only the wall
    # gets removed (no through-cut into interior).
    # Radius of the rounded bottom is half of SLOT_W (SLOT_W is diameter)
    R = SLOT_W / 2.0
    eps = 0.01
    top_z = outer_z / 2.0

    # Build rectangle portion as a polygon so its top aligns with the
    # inner top opening (after the +Z shell). This ensures the slot
    # opens into the case top. Use vertices in the XZ plane:
    # (-R, inner_top) -> (R, inner_top) -> (R, 0) -> (-R, 0)
    # Top of the rectangular cutter must reach the open top plane so
    # the slot opens to the case edge; place slightly above to ensure
    # a clean boolean: outer_z/2 + eps
    inner_top_z = outer_z / 2.0 + eps
    poly = [(-R, inner_top_z), (R, inner_top_z), (R, 0.0), (-R, 0.0)]

    rect_sketch = cq.Workplane("XZ").workplane(offset=-outer_y / 2).polyline(poly).close()
    rect_cut = rect_sketch.extrude(WALL + SLOT_MARGIN, both=True)

    # Circle centered at Z=0 provides the rounded bottom (radius = R)
    circ_sketch = cq.Workplane("XZ").workplane(offset=-outer_y / 2).circle(R)
    circ_cut = circ_sketch.extrude(WALL + SLOT_MARGIN, both=True).translate((0, 0, 0.0))

    # Union rectangle + circle so the sides are vertical (tangent at Z=0)
    slot_cutter = rect_cut.union(circ_cut)
    base = base.cut(slot_cutter)

    return base


def build_lid():
    outer_x = INNER_X + 2 * WALL
    outer_y = INNER_Y + 2 * WALL

    lid = cq.Workplane("XY").box(outer_x, outer_y, LID_THICK)

    # Simple inset lip for fit
    lip_inner_x = INNER_X - 2 * 0.25
    lip_inner_y = INNER_Y - 2 * 0.25
    lip = (
        cq.Workplane("XY").workplane(offset=-1.2).rect(lip_inner_x, lip_inner_y).extrude(1.2)
    )
    lid = lid.union(lip)

    return lid


def export():
    base = build_base()
    lid = build_lid()

    base_path = OUT_DIR / "proto_board_base.stl"
    lid_path = OUT_DIR / "proto_board_lid.stl"
    cq.exporters.export(base, str(base_path))
    cq.exporters.export(lid, str(lid_path))
    print(f"Exported {base_path}")
    print(f"Exported {lid_path}")


if __name__ == "__main__":
    export()
