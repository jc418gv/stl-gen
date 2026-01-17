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
    # try:
    #     base = base.edges("|Z and >Z").chamfer(0.6)
    # except ValueError:
    #     pass

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

    # Front-face Fresnel opening: spans entire width and height for unobstructed sensor insertion
    fresnel_w = outer_y
    fresnel_cutter = (
        cq.Workplane("XZ").workplane(offset=-outer_y / 2)
        .rect(fresnel_w, INNER_Z - WALL)
        .translate((0, 0, WALL))
        .extrude(27, both=True)
    )
    base = base.cut(fresnel_cutter)

    # Cut cutouts in the top frame for lid tabs
    # Front/back cutouts
    x_positions = [-(INNER_X / 2 - TAB_W / 2 - 4.0), (INNER_X / 2 - TAB_W / 2 - 4.0)]
    for y_sign in (-1,):  # Cut tabs for the solid long wall (that the pins plug into)
        for x in x_positions:
            cutout_fb = (
                cq.Workplane("XY")
                .box(TAB_W + RIM_CLEARANCE, WALL + RIM_CLEARANCE, WALL)
                .translate((x, y_sign * (outer_y / 2 - WALL / 2), outer_z / 2 - WALL / 2))
            )
            base = base.cut(cutout_fb)

    # Cut out the other long wall entirely as a single full-height notch
    # Span full Z (outer_z) and extend into the side walls so no floating pieces remain
    cutout_long_wall = (
        cq.Workplane("XY")
        .box(outer_x + 2 * WALL, WALL + RIM_CLEARANCE, WALL)
        .translate((0, outer_y / 2 - (WALL + RIM_CLEARANCE) / 2, outer_z / 2 - WALL / 2))
    )
    base = base.cut(cutout_long_wall)

    # Left/right cutouts
    y_positions = [-(INNER_Y / 2 - TAB_W / 2 - 4.0), (INNER_Y / 2 - TAB_W / 2 - 4.0)]
    for x_sign in (1, -1):
        for y in y_positions:
            cutout_lr = (
                cq.Workplane("XY")
                .box(WALL + RIM_CLEARANCE, TAB_W + RIM_CLEARANCE, WALL)
                .translate((x_sign * (outer_x / 2 - WALL / 2), y, outer_z / 2 - WALL / 2))
            )
            base = base.cut(cutout_lr)

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

    # Add extension on the Fresnel-edge of the lid, extruding in Z by wall height
    fresnel_edge_extension = (
        cq.Workplane("XY")
        .box(outer_x, WALL, WALL)
        # Move the center inside by WALL/2 so the outer face is coplanar
        # with the lid outer face (center at -outer_y/2 + WALL/2).
        .translate((0, -outer_y / 2 + WALL / 2, -LID_THICK / 2 - WALL / 2))
    )
    lid = lid.union(fresnel_edge_extension)

    # Add tabs protruding down from the lid bottom
    # Front/back tabs
    x_positions = [-(INNER_X / 2 - TAB_W / 2 - 4.0), (INNER_X / 2 - TAB_W / 2 - 4.0)]
    for y_sign in (1, -1):  # Both sides
        for x in x_positions:
            tab_fb = (
                cq.Workplane("XY")
                .box(TAB_W, WALL, TAB_H)
                .translate((x, y_sign * (outer_y / 2 - WALL / 2), -LID_THICK / 2 - TAB_H / 2))
            )
            lid = lid.union(tab_fb)

    # Left/right tabs
    y_positions = [-(INNER_Y / 2 - TAB_W / 2 - 4.0), (INNER_Y / 2 - TAB_W / 2 - 4.0)]
    for x_sign in (1, -1):
        for y in y_positions:
            tab_lr = (
                cq.Workplane("XY")
                .box(WALL, TAB_W, TAB_H)
                .translate((x_sign * (outer_x / 2 - WALL / 2), y, -LID_THICK / 2 - TAB_H / 2))
            )
            lid = lid.union(tab_lr)

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
