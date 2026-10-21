import bpy, math
from mathutils import Vector

# Setup a camera and light to render the pistol
blend_path = r"c:\Users\harri\AppData\Roaming\Blender Foundation\Blender\3.3\scripts\addons\extra_files\kk_scene_reader\test_pistol.blend"
bpy.ops.wm.open_mainfile(filepath=blend_path)

cam = bpy.data.cameras.new("RenderCam")
cam_obj = bpy.data.objects.new("RenderCam", cam)
bpy.context.scene.collection.objects.link(cam_obj)
bpy.context.scene.camera = cam_obj

# Position camera looking at the pistol center (X=0.076, Y=0.02, Z=0.64)
cam_obj.location = Vector((0.5, -0.6, 1.0))
# Point at (0.076, 0.02, 0.64)
direction = Vector((0.076, 0.02, 0.64)) - cam_obj.location
rot_quat = direction.to_track_quat('-Z', 'Y')
cam_obj.rotation_euler = rot_quat.to_euler()

light = bpy.data.lights.new("RenderLight", 'SUN')
light.energy = 3.0
light_obj = bpy.data.objects.new("RenderLight", light)
bpy.context.scene.collection.objects.link(light_obj)
light_obj.rotation_euler = (math.radians(45), math.radians(45), 0)

out_png = r"c:\Users\harri\AppData\Roaming\Blender Foundation\Blender\3.3\scripts\addons\extra_files\kk_scene_reader\pistol_render.png"
bpy.context.scene.render.filepath = out_png
bpy.context.scene.render.resolution_x = 960
bpy.context.scene.render.resolution_y = 540
bpy.ops.render.render(write_still=True)
print(f"Rendered pistol image to: {out_png}")
