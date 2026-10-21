import bpy, math
from mathutils import Vector, Euler

blend_path = r"c:\Users\harri\AppData\Roaming\Blender Foundation\Blender\3.3\scripts\addons\extra_files\kk_scene_reader\test_pistol.blend"
bpy.ops.wm.open_mainfile(filepath=blend_path)

# Delete existing cameras and lights
for o in list(bpy.data.objects):
    if o.type in ['CAMERA', 'LIGHT']:
        bpy.data.objects.remove(o)

# Card view angle: looking down and slightly from the right-front
# In Unity space:
# Gun forward is +Z
# Gun up is +Y
# Gun right is +X
# So to look from front-left (like the card thumbnail):
# Camera should be in front (+Z), to the right or left, and elevated (+Y)
cam = bpy.data.cameras.new("CardCam")
cam_obj = bpy.data.objects.new("CardCam", cam)
bpy.context.scene.collection.objects.link(cam_obj)
bpy.context.scene.camera = cam_obj

center = Vector((0.076, 0.02, 0.64))
# In the card, the silencer points towards bottom-left of image
cam_obj.location = center + Vector((-0.6, 0.4, 0.8))
dir_vec = center - cam_obj.location
cam_obj.rotation_euler = dir_vec.to_track_quat('-Z', 'Y').to_euler()

# Lights
light = bpy.data.lights.new("Sun", 'SUN')
light.energy = 3.0
light_obj = bpy.data.objects.new("Sun", light)
bpy.context.scene.collection.objects.link(light_obj)
light_obj.rotation_euler = (math.radians(45), math.radians(30), math.radians(60))

out_png = r"c:\Users\harri\AppData\Roaming\Blender Foundation\Blender\3.3\scripts\addons\extra_files\kk_scene_reader\pistol_card_angle.png"
bpy.context.scene.render.filepath = out_png
bpy.context.scene.render.resolution_x = 960
bpy.context.scene.render.resolution_y = 540
bpy.ops.render.render(write_still=True)
print("Rendered to:", out_png)
