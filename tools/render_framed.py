import bpy, math
from mathutils import Vector

blend_path = r"c:\Users\harri\AppData\Roaming\Blender Foundation\Blender\3.3\scripts\addons\extra_files\kk_scene_reader\test_pistol.blend"
bpy.ops.wm.open_mainfile(filepath=blend_path)

# Calculate true world bounding box of all mesh objects
mesh_objs = [o for o in bpy.data.objects if o.type == 'MESH']
coords = []
for o in mesh_objs:
    for c in o.bound_box:
        coords.append(o.matrix_world @ Vector(c))

min_v = Vector((min(c.x for c in coords), min(c.y for c in coords), min(c.z for c in coords)))
max_v = Vector((max(c.x for c in coords), max(c.y for c in coords), max(c.z for c in coords)))
center = (min_v + max_v) * 0.5
size = (max_v - min_v).length

print("Center:", center, "Size:", size)

# Clean up cameras & lights
for o in list(bpy.data.objects):
    if o.type in ['CAMERA', 'LIGHT']:
        bpy.data.objects.remove(o)

# Create Camera
cam = bpy.data.cameras.new("Cam")
cam.clip_start = 0.01
cam.clip_end = 100.0
cam_obj = bpy.data.objects.new("Cam", cam)
bpy.context.scene.collection.objects.link(cam_obj)
bpy.context.scene.camera = cam_obj

# Camera position: offset from center by 1.2 * size
offset = Vector((1.0, -1.0, 0.8)).normalized() * (size * 1.5)
cam_obj.location = center + offset
dir_vec = center - cam_obj.location
cam_obj.rotation_euler = dir_vec.to_track_quat('-Z', 'Y').to_euler()

# Sun light
sun = bpy.data.lights.new("Sun", 'SUN')
sun.energy = 5.0
sun_obj = bpy.data.objects.new("Sun", sun)
bpy.context.scene.collection.objects.link(sun_obj)
sun_obj.location = center + Vector((2, -2, 5))
sun_obj.rotation_euler = (center - sun_obj.location).to_track_quat('-Z', 'Y').to_euler()

# Solid dark clay material for visibility
mat = bpy.data.materials.new("Clay")
mat.use_nodes = True
bsdf = mat.node_tree.nodes.get("Principled BSDF")
if bsdf:
    bsdf.inputs["Base Color"].default_value = (0.2, 0.2, 0.22, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.5

for o in mesh_objs:
    o.data.materials.clear()
    o.data.materials.append(mat)

# World background
bpy.context.scene.world.use_nodes = True
bg = bpy.context.scene.world.node_tree.nodes.get("Background")
if bg:
    bg.inputs[0].default_value = (0.9, 0.9, 0.9, 1.0)
    bg.inputs[1].default_value = 1.0

out_png = r"c:\Users\harri\AppData\Roaming\Blender Foundation\Blender\3.3\scripts\addons\extra_files\kk_scene_reader\pistol_framed.png"
bpy.context.scene.render.filepath = out_png
bpy.context.scene.render.resolution_x = 960
bpy.context.scene.render.resolution_y = 540
bpy.ops.render.render(write_still=True)
print("Rendered successfully to:", out_png)
