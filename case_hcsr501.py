"""Parametric HC-SR501 case generator.

Builds a two-part case (base + lid) with 2 mm walls, an angled pin opening on the back face,
and a matching lid with an inset lip. Outputs STL files into stl-draft/ by default.
"""
from pathlib import Path
import math
import cadquery as cq

# Default dimensions (mm)
INNER_X = 33.0  # payload length
INNER_Y = 25.0  # payload width (depth in Y)
INNER_Z = 44.0  # payload height
WALL = 2.0
LID_THICK = 2.0

# Pin opening parameters (on +Y face, bottom edge)
PIN_OPEN_WIDTH = 10.0  # along X
PIN_OPEN_HEIGHT = 4.0  # rectangular portion height
PIN_OPEN_SIDE_ANGLE = math.radians(40.0)  # taper angle from horizontal
PIN_OPEN_CLEAR_BOTTOM = 0.8  # lift from absolute bottom to avoid paper-thin edge
EXTRUDE_MARGIN = 0.5  # extra penetration beyond wall to ensure robust boolean
TAB_W = 6.0
TAB_H = 1.2  # match lip height

# Lid lip fit
LIP_HEIGHT = 1.2
LIP_CLEARANCE = 0.25  # clearance on each side for press fit
RIM_CLEARANCE = 0.3   # clearance for rim cutouts
RIM_HEIGHT = TAB_H    # outer rim drop down to match tabs

OUT_DIR = Path(__file__).parent / "stl-draft"
OUT_DIR.mkdir(exist_ok=True)


def build_base():
    outer_x = INNER_X + 2 * WALL
    outer_y = INNER_Y + 2 * WALL
    outer_z = INNER_Z + WALL  # bottom thickness included; lid adds its own thickness

    base = cq.Workplane("XY").box(outer_x, outer_y, outer_z)
    base = base.faces("+Z").shell(-WALL)  # open top shell; negative for inward shell

    # Add a small outer chamfer on the top edge for easier lid seating (if edges exist)
    try:
        base = base.edges("|Z and >Z").chamfer(0.6)
    except ValueError:
        pass

    # Back-face pin opening with tapered top
    # Coordinates on XZ plane of +Y face; origin at face center (x,z), y=const
    half_w = PIN_OPEN_WIDTH / 2.0
    rect_h = PIN_OPEN_HEIGHT
    tri_h = half_w * math.tan(PIN_OPEN_SIDE_ANGLE)
    z_bottom = -outer_z / 2 + WALL + PIN_OPEN_CLEAR_BOTTOM
    z_rect_top = z_bottom + rect_h
    z_apex = z_rect_top + tri_h

    polygon = [
        (-half_w, z_bottom),
        (half_w, z_bottom),
        (half_w, z_rect_top),
        (0.0, z_apex),
        (-half_w, z_rect_top),
    ]
    # Build cutter on XZ plane offset to +Y face; limit extrusion to wall thickness
    pin_cutter = (
        cq.Workplane("XZ").workplane(offset=outer_y / 2)
        .polyline(polygon)
        .close()
        .extrude(WALL + EXTRUDE_MARGIN, both=True)
    )
    base = base.cut(pin_cutter)

    # Front-face Fresnel opening: centered, 24 mm wide, full wall height (avoid cutting floor)
    fresnel_w = 24.0
    half_fw = fresnel_w / 2.0
    fresnel_cutter = (
        cq.Workplane("XZ").workplane(offset=-outer_y / 2)
        .rect(fresnel_w, outer_z - WALL)
        .extrude(WALL + EXTRUDE_MARGIN, both=True)
    )
    base = base.cut(fresnel_cutter)

    # Add vertical tabs on TOP of walls (z-axis); outside the interior opening
    # Front/back walls: tabs span along X, thickness across Y equals WALL
    x_positions = [-(INNER_X / 2 - TAB_W / 2 - 4.0), (INNER_X / 2 - TAB_W / 2 - 4.0)]
    for y_sign in (1, -1):
        for x in x_positions:
            tab_fb = (
                cq.Workplane("XY")
                .box(TAB_W, WALL, TAB_H)
                .translate((x, y_sign * (INNER_Y / 2 + WALL / 2), (outer_z / 2 + TAB_H / 2)))
            )
            base = base.union(tab_fb)

    # Left/right walls: tabs span along Y, thickness across X equals WALL
    y_positions = [-(INNER_Y / 2 - TAB_W / 2 - 4.0), (INNER_Y / 2 - TAB_W / 2 - 4.0)]
    for x_sign in (1, -1):
        for y in y_positions:
            tab_lr = (
                cq.Workplane("XY")
                .box(WALL, TAB_W, TAB_H)
                .translate((x_sign * (INNER_X / 2 + WALL / 2), y, (outer_z / 2 + TAB_H / 2)))
            )
            base = base.union(tab_lr)

    return base


def build_lid():
    outer_x = INNER_X + 2 * WALL
    outer_y = INNER_Y + 2 * WALL

    lid = cq.Workplane("XY").box(outer_x, outer_y, LID_THICK)

    # Add an inset lip that drops inside the case for a snug fit
    lip_inner_x = INNER_X - 2 * LIP_CLEARANCE
    lip_inner_y = INNER_Y - 2 * LIP_CLEARANCE
    lip = (
        cq.Workplane("XY")
        .workplane(offset=-LIP_HEIGHT)
        .rect(lip_inner_x, lip_inner_y)
        .extrude(LIP_HEIGHT)
    )
    lid = lid.union(lip)

    # Add an OUTER rim (outside walls) that drops down; cutouts match wall-top tabs
    rim_outer = (
        cq.Workplane("XY")
        .workplane(offset=-RIM_HEIGHT)
        .rect(outer_x, outer_y)
        .extrude(RIM_HEIGHT)
    )
    rim_inner = (
        cq.Workplane("XY")
        .workplane(offset=-RIM_HEIGHT)
        .rect(outer_x - 2 * WALL, outer_y - 2 * WALL)
        .extrude(RIM_HEIGHT)
    )
    rim = rim_outer.cut(rim_inner)
    lid = lid.union(rim)

    # Cut matching slots in the OUTER rim to accommodate the vertical tabs
    slot_w = TAB_W + RIM_CLEARANCE
    slot_y_thickness = WALL + RIM_CLEARANCE
    x_positions = [-(INNER_X / 2 - TAB_W / 2 - 4.0), (INNER_X / 2 - TAB_W / 2 - 4.0)]
    for y_sign in (1, -1):
        for x in x_positions:
            slot_fb = (
                cq.Workplane("XY")
                .box(slot_w, slot_y_thickness, RIM_HEIGHT)
                .translate((x, y_sign * (outer_y / 2 - WALL / 2), -RIM_HEIGHT / 2))
            )
            lid = lid.cut(slot_fb)

    y_positions = [-(INNER_Y / 2 - TAB_W / 2 - 4.0), (INNER_Y / 2 - TAB_W / 2 - 4.0)]
    slot_x_thickness = WALL + RIM_CLEARANCE
    for x_sign in (1, -1):
        for y in y_positions:
            slot_lr = (
                cq.Workplane("XY")
                .box(slot_x_thickness, slot_w, RIM_HEIGHT)
                .translate((x_sign * (outer_x / 2 - WALL / 2), y, -RIM_HEIGHT / 2))
            )
            lid = lid.cut(slot_lr)

    # Chamfer outer top edges for feel
    try:
        lid = lid.edges("|Z and >Z").chamfer(0.6)
    except ValueError:
        pass
    return lid


def export():
    base = build_base()
    lid = build_lid()

    base_path = OUT_DIR / "hcsr501_case_base.stl"
    lid_path = OUT_DIR / "hcsr501_case_lid.stl"
    cq.exporters.export(base, str(base_path))
    cq.exporters.export(lid, str(lid_path))
    print(f"Exported {base_path}")
    print(f"Exported {lid_path}")


if __name__ == "__main__":
    export()
