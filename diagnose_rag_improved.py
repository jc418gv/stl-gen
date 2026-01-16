"""Improved diagnostic script for rag basket.

Exports STLs at each step into `stl-draft/` alongside this script.
Idempotent: will skip existing files unless `--force` given.
"""
from pathlib import Path
import argparse
import logging
import cadquery as cq

OUT_DIR = Path(__file__).parent / 'stl-draft'
OUT_DIR.mkdir(exist_ok=True)

logger = logging.getLogger('diagnose')
logging.basicConfig(level=logging.INFO, format='%(message)s')

# Parameters
WIDTH = 100.0
DEPTH = 120.0
HEIGHT = 150.0
WALL = 2.0
SLOT_WIDTH = 30.0
SLOT_DEPTH_RATIO = 0.5


def export_if_needed(obj, filename: str, force: bool = False):
    out = OUT_DIR / filename
    if out.exists() and not force:
        logger.info(f"Skipping {filename} (exists). Use --force to overwrite")
        return out
    try:
        cq.exporters.export(obj, str(out))
        logger.info(f"Exported {filename} (size={out.stat().st_size})")
        return out
    except Exception as e:
        logger.error(f"Failed to export {filename}: {e}")
        raise


def step_base_box(width=WIDTH, depth=DEPTH, height=HEIGHT):
    wp = cq.Workplane('XY').box(width, depth, height)
    return wp


def step_shell(wp, wall=WALL):
    return wp.faces('+Z').shell(wall)


def step_slot(wp, width=WIDTH, depth=DEPTH, height=HEIGHT, slot_width=SLOT_WIDTH, slot_depth_ratio=SLOT_DEPTH_RATIO):
    slot_cut_height = height * slot_depth_ratio
    margin = 5.0
    total_cut_h = slot_cut_height + margin
    cut_center_z = height / 2 - slot_cut_height / 2 + margin / 2

    if depth > width:
        cutter = (
            cq.Workplane("YZ")
            .rect(slot_width, total_cut_h)
            .extrude(-(width + 10))
            .translate((width / 2, 0, cut_center_z))
        )
    else:
        cutter = (
            cq.Workplane("XZ")
            .rect(slot_width, total_cut_h)
            .extrude(-(depth + 10))
            .translate((0, depth / 2, cut_center_z))
        )
    return wp.cut(cutter)


def step_one_lattice(wp, diamond_w=8.0, diamond_h=12.0):
    # place a single diamond cutter at mid-back for quick test
    cutter = (
        cq.Workplane('XZ')
        .polyline([(0, diamond_h/2), (diamond_w/2, 0), (0, -diamond_h/2), (-diamond_w/2, 0)])
        .close()
        .extrude(DEPTH+10)
        .val()
        .moved(cq.Location(cq.Vector(0, DEPTH/2, 0)))
    )
    return wp.cut(cutter)


def run_steps(force: bool = False):
    logger.info('Step 1: base box')
    base = step_base_box()
    try:
        bb = base.val().BoundingBox()
        logger.info(f'Base BB: {bb.xlen:.3f} x {bb.ylen:.3f} x {bb.zlen:.3f}')
    except Exception:
        logger.info('Base bounding box unavailable')
    export_if_needed(base, 'step1_base.stl', force=force)

    logger.info('\nStep 2: shell')
    shelled = step_shell(base)
    try:
        bb = shelled.val().BoundingBox()
        logger.info(f'Shelled BB: {bb.xlen:.3f} x {bb.ylen:.3f} x {bb.zlen:.3f}')
    except Exception:
        logger.info('Shelled bounding box unavailable')
    export_if_needed(shelled, 'step2_shell.stl', force=force)

    logger.info('\nStep 3: slot')
    slotted = step_slot(shelled)
    try:
        bb = slotted.val().BoundingBox()
        logger.info(f'Slotted BB: {bb.xlen:.3f} x {bb.ylen:.3f} x {bb.zlen:.3f}')
    except Exception:
        logger.info('Slotted bounding box unavailable')
    export_if_needed(slotted, 'step3_slot.stl', force=force)

    logger.info('\nStep 4: single lattice cutter (sanity test)')
    lat1 = step_one_lattice(slotted)
    try:
        bb = lat1.val().BoundingBox()
        logger.info(f'Lat1 BB: {bb.xlen:.3f} x {bb.ylen:.3f} x {bb.zlen:.3f}')
    except Exception:
        logger.info('Lat1 bounding box unavailable')
    export_if_needed(lat1, 'step4_lat1.stl', force=force)

    logger.info('\nDone')


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--force', action='store_true', help='Overwrite outputs')
    args = p.parse_args()
    run_steps(force=args.force)
