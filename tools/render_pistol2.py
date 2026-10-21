import bpy, math
from mathutils import Vector

blend_path = r"c:\Users\harri\AppData\Roaming\Blender Foundation\Blender\3.3\scripts\addons\extra_files\kk_scene_reader\test_pistol.blend"
bpy.ops.wm.open_mainfile(filepath=blend_path)

# Set world background to light gray
world = bpy.context.scene.world
world.use_nodes = True
bg_node = world.node_tree.nodes.get("Background")
if bg_node:
    bg_node.inputs[0].default_value = (0.8, 0.8, 0.8, 1.0)
    bg_node.inputs[1].default_value = 1.0

cam = bpy.data.cameras.new("RenderCam")
cam_obj = bpy.data.objects.new("RenderCam", cam)
bpy.context.scene.collection.objects.link(cam_obj)
bpy.context.scene.camera = cam_obj

# Pistol center is approximately (0.076, 0.02, 0.64)
# Size is 0.19m X, 0.15m Y, 0.38m Z
target = Vector((0.076, 0.02, 0.64))
cam_obj.location = target + Vector((0.4, -0.4, 0.3))

dir_vec = target - cam_obj.location
cam_obj.rotation_euler = dir_vec.to_track_quat('-Z', 'Y').to_euler()

# Sunlight
light = bpy.data.lights.new("Sun", 'SUN')
light.energy = 2.0
light_obj = bpy.data.objects.new("Sun", light)
bpy.context.scene.collection.objects.link(light_obj)
light_obj.rotation_euler = (math.radians(45), math.radians(30), math.radians(60))

out_png = r"c:\Users\harri\AppData\Roaming\Blender Foundation\Blender\3.3\scripts\addons\extra_files\kk_scene_reader\pistol_render2.png"
bpy.context.scene.render.filepath = out_png
bpy.context.scene.render.resolution_x = 1280
bpy.context.scene.render.resolution_y = 720
bpy.ops.render.render(write_still=True)
print("Rendered:", out_png)
