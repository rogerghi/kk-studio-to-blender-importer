bl_info = {
    "name": "Koikatsu Studio Scene Importer",
    "author": "rinasaurus",
    "version": (1, 5, 1),
    "blender": (3, 0, 0),
    "location": "3D Viewport > Sidebar (N) > KK Studio",
    "description": "Imports Koikatsu Studio scene cards into Blender with character pose armatures, preserving exact hierarchy, transforms, multi-part meshes, and tinted textures for COM3D2 export.",
    "category": "Import-Export",
}

import site, sys, os
sys.path.append(site.getusersitepackages())

import bpy
import struct
import io
import math
import time
from mathutils import Matrix, Vector, Quaternion, Euler
from bpy.props import StringProperty, BoolProperty

try:
    import msgpack
    import UnityPy
    from PIL import Image
    DEPS_LOADED = True
except ImportError:
    DEPS_LOADED = False

# =========================================================================
# Modular Imports
# =========================================================================

try:
    from .parser import KKStudioParser
    from .resolver import KKItemResolver
    from .mesh_loader import KKMeshLoader
    from .retarget import (
        KK_TO_COM_BONES,
        KK_PRIMARY_BONE_CHAIN,
        load_base_skeleton_data,
        build_char_skeleton,
        find_com_append_blend,
        append_com_body,
        setup_kk_to_com_transfer,
        KK_OT_TransferToCOM,
    )
    from .com_tools import (
        KK_OT_CleanOccludedGeometry,
        KK_OT_MergeSelectedProps,
    )
except ImportError:
    from parser import KKStudioParser
    from resolver import KKItemResolver
    from mesh_loader import KKMeshLoader
    from retarget import (
        KK_TO_COM_BONES,
        KK_PRIMARY_BONE_CHAIN,
        load_base_skeleton_data,
        build_char_skeleton,
        find_com_append_blend,
        append_com_body,
        setup_kk_to_com_transfer,
        KK_OT_TransferToCOM,
    )
    from com_tools import (
        KK_OT_CleanOccludedGeometry,
        KK_OT_MergeSelectedProps,
    )


# =========================================================================
# 1. Coordinate & Transform Conversion (Unity -> Blender)
# =========================================================================

def unity_trs_matrix(pos: tuple, rot_deg: tuple, scale: tuple) -> Matrix:
    """Computes exact Unity local TRS affine transformation matrix in right-handed space (X-mirrored)."""
    rx = math.radians(rot_deg[0])
    ry = math.radians(-rot_deg[1])
    rz = math.radians(-rot_deg[2])
    # Intrinsic ZXY rotation order in reflected space
    q = Euler((rx, ry, rz), 'ZXY').to_quaternion()
    
    T = Matrix.Translation(Vector((-pos[0], pos[1], pos[2])))
    R = q.to_matrix().to_4x4()
    S = Matrix.Diagonal(Vector((scale[0], scale[1], scale[2], 1.0)))
    return T @ R @ S


# =========================================================================
# 2. Blender Operators & UI
# =========================================================================

class KK_OT_ReindexDatabase(bpy.types.Operator):
    bl_idname = "kk_studio.reindex_database"
    bl_label = "Re-index Mods & Bundles"
    bl_description = "Force re-scan all Koikatsu asset bundles and zipmod files to update cache"
    bl_options = {'REGISTER'}

    def execute(self, context):
        props = context.scene.kk_studio_props
        kk_dir = props.kk_dir
        if not os.path.isdir(kk_dir):
            self.report({'ERROR'}, f"Directory not found: {kk_dir}")
            return {'CANCELLED'}

        win = getattr(context, "window", None)
        if win:
            win.cursor_modal_set('WAIT')
        try:
            resolver = KKItemResolver.get_resolver(kk_dir)
            resolver.index_all(force=True)
            count = len(resolver.item_index) + len(resolver.zipmod_items)
            self.report({'INFO'}, f"Re-indexed {count} items successfully!")
        finally:
            if win:
                win.cursor_modal_restore()
        return {'FINISHED'}


class KK_OT_ImportScene(bpy.types.Operator):
    bl_idname = "kk_studio.import_scene"
    bl_label = "Import KK Studio Scene"
    bl_description = "Import Koikatsu Studio Scene into Blender"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        if not DEPS_LOADED:
            self.report({'ERROR'}, "UnityPy, msgpack, and Pillow are required.")
            return {'CANCELLED'}

        props = context.scene.kk_studio_props
        kk_dir = props.kk_dir
        scene_path = props.scene_path

        if not os.path.exists(kk_dir):
            self.report({'ERROR'}, f"Koikatsu directory not found: {kk_dir}")
            return {'CANCELLED'}
        if not os.path.exists(scene_path):
            self.report({'ERROR'}, f"Scene PNG not found: {scene_path}")
            return {'CANCELLED'}

        start_time = time.time()
        wm = context.window_manager
        win = getattr(context, "window", None)
        if win:
            win.cursor_modal_set('WAIT')

        try:
            # 1. Resolve / Index Database (Instant if cached)
            resolver = KKItemResolver.get_resolver(kk_dir)
            resolver.index_all()

            mesh_loader = KKMeshLoader(kk_dir, use_fallback_cubes=props.use_fallback_cubes)
            parser = KKStudioParser(scene_path)

            children_map = {}
            for k, n in parser.parsed_tree.items():
                pk = n.get("parent_key")
                if pk is not None:
                    children_map.setdefault(pk, []).append(k)

            if not props.import_attached_props:
                char_keys = {k for k, v in parser.parsed_tree.items() if v.get("kind") == 0}
                def is_descendant_of_char(k):
                    cur = parser.parsed_tree[k].get("parent_key")
                    while cur is not None:
                        if cur in char_keys:
                            return True
                        cur = parser.parsed_tree.get(cur, {}).get("parent_key")
                    return False

                attached_keys = [k for k in parser.parsed_tree if is_descendant_of_char(k)]
                for k in attached_keys:
                    parser.parsed_tree.pop(k, None)
                    parser.tree_names.pop(k, None)

            scene_name = os.path.splitext(os.path.basename(scene_path))[0]
            scene_col = bpy.data.collections.new(f"KK_Scene_{scene_name}")
            bpy.context.scene.collection.children.link(scene_col)

            scene_root = bpy.data.objects.new(f"KK_Root_{scene_name}", None)
            scene_root.empty_display_type = 'PLAIN_AXES'
            scene_root.empty_display_size = 0.5
            # Rotate +90 degrees on X to convert Unity Y-up to Blender Z-up
            scene_root.rotation_euler = (math.radians(90), 0, 0)
            scene_col.objects.link(scene_root)

            total_nodes = len(parser.parsed_tree)
            wm.progress_begin(0, total_nodes)

            created_objects = {}
            current_progress = 0

            # 2. First Pass: Create Nested Folder Collections & Empty Anchors
            folder_cols = {} # dic_key -> Collection

            def get_or_create_folder_col(f_key):
                if f_key in folder_cols:
                    return folder_cols[f_key]
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
                if node["kind"] == 3: # Folder
                    get_or_create_folder_col(dic_key)

            def get_target_collection(n_key):
                cur = parser.parsed_tree[n_key].get("parent_key")
                while cur is not None:
                    if cur in folder_cols:
                        return folder_cols[cur]
                    cur = parser.parsed_tree.get(cur, {}).get("parent_key")
                return scene_col

            def is_node_effectively_visible(n_key):
                cur = n_key
                while cur is not None and cur in parser.parsed_tree:
                    n = parser.parsed_tree[cur]
                    if not n.get("visible", True):
                        return False
                    cur = n.get("parent_key")
                return True

            def get_eval_order(tree):
                visited = set()
                order = []
                def visit(k):
                    if k in visited:
                        return
                    visited.add(k)
                    pk = tree[k].get("parent_key")
                    if pk is not None and pk in tree:
                        visit(pk)
                    order.append(k)
                for k in tree:
                    visit(k)
                return order

            eval_order = get_eval_order(parser.parsed_tree)

            # Compute Forward Kinematics for Characters if skeleton data is available
            skeleton, acc_map, bone_map = load_base_skeleton_data()
            name_to_bone_idx = {v: k for k, v in bone_map.items()} if bone_map else {}
            C_flip = Matrix.Diagonal(Vector((-1.0, 1.0, 1.0, 1.0)))

            char_posed_u = {}
            char_skeletons = {}
            if skeleton:
                for dic_key, node in parser.parsed_tree.items():
                    if node.get("kind") == 0:
                        char_sk = build_char_skeleton(skeleton, node, simplify=props.simplify_armature_bones, acc_map=acc_map)
                        char_skeletons[dic_key] = char_sk
                        char_bones = node.get("bones", {})
                        r_hand_active = (
                            char_bones.get(22, {}).get("rot", (0.0, 0.0, 0.0)) != (0.0, 0.0, 0.0)
                            or char_bones.get(25, {}).get("rot", (0.0, 0.0, 0.0)) != (0.0, 0.0, 0.0)
                        )
                        l_hand_active = (
                            char_bones.get(37, {}).get("rot", (0.0, 0.0, 0.0)) != (0.0, 0.0, 0.0)
                            or char_bones.get(40, {}).get("rot", (0.0, 0.0, 0.0)) != (0.0, 0.0, 0.0)
                        )
                        p_u = {}
                        def get_p_u(b):
                            if b in p_u: return p_u[b]
                            info = char_sk[b]
                            p = info['p']
                            t = Vector(info['t'])
                            r = Quaternion((info['r'][3], info['r'][0], info['r'][1], info['r'][2]))
                            s = Vector(info.get('s', [1.0, 1.0, 1.0]))
                            b_idx = name_to_bone_idx.get(b)
                            if b_idx is not None and b_idx in char_bones:
                                skip_fk = (22 <= b_idx <= 36 and not r_hand_active) or (37 <= b_idx <= 51 and not l_hand_active)
                                if not skip_fk:
                                    b_data = char_bones[b_idx]
                                    rot = b_data["rot"]
                                    q_fk = Euler((math.radians(rot[0]), math.radians(rot[1]), math.radians(rot[2])), 'ZXY').to_quaternion()
                                    r = q_fk
                                    t = t + Vector(b_data.get("pos", (0.0, 0.0, 0.0)))
                                    b_s = b_data.get("scale", (1.0, 1.0, 1.0))
                                    s = Vector((s.x * b_s[0], s.y * b_s[1], s.z * b_s[2]))
                            abm_rot = info.get("abm_rot")
                            if abm_rot:
                                q_abm = Euler((math.radians(abm_rot[0]), math.radians(abm_rot[1]), math.radians(abm_rot[2])), 'ZXY').to_quaternion()
                                r = r @ q_abm
                            S_mat = Matrix.Diagonal(Vector((s.x, s.y, s.z, 1.0)))
                            m = Matrix.Translation(t) @ r.to_matrix().to_4x4() @ S_mat
                            if p and p in char_sk: m = get_p_u(p) @ m
                            p_u[b] = m
                            return m
                        for b in char_sk: get_p_u(b)
                        char_posed_u[dic_key] = p_u

            # Compute absolute Unity world transforms (canceling scale inheritance to match KK Studio LateUpdate)
            # and track character bone attachments
            unity_world = {}
            char_attachments = {} # dic_key -> (char_key, attach_bone_name, m_in_char_u)

            for k in eval_order:
                node = parser.parsed_tree[k]
                pos = node["pos"]
                rot = node["rot"]
                scale = node["scale"]
                pk = node.get("parent_key")

                # Direct character bone attachment
                if pk is not None and pk in parser.parsed_tree and parser.parsed_tree[pk].get("kind") == 0:
                    ap_idx = node.get("attach_point")
                    ap_name = acc_map.get(ap_idx) if acc_map else None
                    if ap_name and pk in char_posed_u and ap_name in char_posed_u[pk]:
                        m_bone_u = char_posed_u[pk][ap_name]
                        t_u = Vector(pos)
                        r_u = Euler((math.radians(rot[0]), math.radians(rot[1]), math.radians(rot[2])), 'ZXY').to_matrix().to_4x4()
                        s_u = Matrix.Diagonal(Vector((scale[0], scale[1], scale[2], 1.0)))
                        m_local_u = Matrix.Translation(t_u) @ r_u @ s_u
                        m_in_char_u = m_bone_u @ m_local_u
                        char_attachments[k] = (pk, ap_name, m_in_char_u)
                        continue

                # Indirect character attachment (descendant of an attached prop)
                if pk is not None and pk in char_attachments:
                    char_key, _, parent_m_in_char_u = char_attachments[pk]
                    t_u = Vector(pos)
                    r_u = Euler((math.radians(rot[0]), math.radians(rot[1]), math.radians(rot[2])), 'ZXY').to_matrix().to_4x4()
                    s_u = Matrix.Diagonal(Vector((scale[0], scale[1], scale[2], 1.0)))
                    m_local_u = Matrix.Translation(t_u) @ r_u @ s_u
                    m_in_char_u = parent_m_in_char_u @ m_local_u
                    char_attachments[k] = (char_key, None, m_in_char_u)
                    continue

                # Normal scene object / room hierarchy
                rx = math.radians(rot[0])
                ry = math.radians(-rot[1])
                rz = math.radians(-rot[2])
                local_q = Euler((rx, ry, rz), 'ZXY').to_quaternion()
                local_pos = Vector((-pos[0], pos[1], pos[2]))
                local_scale = Vector((scale[0], scale[1], scale[2]))

                if pk is not None and pk in unity_world:
                    p_pos, p_q, p_scale = unity_world[pk]
                    scaled_offset = Vector((local_pos.x * p_scale.x, local_pos.y * p_scale.y, local_pos.z * p_scale.z))
                    w_pos = p_pos + (p_q @ scaled_offset)
                    w_q = p_q @ local_q
                    w_scale = local_scale
                    unity_world[k] = (w_pos, w_q, w_scale)
                else:
                    unity_world[k] = (local_pos, local_q, local_scale)

            single_part_matrices = {}
            pending_com_transfers = []

            for dic_key in eval_order:
                node = parser.parsed_tree[dic_key]
                current_progress += 1
                wm.progress_update(current_progress)

                kind = node["kind"]
                if kind in [3, 0, 4, 5]: # Folder, Character, Route, Camera
                    if not props.import_attached_props and dic_key in char_attachments:
                        continue

                    display_name = parser.tree_names.get(dic_key, node.get("name", f"Node_{dic_key}"))
                    target_col = folder_cols.get(dic_key) if kind == 3 else get_target_collection(dic_key)

                    if kind == 0 and skeleton and props.import_character_pose:
                        char_sk = char_skeletons.get(dic_key) or build_char_skeleton(skeleton, node, simplify=props.simplify_armature_bones, acc_map=acc_map)
                        arm_data = bpy.data.armatures.new(f"{display_name}_Armature")
                        arm_data.display_type = 'OCTAHEDRAL'
                        arm_obj = bpy.data.objects.new(display_name, arm_data)
                        arm_obj.show_in_front = True
                        target_col.objects.link(arm_obj)
                        context.view_layer.objects.active = arm_obj

                        # Compute rest matrices in character local space (with character height/body sliders and ABMX bone scales/lengths)
                        rest_u = {}
                        def get_rest_u(b):
                            if b in rest_u: return rest_u[b]
                            info = char_sk[b]
                            p = info['p']
                            t = Vector(info['t'])
                            r = Quaternion((info['r'][3], info['r'][0], info['r'][1], info['r'][2]))
                            s = Vector(info.get('s', [1.0, 1.0, 1.0]))
                            S_mat = Matrix.Diagonal(Vector((s.x, s.y, s.z, 1.0)))
                            m = Matrix.Translation(t) @ r.to_matrix().to_4x4() @ S_mat
                            if p and p in char_sk: m = get_rest_u(p) @ m
                            rest_u[b] = m
                            return m
                        for b in char_sk: get_rest_u(b)

                        posed_u = char_posed_u.get(dic_key, {})

                        rest_bl = {b: C_flip @ rest_u[b] @ C_flip for b in char_sk}
                        posed_bl = {b: C_flip @ posed_u[b] @ C_flip for b in char_sk}

                        # Compute pure world rotation delta for each bone from rest pose to posed pose
                        delta_R_bl = {}
                        for b in char_sk:
                            R_delta_u = posed_u[b].to_quaternion().to_matrix() @ rest_u[b].to_quaternion().to_matrix().inverted()
                            delta_R_bl[b] = C_flip.to_3x3() @ R_delta_u @ C_flip.to_3x3()

                        bpy.ops.object.mode_set(mode='EDIT')
                        eb_map = {}
                        for b_name in char_sk:
                            eb = arm_data.edit_bones.new(b_name)
                            m_bl = rest_bl[b_name]
                            eb.head = m_bl.translation
                            eb.tail = m_bl.translation + Vector((0, 0, 0.05))
                            eb_map[b_name] = eb

                        for b_name, info in char_sk.items():
                            p_name = info['p']
                            if p_name and p_name in eb_map:
                                eb_map[b_name].parent = eb_map[p_name]

                        for b_name in char_sk:
                            eb = eb_map[b_name]
                            if b_name in ['cf_j_root', 'cf_n_height']:
                                eb.tail = eb.head + Vector((0.0, 0.0, 0.1))
                                continue
                            if b_name in KK_PRIMARY_BONE_CHAIN and KK_PRIMARY_BONE_CHAIN[b_name] in eb_map:
                                target = eb_map[KK_PRIMARY_BONE_CHAIN[b_name]]
                                if (target.head - eb.head).length > 0.01:
                                    eb.tail = target.head
                                    continue
                            children = eb.children
                            if len(children) == 1:
                                if (children[0].head - eb.head).length > 0.01:
                                    eb.tail = children[0].head
                            elif len(children) > 1:
                                best = None
                                for c in children:
                                    if c.name.startswith('cf_j_'):
                                        best = c
                                        break
                                if not best:
                                    for c in children:
                                        if any(k in c.name for k in ['spine', 'neck', 'head', 'arm', 'forearm', 'hand', 'thigh', 'leg', 'foot']):
                                            best = c
                                            break
                                if not best: best = children[0]
                                if (best.head - eb.head).length > 0.01:
                                    eb.tail = best.head
                            else:
                                if eb.parent:
                                    d = (eb.head - eb.parent.head).normalized()
                                    if d.length > 0.1: eb.tail = eb.head + d * 0.05

                        bpy.ops.object.mode_set(mode='POSE')
                        E_rest = {b: arm_data.bones[b].matrix_local for b in char_sk}

                        P_target = {}
                        for b in char_sk:
                            E_b = E_rest[b]
                            R_b = (delta_R_bl[b] @ E_b.to_3x3()).to_4x4()
                            R_b.translation = posed_bl[b].translation
                            P_target[b] = R_b

                        def get_bone_order():
                            vis, ord = set(), []
                            def v(b):
                                if b in vis or b not in char_sk: return
                                vis.add(b)
                                p = char_sk[b]['p']
                                if p and p in char_sk: v(p)
                                ord.append(b)
                            for b in char_sk: v(b)
                            return ord

                        bone_eval_order = get_bone_order()
                        pose_bones = arm_obj.pose.bones

                        for b in bone_eval_order:
                            pb = pose_bones.get(b)
                            if not pb: continue
                            info = char_sk[b]
                            p = info['p']
                            if p and p in char_sk and p in pose_bones:
                                E_b = E_rest[b]
                                E_p = E_rest[p]
                                P_b = P_target[b]
                                P_p = P_target[p]
                                M_basis = E_b.inverted() @ E_p @ P_p.inverted() @ P_b
                            else:
                                E_b = E_rest[b]
                                P_b = P_target[b]
                                M_basis = E_b.inverted() @ P_b

                            pb.rotation_mode = 'QUATERNION'
                            loc, rot, sca = M_basis.decompose()
                            pb.location = loc
                            pb.rotation_quaternion = rot
                            pb.scale = sca

                        bpy.ops.object.mode_set(mode='OBJECT')
                        created_objects[dic_key] = arm_obj

                        if props.transfer_to_com_body:
                            pending_com_transfers.append((arm_obj, target_col))
                    else:
                        empty = bpy.data.objects.new(display_name, None)
                        if kind == 3:
                            empty.empty_display_type = 'PLAIN_AXES'
                            empty.empty_display_size = 0.03 # subtle, clean anchor
                        else:
                            empty.empty_display_type = 'PLAIN_AXES'
                            empty.empty_display_size = 0.1
                        target_col.objects.link(empty)
                        created_objects[dic_key] = empty

                    is_vis = is_node_effectively_visible(dic_key)
                    # Don't hide character armatures if user requested character poses
                    if not is_vis and kind != 0:
                        created_objects[dic_key].hide_viewport = True
                        created_objects[dic_key].hide_render = True

            # 3. Second Pass: Create Props & Multi-Part Meshes
            item_keys = [k for k, n in parser.parsed_tree.items() if n["kind"] == 1]
            total_items = len(item_keys)

            unique_prop_configs = set()
            for k in item_keys:
                node = parser.parsed_tree[k]
                uar = parser.uar_items.get(k)
                mod_id = uar.get("ModID") if uar else None
                slot = uar.get("Slot") if uar else None
                c_tuple = tuple(node.get("colors", []))
                unique_prop_configs.add((node.get("group", 0), node.get("category", 0), node.get("no", 0), mod_id, slot, c_tuple))
            print(f"[KK Importer] Pre-scan: {total_items} scene props map to {len(unique_prop_configs)} unique prefab/color definitions.")

            for item_idx, dic_key in enumerate(item_keys):
                if not props.import_attached_props and dic_key in char_attachments:
                    continue
                node = parser.parsed_tree[dic_key]
                current_progress += 1
                wm.progress_update(current_progress)

                uar_info = parser.uar_items.get(dic_key)
                uar_guid = uar_info.get("ModID") if uar_info else None
                uar_slot = uar_info.get("Slot") if uar_info else None

                custom_name = parser.tree_names.get(dic_key)
                item_def = resolver.resolve(
                    node.get("group", 0), node.get("category", 0), node.get("no", 0),
                    uar_guid, uar_slot, custom_name
                )

                # Determine actual object name prioritizing KK Prefab name, keeping _[dic_key]
                if item_def and item_def.get("prefab"):
                    base_name = item_def["prefab"]
                elif custom_name:
                    base_name = custom_name
                elif item_def and item_def.get("name"):
                    base_name = item_def["name"]
                else:
                    base_name = "Item"

                if base_name.endswith(f"_{dic_key}"):
                    display_name = base_name
                else:
                    display_name = f"{base_name}_{dic_key}"

                if item_idx % 50 == 0 or item_idx == total_items - 1:
                    print(f"[KK Importer] ({item_idx + 1}/{total_items}) Loading: {display_name}")

                parts = []
                if item_def:
                    parts = mesh_loader.get_meshes_and_materials(item_def, node.get("colors"))

                is_dummy_node = "obj無し" in display_name or "objなし" in display_name or "（obj無し）" in display_name or "回転音" in display_name or "Without Object" in display_name
                has_children = dic_key in children_map and len(children_map[dic_key]) > 0

                if not parts:
                    if props.use_fallback_cubes and props.import_meshless and not is_dummy_node:
                        fallback_mesh = mesh_loader.create_fallback_cube(display_name)
                        parts = [{"name": display_name, "mesh": fallback_mesh, "material": None}]
                    elif not props.import_meshless and not has_children:
                        # Skip leaf meshless objects that have no 3D geometry
                        continue

                target_col = get_target_collection(dic_key)
                is_vis = is_node_effectively_visible(dic_key)

                def setup_skinned_part(part, part_display_name, target_col, is_vis, node_bones):
                    arm_info = part["armature_data"]
                    arm_data = bpy.data.armatures.new(f"{part_display_name}_Armature")
                    arm_obj = bpy.data.objects.new(f"{part_display_name}_Armature", arm_data)
                    scene_col.objects.link(arm_obj)

                    if context.view_layer.objects.active and context.view_layer.objects.active.mode != 'OBJECT':
                        bpy.ops.object.mode_set(mode='OBJECT')

                    context.view_layer.objects.active = arm_obj
                    arm_obj.select_set(True)
                    bpy.ops.object.mode_set(mode='EDIT')

                    bnames = arm_info["bone_names"]
                    bposes = arm_info["bind_poses"]
                    pmap = arm_info["parent_map"]

                    head_positions = {}
                    for bn, bp in zip(bnames, bposes):
                        mat = Matrix(bp)
                        inv = mat.inverted()
                        head_positions[bn] = Vector((-inv.translation.x, inv.translation.y, inv.translation.z))

                    for bn in bnames:
                        eb = arm_data.edit_bones.new(bn)
                        h = head_positions[bn]
                        eb.head = h
                        eb.tail = h + Vector((0, 0, 0.02))

                    for bn in bnames:
                        pn = pmap.get(bn)
                        if pn and pn in arm_data.edit_bones:
                            arm_data.edit_bones[bn].parent = arm_data.edit_bones[pn]

                    bpy.ops.object.mode_set(mode='OBJECT')

                    if target_col != scene_col:
                        target_col.objects.link(arm_obj)
                        scene_col.objects.unlink(arm_obj)

                    mesh_copy = part["mesh"].copy()
                    mesh_obj = bpy.data.objects.new(part_display_name, mesh_copy)
                    if part.get("material"):
                        mesh_obj.data.materials.append(part["material"])
                    target_col.objects.link(mesh_obj)

                    for bn in bnames:
                        mesh_obj.vertex_groups.new(name=bn)
                    for v_idx, s_info in enumerate(arm_info["skin"]):
                        for b_attr, w_attr in [('boneIndex_0_', 'weight_0_'), ('boneIndex_1_', 'weight_1_'), ('boneIndex_2_', 'weight_2_'), ('boneIndex_3_', 'weight_3_')]:
                            w = getattr(s_info, w_attr, 0.0)
                            if w and w > 0.0001:
                                bi = getattr(s_info, b_attr, 0)
                                if bi < len(bnames):
                                    mesh_obj.vertex_groups[bnames[bi]].add([v_idx], w, 'REPLACE')

                    mesh_obj.parent = arm_obj
                    mod = mesh_obj.modifiers.new(name="Armature", type='ARMATURE')
                    mod.object = arm_obj

                    for bn, bd in node_bones.items():
                        pb = arm_obj.pose.bones.get(bn)
                        if pb:
                            rot = bd["rot"]
                            rx = math.radians(rot[0])
                            ry = math.radians(-rot[1])
                            rz = math.radians(-rot[2])
                            pb.rotation_mode = 'QUATERNION'
                            pb.rotation_quaternion = Euler((rx, ry, rz), 'ZXY').to_quaternion()
                            if any(abs(x) > 0.0001 for x in bd["pos"]):
                                pb.location = Vector((-bd["pos"][0], bd["pos"][1], bd["pos"][2]))

                    if not is_vis:
                        arm_obj.hide_viewport = True
                        arm_obj.hide_render = True
                        mesh_obj.hide_viewport = True
                        mesh_obj.hide_render = True

                    return arm_obj, mesh_obj

                def assign_object_material(target_obj, mat):
                    if not mat:
                        return
                    if not target_obj.material_slots:
                        target_obj.data.materials.append(None)
                    target_obj.material_slots[0].link = 'OBJECT'
                    target_obj.material_slots[0].material = mat

                if len(parts) == 1:
                    part = parts[0]
                    if part.get("armature_data"):
                        arm_obj, mesh_obj = setup_skinned_part(part, display_name, target_col, is_vis, node.get("bones", {}))
                        created_objects[dic_key] = arm_obj
                    else:
                        obj = bpy.data.objects.new(display_name, part["mesh"])
                        assign_object_material(obj, part.get("material"))
                        target_col.objects.link(obj)
                        created_objects[dic_key] = obj
                        if not is_vis:
                            obj.hide_viewport = True
                            obj.hide_render = True
                    single_part_matrices[dic_key] = part.get("local_matrix", Matrix.Identity(4))

                elif len(parts) > 1:
                    parent_obj = bpy.data.objects.new(display_name, None)
                    parent_obj.empty_display_type = 'PLAIN_AXES'
                    parent_obj.empty_display_size = 0.05
                    target_col.objects.link(parent_obj)
                    created_objects[dic_key] = parent_obj
                    if not is_vis:
                        parent_obj.hide_viewport = True
                        parent_obj.hide_render = True

                    for sub_idx, part in enumerate(parts):
                        sub_name = f"{display_name}_{part['name']}"
                        part_lmat = part.get("local_matrix", Matrix.Identity(4))
                        if part.get("armature_data"):
                            arm_obj, mesh_obj = setup_skinned_part(part, sub_name, target_col, is_vis, node.get("bones", {}))
                            arm_obj.parent = parent_obj
                            arm_obj.matrix_basis = part_lmat
                        else:
                            sub_obj = bpy.data.objects.new(sub_name, part["mesh"])
                            assign_object_material(sub_obj, part.get("material"))
                            target_col.objects.link(sub_obj)
                            sub_obj.parent = parent_obj
                            sub_obj.matrix_basis = part_lmat
                            if not is_vis:
                                sub_obj.hide_viewport = True
                                sub_obj.hide_render = True

                elif not parts:
                    empty = bpy.data.objects.new(display_name, None)
                    empty.empty_display_type = 'PLAIN_AXES'
                    empty.empty_display_size = 0.03
                    target_col.objects.link(empty)
                    created_objects[dic_key] = empty
                    if not is_vis:
                        empty.hide_viewport = True
                        empty.hide_render = True

            # 4. Third Pass: Link Hierarchy & Set Exact Transforms without Scale Distortion
            bpy.context.view_layer.update()
            root_mw = scene_root.matrix_world

            for dic_key in eval_order:
                obj = created_objects.get(dic_key)
                if not obj:
                    continue

                node = parser.parsed_tree[dic_key]
                parent_key = node.get("parent_key")
                parent_obj = created_objects.get(parent_key) if parent_key is not None else None

                if dic_key in char_attachments:
                    char_key, ap_name, m_in_char_u = char_attachments[dic_key]
                    char_obj = created_objects.get(char_key)

                    m_in_char_bl = C_flip @ m_in_char_u @ C_flip
                    if dic_key in single_part_matrices:
                        l_mat = single_part_matrices[dic_key]
                        if l_mat != Matrix.Identity(4):
                            m_in_char_bl = m_in_char_bl @ l_mat

                    char_mw = char_obj.matrix_world if char_obj else scene_root.matrix_world
                    blender_mw = char_mw @ m_in_char_bl

                    if parent_obj and parent_obj != char_obj and obj != parent_obj:
                        obj.parent = parent_obj
                        obj.matrix_parent_inverse = parent_obj.matrix_world.inverted()
                    elif char_obj and char_obj.type == 'ARMATURE' and ap_name and ap_name in char_obj.pose.bones:
                        obj.parent = char_obj
                        obj.parent_type = 'BONE'
                        obj.parent_bone = ap_name
                        bone_mw = char_obj.matrix_world @ char_obj.pose.bones[ap_name].matrix
                        obj.matrix_parent_inverse = bone_mw.inverted()
                    elif char_obj and obj != char_obj:
                        obj.parent = char_obj
                        obj.matrix_parent_inverse = char_obj.matrix_world.inverted()
                    else:
                        obj.parent = scene_root
                        obj.matrix_parent_inverse = scene_root.matrix_world.inverted()

                    obj.matrix_world = blender_mw

                else:
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

            if pending_com_transfers:
                com_blend = find_com_append_blend()
                if com_blend:
                    for arm_obj, target_col in pending_com_transfers:
                        com_arm, com_mesh = append_com_body(com_blend, target_col)
                        com_arm.show_in_front = True
                        if com_mesh:
                            com_mesh.hide_viewport = False
                            com_mesh.hide_render = False
                        setup_kk_to_com_transfer(arm_obj, com_arm)
                else:
                    print("[KK Importer] CM3D2 Converter append_data.blend not found. Skipping COM transfer.")

            # 5. Fifth Pass: Apply Inactive Visibility to Folder Collections
            def set_collection_visibility(layer_col, target_col, visible):
                if layer_col.collection == target_col:
                    layer_col.hide_viewport = not visible
                    return True
                for child in layer_col.children:
                    if set_collection_visibility(child, target_col, visible):
                        return True
                return False

            root_lc = context.view_layer.layer_collection
            for f_key, f_col in folder_cols.items():
                if not is_node_effectively_visible(f_key):
                    f_col.hide_viewport = True
                    f_col.hide_render = True
                    set_collection_visibility(root_lc, f_col, False)

            elapsed = time.time() - start_time
            self.report({'INFO'}, f"Successfully imported {len(created_objects)} objects in {elapsed:.1f}s!")
            print(f"[KK Importer] Finished importing {len(created_objects)} objects in {elapsed:.1f}s.")
        finally:
            wm.progress_end()
            if win:
                win.cursor_modal_restore()

        return {'FINISHED'}


# =========================================================================
# 3. Property Definitions & UI Panels
# =========================================================================

class KKStudioSceneProperties(bpy.types.PropertyGroup):
    kk_dir: StringProperty(
        name="Koikatsu Path",
        description="Path to Koikatsu game directory",
        default=r"K:\KK",
        subtype='DIR_PATH'
    )
    scene_path: StringProperty(
        name="Scene PNG",
        description="Path to Studio Scene PNG file",
        default=r"K:\KK\UserData\Studio\scene\2026_0222_2203_14_452.png",
        subtype='FILE_PATH'
    )
    import_character_pose: BoolProperty(
        name="Import Character Pose",
        description="Build posed KK character armature from scene FK data",
        default=True
    )
    simplify_armature_bones: BoolProperty(
        name="Simplify Bone Hierarchy",
        description="Exclude internal Koikatsu physics, collision, and morph clutter bones (keeps only COM body & accessory attachment bones)",
        default=True
    )
    transfer_to_com_body: BoolProperty(
        name="Transfer to COM Body",
        description="Append lightweight COM body and retarget the pose via driver constraints",
        default=False
    )
    import_attached_props: BoolProperty(
        name="Import Attached Props",
        description="Load props attached to characters (body/clothes ignored)",
        default=True
    )
    import_meshless: BoolProperty(
        name="Import Meshless Objects",
        description="Load objects without 3D geometry (keeps hierarchy empties for children if disabled, skips leaf meshless objects)",
        default=False
    )
    use_fallback_cubes: BoolProperty(
        name="Fallback Cubes",
        description="Place labeled cubes for missing modded assets",
        default=False
    )


class KK_PT_StudioImporterPanel(bpy.types.Panel):
    bl_label = "KK Studio Importer"
    bl_idname = "KK_PT_studio_importer"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "KK Studio"

    def draw(self, context):
        layout = self.layout
        props = context.scene.kk_studio_props

        if not DEPS_LOADED:
            box = layout.box()
            box.label(text="Dependencies Missing!", icon='ERROR')
            box.label(text="Run: pip install UnityPy msgpack Pillow")
            return

        box = layout.box()
        box.label(text="Paths:", icon='FILE_FOLDER')
        box.prop(props, "kk_dir")
        box.prop(props, "scene_path")
        box.operator("kk_studio.reindex_database", text="Re-index Asset Cache", icon='FILE_REFRESH')

        box = layout.box()
        box.label(text="Character & COM Pose:", icon='ARMATURE_DATA')
        box.prop(props, "import_character_pose")
        box.prop(props, "simplify_armature_bones")
        box.prop(props, "transfer_to_com_body")
        box.operator("kk_studio.transfer_to_com", text="Retarget Active Rig to COM", icon='CON_ROTLIMIT')

        box = layout.box()
        box.label(text="Scene Props:", icon='PREFERENCES')
        box.prop(props, "import_attached_props")
        box.prop(props, "import_meshless")
        box.prop(props, "use_fallback_cubes")

        layout.separator()
        layout.operator("kk_studio.import_scene", text="Import Studio Scene", icon='IMPORT')

        box = layout.box()
        box.label(text="COM3D2 Merge & Prep (Selected):", icon='MOD_SOLIDIFY')
        box.operator("kk_studio.clean_occluded_geometry", text="Clean Occluded Geometry", icon='BRUSH_DATA')
        box.operator("kk_studio.merge_selected_props", text="Merge Selected into .model Mesh", icon='AUTOMERGE_ON')


classes = (
    KKStudioSceneProperties,
    KK_OT_ReindexDatabase,
    KK_OT_TransferToCOM,
    KK_OT_ImportScene,
    KK_OT_CleanOccludedGeometry,
    KK_OT_MergeSelectedProps,
    KK_PT_StudioImporterPanel,
)

def register():
    for c in classes:
        bpy.utils.register_class(c)
    bpy.types.Scene.kk_studio_props = bpy.props.PointerProperty(type=KKStudioSceneProperties)

def unregister():
    for c in reversed(classes):
        bpy.utils.unregister_class(c)
    del bpy.types.Scene.kk_studio_props

if __name__ == "__main__":
    register()
