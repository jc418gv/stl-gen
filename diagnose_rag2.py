from pathlib import Path
import cadquery as cq

OUT_DIR = Path(__file__).parent / 'stl-draft'
OUT_DIR.mkdir(exist_ok=True)

width = 100.0
depth = 120.0
height = 150.0
wall = 2.0

def try_export(obj, name):
    path = OUT_DIR / name
    try:
        cq.exporters.export(obj, str(path))
        print(f'Exported {name}: exists={path.exists()} size={path.stat().st_size}')
    except Exception as e:
        print(f'Export {name} failed: {e}')

# Step 1: base box
print('Step 1: base box')
base = cq.Workplane('XY').box(width, depth, height)
try:
    bb = base.val().BoundingBox()
    print('Base BB:', bb.xlen, bb.ylen, bb.zlen)
except Exception as e:
    print('Base BB error:', e)
try_export(base, 'step1_base.stl')

# Step 2: shell
print('\nStep 2: shell')
shelled = base.faces('+Z').shell(wall)
try:
    bb = shelled.val().BoundingBox()
    print('Shelled BB:', bb.xlen, bb.ylen, bb.zlen)
except Exception as e:
    print('Shelled BB error:', e)
try_export(shelled, 'step2_shell.stl')

# Step 3: slot cutter
print('\nStep 3: slot cutter')
slot_cut_height = height * 0.5
margin = 5.0
total_cut_h = slot_cut_height + margin
cut_center_z = height / 2 - slot_cut_height / 2 + margin / 2

cutter = (
    cq.Workplane('XZ')
    .rect(30.0, total_cut_h)
    .extrude(-(depth + 10))
    .translate((0, depth / 2, cut_center_z))
)
slotted = shelled.cut(cutter)
try:
    bb = slotted.val().BoundingBox()
    print('Slotted BB:', bb.xlen, bb.ylen, bb.zlen)
except Exception as e:
    print('Slotted BB error:', e)
try_export(slotted, 'step3_slot.stl')

# Step 4: single lattice cutter at center of back face for test
print('\nStep 4: single lattice cutter on back face')
cutter2 = (
    cq.Workplane('XZ')
    .polyline([(0, 6), (4,0), (0,-6), (-4,0)])
    .close()
    .extrude(depth + 10)
    .val()
    .moved(cq.Location(cq.Vector(0, depth/2, 0)))
)
lat1 = slotted.cut(cutter2)
try:
    bb = lat1.val().BoundingBox()
    print('Lat1 BB:', bb.xlen, bb.ylen, bb.zlen)
except Exception as e:
    print('Lat1 BB error:', e)
try_export(lat1, 'step4_lat1.stl')

print('\nDone')
