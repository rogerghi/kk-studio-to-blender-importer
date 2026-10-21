import bpy
import json
import math
import sys
from mathutils import Matrix, Vector, Euler, Quaternion

sys.path.append(r'c:\Users\harri\AppData\Roaming\Blender Foundation\Blender\3.3\scripts\addons')
from kk_studio_scene_importer import KKStudioParser

# Parse scene
p = KKStudioParser(r'K:\KK\UserData\Studio\scene\2021_0614_1058_19_167.png')
char_node = p.parsed_tree[1518]

with open(r'c:\Users\harri\AppData\Roaming\Blender Foundation\Blender\3.3\scripts\addons\extra_files\kk_scene_reader\kk_base_skeleton.json', 'r') as f:
    skeleton = json.load(f)

with open(r'c:\Users\harri\AppData\Roaming\Blender Foundation\Blender\3.3\scripts\addons\extra_files\kk_scene_reader\kk_studio_bone_maps.json', 'r') as f:
    maps = json.load(f)

acc_map = {int(k): v for k, v in maps['accessory_points'].items()}
bone_map = {int(k): v for k, v in maps['bones'].items()}

# Clear scene
bpy.ops.wm.read_factory_settings(use_empty=True)

# 1. Create Armature
arm_data = bpy.data.armatures.new("KK_Character_1518")
arm_obj = bpy.data.objects.new("Character_1518", arm_data)
bpy.context.scene.collection.objects.link(arm_obj)
bpy.context.view_layer.objects.active = arm_obj

# Set character transform
c_pos = char_node["pos"]
c_rot = char_node["rot"]
c_scale = char_node["scale"]

arm_obj.location = Vector((-c_pos[0], c_pos[1], c_pos[2]))
rx = math.radians(c_rot[0])
ry = math.radians(-c_rot[1])
rz = math.radians(-c_rot[2])
arm_obj.rotation_mode = 'ZXY'
arm_obj.rotation_euler = Euler((rx, ry, rz), 'ZXY')
arm_obj.scale = Vector((c_scale[0], c_scale[1], c_scale[2]))

# Compute Unity rest matrices
rest_unity = {}
def get_unity_rest(b_name):
    if b_name in rest_unity:
        return rest_unity[b_name]
    info = skeleton[b_name]
    p_name = info['p']
    t = Vector(info['t'])
    r = Quaternion((info['r'][3], info['r'][0], info['r'][1], info['r'][2]))
    m_local = Matrix.Translation(t) @ r.to_matrix().to_4x4()
    if p_name and p_name in skeleton:
        m_world = get_unity_rest(p_name) @ m_local
    else:
        m_world = m_local
    rest_unity[b_name] = m_world
    return m_world

for b_name in skeleton:
    get_unity_rest(b_name)

bpy.ops.object.mode_set(mode='EDIT')
edit_bones = arm_data.edit_bones
created_eb = {}

for b_name, info in skeleton.items():
    eb = edit_bones.new(b_name)
    m_u = rest_unity[b_name]
    head_pos = Vector((-m_u[0][3], m_u[1][3], m_u[2][3]))
    eb.head = head_pos
    eb.tail = head_pos + Vector((0, 0, 0.02))
    created_eb[b_name] = eb

for b_name, info in skeleton.items():
    p_name = info['p']
    if p_name and p_name in created_eb:
        created_eb[b_name].parent = created_eb[p_name]

bpy.ops.object.mode_set(mode='OBJECT')

# Apply FK Bone Rotations in Pose Mode
bpy.ops.object.mode_set(mode='POSE')
pose_bones = arm_obj.pose.bones

for b_idx, b_info in char_node.get("bones", {}).items():
    b_name = bone_map.get(b_idx)
    if not b_name or b_name not in pose_bones:
        continue
    pb = pose_bones[b_name]
    b_rot = b_info["rot"]
    
    # In Studio: bone rotation
    pb.rotation_mode = 'ZXY'
    pb.rotation_euler = Euler((
        math.radians(b_rot[0]),
        math.radians(-b_rot[1]),
        math.radians(-b_rot[2])
    ), 'ZXY')

bpy.ops.object.mode_set(mode='OBJECT')
bpy.context.view_layer.update()

# Check world position of attach points!
print("=== Attach Point World Positions ===")
for ap_idx in [17, 18, 52, 13]: # nip_L, nip_R, kokan, mouth
    ap_name = acc_map.get(ap_idx)
    if ap_name in pose_bones:
        pb = pose_bones[ap_name]
        w_mat = arm_obj.matrix_world @ pb.matrix
        print(f"AttachPoint {ap_idx} ({ap_name}): world pos = {w_mat.translation}")

# Save debug blend
bpy.ops.wm.save_as_mainfile(filepath=r'C:\Users\harri\.gemini\antigravity-ide\brain\79e9848f-ffbb-4a58-b234-ab13c2cabc72\scratch\test_char_rig.blend')
print("Saved test_char_rig.blend successfully!")
