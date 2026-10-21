import bpy
import json
import math
import sys
import os
from mathutils import Matrix, Vector, Euler, Quaternion

# 1. Clear scene
bpy.ops.wm.read_factory_settings(use_empty=True)

# 2. Setup paths
addon_dir = r'C:\Users\harri\AppData\Roaming\Blender Foundation\Blender\3.3\scripts\addons'
extra_dir = os.path.join(addon_dir, 'extra_files', 'kk_scene_reader')
sys.path.append(addon_dir)

from kk_studio_scene_importer import KKStudioParser, KKItemResolver, KKMeshLoader

scene_path = r'K:\KK\UserData\Studio\scene\2021_0614_1058_19_167.png'
kk_dir = r'K:\KK'

# Load maps
with open(os.path.join(extra_dir, 'kk_base_skeleton.json'), 'r') as f:
    skeleton = json.load(f)

with open(os.path.join(extra_dir, 'kk_studio_bone_maps.json'), 'r') as f:
    maps = json.load(f)

acc_map = {int(k): v for k, v in maps['accessory_points'].items()}
bone_map = {int(k): v for k, v in maps['bones'].items()}
name_to_bone_idx = {v: k for k, v in bone_map.items()}

parser = KKStudioParser(scene_path)
resolver = KKItemResolver.get_resolver(kk_dir)
mesh_loader = KKMeshLoader(resolver)

# Build FK for all character nodes
char_fk = {} # char_key -> {bone_name: (pos, q, scale)}

for dic_key, node in parser.parsed_tree.items():
    if node["kind"] == 0:
        c_pos = Vector(node["pos"])
        c_rot = node["rot"]
        c_q = Euler((math.radians(c_rot[0]), math.radians(c_rot[1]), math.radians(c_rot[2])), 'ZXY').to_quaternion()
        c_scale = Vector(node["scale"])
        char_bones = node.get("bones", {})
        
        bone_world = {}
        def get_bw(b_name):
            if b_name in bone_world:
                return bone_world[b_name]
            info = skeleton[b_name]
            p_name = info['p']
            t = Vector(info['t'])
            q = Quaternion((info['r'][3], info['r'][0], info['r'][1], info['r'][2]))
            s = Vector(info['s'])
            
            b_idx = name_to_bone_idx.get(b_name)
            if b_idx is not None and b_idx in char_bones:
                fk_rot = char_bones[b_idx]["rot"]
                fk_q = Euler((math.radians(fk_rot[0]), math.radians(fk_rot[1]), math.radians(fk_rot[2])), 'ZXY').to_quaternion()
                q = q @ fk_q
            
            if p_name and p_name in skeleton:
                p_pos, p_q, p_scale = get_bw(p_name)
                scaled_offset = Vector((t.x * p_scale.x, t.y * p_scale.y, t.z * p_scale.z))
                w_pos = p_pos + (p_q @ scaled_offset)
                w_q = p_q @ q
                w_scale = Vector((p_scale.x * s.x, p_scale.y * s.y, p_scale.z * s.z))
            else:
                scaled_offset = Vector((t.x * c_scale.x, t.y * c_scale.y, t.z * c_scale.z))
                w_pos = c_pos + (c_q @ scaled_offset)
                w_q = c_q @ q
                w_scale = Vector((c_scale.x * s.x, c_scale.y * s.y, c_scale.z * s.z))
            bone_world[b_name] = (w_pos, w_q, w_scale)
            return bone_world[b_name]
            
        for b_name in skeleton:
            get_bw(b_name)
        char_fk[dic_key] = bone_world

print("Computed FK for", len(char_fk), "characters")

# Calculate Unity World for all nodes
unity_world = {}
eval_order = []
visited = set()
def visit(k):
    if k in visited or k not in parser.parsed_tree: return
    visited.add(k)
    pk = parser.parsed_tree[k].get("parent_key")
    if pk is not None: visit(pk)
    eval_order.append(k)

for k in parser.parsed_tree: visit(k)

for k in eval_order:
    node = parser.parsed_tree[k]
    pos = node.get("pos", (0, 0, 0))
    rot = node.get("rot", (0, 0, 0))
    scale = node.get("scale", (1, 1, 1))

    rx = math.radians(rot[0])
    ry = math.radians(-rot[1])
    rz = math.radians(-rot[2])
    local_q = Euler((rx, ry, rz), 'ZXY').to_quaternion()
    local_pos = Vector((-pos[0], pos[1], pos[2]))
    local_scale = Vector((scale[0], scale[1], scale[2]))

    pk = node.get("parent_key")
    if pk is not None and pk in parser.parsed_tree and parser.parsed_tree[pk]["kind"] == 0:
        # Parent is Character! Check attach point
        ap_idx = node.get("attach_point")
        ap_name = acc_map.get(ap_idx)
        if ap_name and pk in char_fk and ap_name in char_fk[pk]:
            ap_pos, ap_q, ap_scale = char_fk[pk][ap_name]
            # Convert ap_pos and ap_q to Blender-mirrored space
            # ap_pos in Unity: (x, y, z) -> Blender: (-x, y, z)
            # ap_q in Unity: q -> Blender Euler
            # In Unity: world_pos = ap_pos + ap_q * (local_pos_u * ap_scale)
            i_pos_u = Vector(pos)
            scaled_offset_u = Vector((i_pos_u.x * ap_scale.x, i_pos_u.y * ap_scale.y, i_pos_u.z * ap_scale.z))
            w_pos_u = ap_pos + (ap_q @ scaled_offset_u)
            
            i_rot_u = Euler((math.radians(rot[0]), math.radians(rot[1]), math.radians(rot[2])), 'ZXY').to_quaternion()
            w_q_u = ap_q @ i_rot_u
            
            # Now convert to Blender (-x, y, z)
            bl_w_pos = Vector((-w_pos_u.x, w_pos_u.y, w_pos_u.z))
            # Convert rotation:
            bl_e = w_q_u.to_euler('ZXY')
            bl_w_q = Euler((bl_e.x, -bl_e.y, -bl_e.z), 'ZXY').to_quaternion()
            unity_world[k] = (bl_w_pos, bl_w_q, local_scale)
            continue

    if pk is not None and pk in unity_world:
        p_pos, p_q, p_scale = unity_world[pk]
        scaled_offset = Vector((local_pos.x * p_scale.x, local_pos.y * p_scale.y, local_pos.z * p_scale.z))
        w_pos = p_pos + (p_q @ scaled_offset)
        w_q = p_q @ local_q
        w_scale = local_scale
        unity_world[k] = (w_pos, w_q, w_scale)
    else:
        unity_world[k] = (local_pos, local_q, local_scale)

print("Calculated world transforms for", len(unity_world), "nodes.")

# Let's check some attached needles/items
for k, v in parser.parsed_tree.items():
    if v.get("parent_key") == 1518:
        pos, q, sc = unity_world[k]
        name = parser.tree_names.get(k, f"Item_{k}")
        print(f"Attached item {name} ({k}) world pos: {pos}")
        break
