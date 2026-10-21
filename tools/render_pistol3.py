import bpy, math
from mathutils import Vector

blend_path = r"c:\Users\harri\AppData\Roaming\Blender Foundation\Blender\3.3\scripts\addons\extra_files\kk_scene_reader\test_pistol.blend"
bpy.ops.wm.open_mainfile(filepath=blend_path)

world = bpy.context.scene.world
world.use_nodes = True
bg_node = world.node_tree.nodes.get("Background")
if bg_node:
    bg_node.inputs[0].default_value = (0.1, 0.1, 0.1, 1.0)
    bg_node.inputs[1].default_value = 1.0

# Add material to all meshes so they are solid gray
mat = bpy.data.materials.new("Clay")
mat.use_nodes = True
bsdf = mat.node_tree.nodes.get("Principled BSDF")
if bsdf:
    bsdf.inputs["Base Color"].default_value = (0.7, 0.7, 0.7, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.4

for obj in bpy.data.objects:
    if obj.type == 'MESH':
        obj.data.materials.clear()
        obj.data.materials.append(mat)

cam = bpy.data.cameras.new("RenderCam")
cam_obj = bpy.data.objects.new("RenderCam", cam)
bpy.context.scene.collection.objects.link(cam_obj)
bpy.context.scene.camera = cam_obj

# In Unity coordinates:
# X is side (0.076)
# Y is up (0.02)
# Z is forward (0.64)
# Let's place camera to side-view of pistol:
# Looking from +X towards -X, slightly elevated in Y, centered on Z
cam_obj.location = Vector((0.6, 0.05, 0.64))
dir_vec = Vector((0.076, 0.02, 0.64)) - cam_obj.location
cam_obj.rotation_euler = dir_vec.to_track_quat('-Z', 'Y').to_euler()

light = bpy.data.lights.new("Sun", 'SUN')
light.energy = 4.0
light_obj = bpy.data.objects.new("Sun", light)
bpy.context.scene.collection.objects.link(light_obj)
light_obj.rotation_euler = (math.radians(30), math.radians(45), math.radians(10))

out_png = r"c:\Users\harri\AppData\Roaming\Blender Foundation\Blender\3.3\scripts\addons\extra_files\kk_scene_reader\pistol_render3.png"
bpy.context.scene.render.filepath = out_png
bpy.context.scene.render.resolution_x = 1280
bpy.context.scene.render.resolution_y = 720
bpy.ops.render.render(write_still=True)
print("Rendered:", out_png)
