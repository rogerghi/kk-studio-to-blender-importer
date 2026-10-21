import bpy
import json
import math
import sys
import os
from mathutils import Matrix, Vector, Euler, Quaternion

# Let's import the full scene using kk_studio_scene_importer but with our FK attach resolver plugged in!
sys.path.append(r'c:\Users\harri\AppData\Roaming\Blender Foundation\Blender\3.3\scripts\addons')
import kk_studio_scene_importer
from kk_studio_scene_importer import KKStudioParser, KKItemResolver, KKMeshLoader

# Clear
bpy.ops.wm.read_factory_settings(use_empty=True)

scene_path = r'K:\KK\UserData\Studio\scene\2021_0614_1058_19_167.png'
kk_dir = r'K:\KK'

# Run full import with import_attached_props = True
# But first let's see how kk_studio_scene_importer currently does it
# In kk_studio_scene_importer:
# props.kk_dir = kk_dir
# props.scene_path = scene_path
# props.import_attached_props = True
bpy.context.scene.kk_studio_props.kk_dir = kk_dir
bpy.context.scene.kk_studio_props.scene_path = scene_path
bpy.context.scene.kk_studio_props.import_attached_props = True

print("Ready to integrate into importer.")
