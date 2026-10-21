import bpy
import json
import math
from mathutils import Matrix, Vector, Euler, Quaternion

# Load skeleton and maps
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
bpy.ops.object.mode_set(mode='EDIT')

# Compute rest matrices in Unity space -> convert to Blender space
# In Unity: x is right, y is up, z is forward
# Blender: x is right, y is forward, z is up (or match our scene conversion)
# In our scene importer:
# local_q = Euler((rx, -ry, -rz), 'ZXY').to_quaternion()
# local_pos = Vector((-pos[0], pos[1], pos[2]))

# Let's compute world rest matrix for each node in Unity space first
rest_unity = {}
def get_unity_rest(b_name):
    if b_name in rest_unity:
        return rest_unity[b_name]
    info = skeleton[b_name]
    p_name = info['p']
    t = Vector(info['t'])
    # Unity quaternion (x, y, z, w)
    r = Quaternion((info['r'][3], info['r'][0], info['r'][1], info['r'][2]))
    s = Vector(info['s'])
    
    # local matrix
    m_local = Matrix.Translation(t) @ r.to_matrix().to_4x4()
    
    if p_name and p_name in skeleton:
        p_mat = get_unity_rest(p_name)
        m_world = p_mat @ m_local
    else:
        m_world = m_local
    rest_unity[b_name] = m_world
    return m_world

for b_name in skeleton:
    get_unity_rest(b_name)

# Coordinate conversion matrix: Unity -> Blender
# Unity: (X, Y, Z) -> Blender: (-X, Z, Y) or (-X, Y, Z)?
# Notice in kk_studio_scene_importer:
# local_pos = Vector((-pos[0], pos[1], pos[2]))
# and rx = rot[0], ry = -rot[1], rz = -rot[2], Euler order 'ZXY'
# In Blender, our world is (-x, y, z)
# Let's check:
unity_to_blender = Matrix((
    [-1, 0, 0, 0],
    [ 0, 0, 1, 0],
    [ 0, 1, 0, 0],
    [ 0, 0, 0, 1]
))

# Create edit bones
edit_bones = arm_data.edit_bones
created_eb = {}

for b_name, info in skeleton.items():
    eb = edit_bones.new(b_name)
    m_u = rest_unity[b_name]
    # Position in Blender space: (-x, y, z)
    head_pos = Vector((-m_u[0][3], m_u[1][3], m_u[2][3]))
    eb.head = head_pos
    eb.tail = head_pos + Vector((0, 0, 0.02)) # small stub
    created_eb[b_name] = eb

# Parent edit bones
for b_name, info in skeleton.items():
    p_name = info['p']
    if p_name and p_name in created_eb:
        created_eb[b_name].parent = created_eb[p_name]

bpy.ops.object.mode_set(mode='OBJECT')
print("Armature built with", len(arm_obj.pose.bones), "bones")
