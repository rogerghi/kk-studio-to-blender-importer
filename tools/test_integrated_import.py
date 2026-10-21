import bpy
import json
import math
import sys
import os
from mathutils import Matrix, Vector, Euler, Quaternion

addon_dir = r'C:\Users\harri\AppData\Roaming\Blender Foundation\Blender\3.3\scripts\addons'
extra_dir = os.path.join(addon_dir, 'extra_files', 'kk_scene_reader')
sys.path.append(addon_dir)

from kk_studio_scene_importer import KKStudioParser, KKItemResolver, KKMeshLoader

# Clear
bpy.ops.wm.read_factory_settings(use_empty=True)

scene_path = r'K:\KK\UserData\Studio\scene\2021_0614_1058_19_167.png'
kk_dir = r'K:\KK'

# Load maps
with open(os.path.join(addon_dir, 'kk_base_skeleton.json'), 'r') as f:
    skeleton = json.load(f)

with open(os.path.join(addon_dir, 'kk_studio_bone_maps.json'), 'r') as f:
    maps = json.load(f)

acc_map = {int(k): v for k, v in maps['accessory_points'].items()}
bone_map = {int(k): v for k, v in maps['bones'].items()}
name_to_bone_idx = {v: k for k, v in bone_map.items()}

parser = KKStudioParser(scene_path)
resolver = KKItemResolver.get_resolver(kk_dir)
mesh_loader = KKMeshLoader(kk_dir)

scene_name = os.path.splitext(os.path.basename(scene_path))[0]
scene_col = bpy.data.collections.new(f"KK_Scene_{scene_name}")
bpy.context.scene.collection.children.link(scene_col)

scene_root = bpy.data.objects.new(f"KK_Root_{scene_name}", None)
scene_root.empty_display_type = 'PLAIN_AXES'
scene_root.empty_display_size = 0.5
scene_root.rotation_euler = (math.radians(90), 0, 0)
scene_col.objects.link(scene_root)

# 1. Forward Kinematics for Characters
char_fk = {}
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

# 2. Compute eval_order and unity_world
def get_eval_order(tree):
    visited = set()
    order = []
    def visit(k):
        if k in visited or k not in tree: return
        visited.add(k)
        pk = tree[k].get("parent_key")
        if pk is not None: visit(pk)
        order.append(k)
    for k in tree: visit(k)
    return order

eval_order = get_eval_order(parser.parsed_tree)

unity_world = {}
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
        ap_idx = node.get("attach_point")
        ap_name = acc_map.get(ap_idx)
        if ap_name and pk in char_fk and ap_name in char_fk[pk]:
            ap_pos, ap_q, ap_scale = char_fk[pk][ap_name]
            i_pos_u = Vector(pos)
            scaled_offset_u = Vector((i_pos_u.x * ap_scale.x, i_pos_u.y * ap_scale.y, i_pos_u.z * ap_scale.z))
            w_pos_u = ap_pos + (ap_q @ scaled_offset_u)
            i_rot_u = Euler((math.radians(rot[0]), math.radians(rot[1]), math.radians(rot[2])), 'ZXY').to_quaternion()
            w_q_u = ap_q @ i_rot_u
            
            bl_w_pos = Vector((-w_pos_u.x, w_pos_u.y, w_pos_u.z))
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

# 3. Create objects
created_objects = {}
folder_cols = {}

def get_or_create_folder_col(f_key):
    if f_key in folder_cols: return folder_cols[f_key]
    f_node = parser.parsed_tree[f_key]
    f_name = parser.tree_names.get(f_key, f_node.get("name", f"Folder_{f_key}"))
    f_col = bpy.data.collections.new(f_name)
    f_parent_key = f_node.get("parent_key")
    if f_parent_key is not None and parser.parsed_tree.get(f_parent_key, {}).get("kind") == 3:
        parent_f_col = get_or_create_folder_col(f_parent_key)
        parent_f_col.children.link(f_col)
    else:
        scene_col.children.link(f_col)
    folder_cols[f_key] = f_col
    return f_col

for dic_key, node in parser.parsed_tree.items():
    if node["kind"] == 3:
        get_or_create_folder_col(dic_key)

def get_target_collection(n_key):
    cur = parser.parsed_tree[n_key].get("parent_key")
    while cur is not None:
        if cur in folder_cols: return folder_cols[cur]
        cur = parser.parsed_tree.get(cur, {}).get("parent_key")
    return scene_col

# Create Character Rigs and Folder / Anchor Empties
for dic_key in eval_order:
    node = parser.parsed_tree[dic_key]
    kind = node["kind"]
    display_name = parser.tree_names.get(dic_key, node.get("name", f"Node_{dic_key}"))
    target_col = folder_cols.get(dic_key) if kind == 3 else get_target_collection(dic_key)

    if kind == 0: # Character Armature
        arm_data = bpy.data.armatures.new(f"{display_name}_Armature")
        arm_obj = bpy.data.objects.new(display_name, arm_data)
        target_col.objects.link(arm_obj)
        bpy.context.view_layer.objects.active = arm_obj
        bpy.ops.object.mode_set(mode='EDIT')

        # Rest Unity matrices
        rest_unity = {}
        def get_unity_rest(b_name):
            if b_name in rest_unity: return rest_unity[b_name]
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

        for b_name in skeleton: get_unity_rest(b_name)

        created_eb = {}
        for b_name in skeleton:
            eb = arm_data.edit_bones.new(b_name)
            m_u = rest_unity[b_name]
            head_pos = Vector((-m_u[0][3], m_u[1][3], m_u[2][3]))
            eb.head = head_pos
            eb.tail = head_pos + Vector((0, 0, 0.02))
            created_eb[b_name] = eb

        for b_name, info in skeleton.items():
            p_name = info['p']
            if p_name and p_name in created_eb:
                created_eb[b_name].parent = created_eb[p_name]

        bpy.ops.object.mode_set(mode='POSE')
        pose_bones = arm_obj.pose.bones
        for b_idx, b_info in node.get("bones", {}).items():
            b_name = bone_map.get(b_idx)
            if b_name and b_name in pose_bones:
                pb = pose_bones[b_name]
                b_rot = b_info["rot"]
                pb.rotation_mode = 'ZXY'
                pb.rotation_euler = Euler((
                    math.radians(b_rot[0]),
                    math.radians(-b_rot[1]),
                    math.radians(-b_rot[2])
                ), 'ZXY')

        bpy.ops.object.mode_set(mode='OBJECT')
        created_objects[dic_key] = arm_obj

    elif kind in [3, 4, 5]:
        empty = bpy.data.objects.new(display_name, None)
        empty.empty_display_type = 'PLAIN_AXES'
        empty.empty_display_size = 0.03
        target_col.objects.link(empty)
        created_objects[dic_key] = empty

# Create Items
item_keys = [k for k, n in parser.parsed_tree.items() if n["kind"] == 1]
single_part_matrices = {}

for item_idx, dic_key in enumerate(item_keys):
    node = parser.parsed_tree[dic_key]
    uar_info = parser.uar_items.get(dic_key)
    uar_guid = uar_info.get("ModID") if uar_info else None
    uar_slot = uar_info.get("Slot") if uar_info else None
    custom_name = parser.tree_names.get(dic_key)
    
    item_def = resolver.resolve(
        node.get("group", 0), node.get("category", 0), node.get("no", 0),
        uar_guid, uar_slot, custom_name
    )
    base_name = custom_name if custom_name else (item_def.get("name") if item_def and item_def.get("name") else f"Item_{dic_key}")
    display_name = base_name if base_name.endswith(f"_{dic_key}") else f"{base_name}_{dic_key}"
    target_col = get_target_collection(dic_key)

    is_vis = node.get("visible", True)
    parts = mesh_loader.get_meshes_and_materials(item_def, node.get("colors", [])) if item_def else []

    if len(parts) == 1:
        part = parts[0]
        obj = bpy.data.objects.new(display_name, part["mesh"])
        if part.get("material"): obj.data.materials.append(part["material"])
        target_col.objects.link(obj)
        created_objects[dic_key] = obj
        if not is_vis: obj.hide_viewport = obj.hide_render = True
        single_part_matrices[dic_key] = part.get("local_matrix", Matrix.Identity(4))
    elif len(parts) > 1:
        parent_obj = bpy.data.objects.new(display_name, None)
        target_col.objects.link(parent_obj)
        created_objects[dic_key] = parent_obj
        if not is_vis: parent_obj.hide_viewport = parent_obj.hide_render = True
        for part in parts:
            sub_name = f"{display_name}_{part['name']}"
            sub_obj = bpy.data.objects.new(sub_name, part["mesh"])
            if part.get("material"): sub_obj.data.materials.append(part["material"])
            target_col.objects.link(sub_obj)
            sub_obj.parent = parent_obj
            sub_obj.matrix_basis = part.get("local_matrix", Matrix.Identity(4))
            if not is_vis: sub_obj.hide_viewport = sub_obj.hide_render = True
    else:
        empty = bpy.data.objects.new(display_name, None)
        target_col.objects.link(empty)
        created_objects[dic_key] = empty
        if not is_vis: empty.hide_viewport = empty.hide_render = True

# Link Hierarchy & Matrices
bpy.context.view_layer.update()
root_mw = scene_root.matrix_world

for dic_key in eval_order:
    obj = created_objects.get(dic_key)
    if not obj: continue
    node = parser.parsed_tree[dic_key]
    parent_key = node.get("parent_key")
    parent_obj = created_objects.get(parent_key) if parent_key is not None else None

    w_pos, w_q, w_scale = unity_world[dic_key]
    T = Matrix.Translation(w_pos)
    R = w_q.to_matrix().to_4x4()
    S = Matrix.Diagonal(Vector((w_scale.x, w_scale.y, w_scale.z, 1.0)))
    unity_mw = T @ R @ S
    if dic_key in single_part_matrices:
        l_mat = single_part_matrices[dic_key]
        if l_mat != Matrix.Identity(4):
            unity_mw = unity_mw @ l_mat
    blender_mw = root_mw @ unity_mw

    if parent_obj and obj != parent_obj:
        obj.parent = parent_obj
        obj.matrix_parent_inverse = parent_obj.matrix_world.inverted()
    else:
        obj.parent = scene_root
        obj.matrix_parent_inverse = scene_root.matrix_world.inverted()
    obj.matrix_world = blender_mw

bpy.context.view_layer.update()

# Setup camera for render
scene = bpy.context.scene
cam_data = bpy.data.cameras.new("RenderCam")
cam_obj = bpy.data.objects.new("RenderCam", cam_data)
scene.collection.objects.link(cam_obj)
bpy.context.scene.camera = cam_obj
cam_obj.location = Vector((2.8, -3.5, 1.8))
direction = Vector((1.0, -1.8, 0.7)) - cam_obj.location
cam_obj.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()

# Save blend file
blend_out = r'C:\Users\harri\.gemini\antigravity-ide\brain\79e9848f-ffbb-4a58-b234-ab13c2cabc72\scratch\scene_armature_test.blend'
bpy.ops.wm.save_as_mainfile(filepath=blend_out)
print("Saved blend file to", blend_out)

# Render Workbench
scene = bpy.context.scene
scene.render.engine = 'BLENDER_WORKBENCH'
scene.display.shading.light = 'STUDIO'
scene.display.shading.color_type = 'MATERIAL'
scene.render.resolution_x = 1280
scene.render.resolution_y = 720
render_out = r'C:\Users\harri\.gemini\antigravity-ide\brain\79e9848f-ffbb-4a58-b234-ab13c2cabc72\scene_armature_verified.png'
scene.render.filepath = render_out
bpy.ops.render.render(write_still=True)
print("Rendered to", render_out)

