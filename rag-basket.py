import cadquery as cq

# --- Parameters ---
# Units: mm

# 1. Dimensions
width = 100.0   # X-axis dimension
depth = 120.0   # Y-axis dimension
height = 150.0  # Z-axis dimension
wall_thickness = 2.0

# 2. Slot (Front Face +Y)
# The slot should go halfway down from the top edge.
slot_width = 30.0
slot_depth_ratio = 0.5 

# 3. Lattice (Other Faces)
lattice_offset_edge = 10.0 # Margin from the outer edges of the face
diamond_width = 8.0
diamond_height = 12.0
diamond_spacing_x = 4.0 
diamond_spacing_y = 4.0


# --- Create Base Shell ---

# Create a solid box centered at (0,0,0)
# Default box is centered. Z ranges from -height/2 to height/2.
result = cq.Workplane("XY").box(width, depth, height)

# Hollow it out, leaving the top (+Z) open.
# The bottom (-Z) is solid, as requested.
result = result.faces("+Z").shell(wall_thickness)


# --- Create the Slot on Front Face ---

# Front face is in the +Y direction.
# We want a vertical slot starting from the top rim and going down 50%.
# Top Z = height/2. Bottom of slot Z = height/2 - (height * slot_depth_ratio).
# Slot height = height * slot_depth_ratio.
# We cut a rectangle. To ensure the top rim is broken cleanly, we can extend the cut slightly above the top.

slot_cut_height = height * slot_depth_ratio
margin = 5.0 # Cut slightly above top edge
total_cut_h = slot_cut_height + margin

# Center of the cut rect in the Workplane Y-axis (which corresponds to Global Z):
# The cut extends from (height/2 - slot_cut_height) to (height/2 + margin).
# Midpoint = ( (height/2 - slot_cut_height) + (height/2 + margin) ) / 2
#          = height/2 - slot_cut_height/2 + margin/2
cut_center_z = height/2 - slot_cut_height/2 + margin/2

result = (
    result.faces("+Y").workplane()  # Workplane on front face. Local X=Global X, Local Y=Global Z
    .rect(slot_width, total_cut_h)
    .translate((0, cut_center_z))
    .cutThruAll()
)


# --- Create Lattice on Other Sides ---

# Define the diamond shape for cutting
diamond_profile = (
    cq.Workplane("XY")
    .polygon([
        (0, diamond_height / 2),
        (diamond_width / 2, 0),
        (0, -diamond_height / 2),
        (-diamond_width / 2, 0)
    ])
)
# Extrude it to be a cutter
diamond_cutter = diamond_profile.extrude(wall_thickness * 3) # Deep enough to cut wall

def create_lattice_for_face(cad_obj, face_selector):
    """
    Generates a compound of diamond cutters distributed over the selected face.
    Dynamically calculates face dimensions.
    """
    # Select the face
    face_obj = cad_obj.faces(face_selector).val()
    bb = face_obj.BoundingBox()
    
    # Determine width and height of the face
    # Since walls are vertical, Height is Z-length. Width is the horizontal length.
    face_h = bb.zlen
    # Width is either xlen or ylen depending on orientation
    face_w = max(bb.xlen, bb.ylen)
    
    # Calculate usable area for lattice
    usable_w = face_w - 2 * lattice_offset_edge
    usable_h = face_h - 2 * lattice_offset_edge
    
    # Calculate grid counts
    nx = int(usable_w / (diamond_width + diamond_spacing_x))
    ny = int(usable_h / (diamond_height + diamond_spacing_y))
    
    if nx <= 0 or ny <= 0:
        return None

    # Total grid size
    grid_total_w = nx * diamond_width + (nx - 1) * diamond_spacing_x
    grid_total_h = ny * diamond_height + (ny - 1) * diamond_spacing_y
    
    # Generate points centered on the face
    points = []
    for j in range(ny):
        for i in range(nx):
            # Local coordinates relative to grid center
            lx = -grid_total_w/2 + diamond_width/2 + i*(diamond_width+diamond_spacing_x)
            ly = -grid_total_h/2 + diamond_height/2 + j*(diamond_height+diamond_spacing_y)
            points.append((lx, ly))
            
    # Create the cutters
    # We use centerOption="CenterOfMass" so the Workplane origin (0,0) is at the face center
    return (
        cad_obj.faces(face_selector)
        .workplane(centerOption="CenterOfMass")
        .pushPoints(points)
        .eachpoint(lambda loc: diamond_cutter.val().moved(loc), combine=True)
        .combine(clean=True)
    )

# Apply lattice to Back (-Y), Right (+X), Left (-X)
# Front (+Y) has the big slot, so we skip it.
for side in ["-Y", "+X", "-X"]:
    cutters = create_lattice_for_face(result, side)
    if cutters:
        result = result.cut(cutters)


# --- Export ---
output_filename = 'rag_basket.stl'
cq.exporters.export(result, output_filename)
print(f"Generated {output_filename}")

# For CQ-editor interaction (optional)
# show_object(result)
