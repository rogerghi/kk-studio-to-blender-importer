import json
import math
import sys
from mathutils import Matrix, Vector, Euler, Quaternion

sys.path.append(r'c:\Users\harri\AppData\Roaming\Blender Foundation\Blender\3.3\scripts\addons')
from kk_studio_scene_importer import KKStudioParser

p = KKStudioParser(r'K:\KK\UserData\Studio\scene\2021_0614_1058_19_167.png')
char_node = p.parsed_tree[1518]

with open(r'c:\Users\harri\AppData\Roaming\Blender Foundation\Blender\3.3\scripts\addons\extra_files\kk_scene_reader\kk_base_skeleton.json', 'r') as f:
    skeleton = json.load(f)

with open(r'c:\Users\harri\AppData\Roaming\Blender Foundation\Blender\3.3\scripts\addons\extra_files\kk_scene_reader\kk_studio_bone_maps.json', 'r') as f:
    maps = json.load(f)

acc_map = {int(k): v for k, v in maps['accessory_points'].items()}
bone_map = {int(k): v for k, v in maps['bones'].items()}
name_to_bone_idx = {v: k for k, v in bone_map.items()}

# Character root transform in Unity
c_pos = Vector(char_node["pos"])
c_rot = char_node["rot"]
c_q = Euler((math.radians(c_rot[0]), math.radians(c_rot[1]), math.radians(c_rot[2])), 'ZXY').to_quaternion()
c_scale = Vector(char_node["scale"])

# Character FK bones in scene
char_bones = char_node.get("bones", {})

# Forward Kinematics for all nodes in skeleton
unity_world_bones = {}

def get_bone_unity_world(b_name):
    if b_name in unity_world_bones:
        return unity_world_bones[b_name]
    info = skeleton[b_name]
    p_name = info['p']
    
    # Rest local
    t = Vector(info['t'])
    q = Quaternion((info['r'][3], info['r'][0], info['r'][1], info['r'][2]))
    s = Vector(info['s'])
    
    # Check if FK rotation exists for this bone
    b_idx = name_to_bone_idx.get(b_name)
    if b_idx is not None and b_idx in char_bones:
        fk_rot = char_bones[b_idx]["rot"]
        fk_q = Euler((math.radians(fk_rot[0]), math.radians(fk_rot[1]), math.radians(fk_rot[2])), 'ZXY').to_quaternion()
        q = q @ fk_q # apply FK rotation
    
    if p_name and p_name in skeleton:
        p_pos, p_q, p_scale = get_bone_unity_world(p_name)
        scaled_offset = Vector((t.x * p_scale.x, t.y * p_scale.y, t.z * p_scale.z))
        w_pos = p_pos + (p_q @ scaled_offset)
        w_q = p_q @ q
        w_scale = Vector((p_scale.x * s.x, p_scale.y * s.y, p_scale.z * s.z))
    else:
        # Parented to character root
        scaled_offset = Vector((t.x * c_scale.x, t.y * c_scale.y, t.z * c_scale.z))
        w_pos = c_pos + (c_q @ scaled_offset)
        w_q = c_q @ q
        w_scale = Vector((c_scale.x * s.x, c_scale.y * s.y, c_scale.z * s.z))
        
    unity_world_bones[b_name] = (w_pos, w_q, w_scale)
    return unity_world_bones[b_name]

for b_name in skeleton:
    get_bone_unity_world(b_name)

# Now inspect attached items
attached = [v for v in p.parsed_tree.values() if v.get('parent_key') == 1518]
print(f"Testing {len(attached)} attached items...")

for item in attached[:10]:
    dic_key = item['dic_key']
    name = p.tree_names.get(dic_key, f"Item_{dic_key}")
    ap_idx = item.get('attach_point')
    ap_name = acc_map.get(ap_idx, 'Unknown')
    
    if ap_name in unity_world_bones:
        ap_pos, ap_q, ap_scale = unity_world_bones[ap_name]
        
        # Item local in Unity
        i_pos = Vector(item['pos'])
        i_rot = item['rot']
        i_q = Euler((math.radians(i_rot[0]), math.radians(i_rot[1]), math.radians(i_rot[2])), 'ZXY').to_quaternion()
        
        # Item world in Unity
        scaled_offset = Vector((i_pos.x * ap_scale.x, i_pos.y * ap_scale.y, i_pos.z * ap_scale.z))
        item_w_pos = ap_pos + (ap_q @ scaled_offset)
        
        # Convert to Blender space: (-x, y, z)
        blender_pos = Vector((-item_w_pos.x, item_w_pos.y, item_w_pos.z))
        print(f"[{name}] (Attach: {ap_name}) -> Blender World Pos: {blender_pos}")
