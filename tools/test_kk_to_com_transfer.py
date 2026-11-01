import bpy
import json
import math
import os
import sys
from mathutils import Matrix, Vector, Euler, Quaternion

# 1. Base mappings
KK_TO_COM_BONES = {
    # Core Spine & Head
    "cf_j_hips": "Bip01 Pelvis",
    "cf_j_waist01": "Bip01 Spine",
    "cf_j_spine01": "Bip01 Spine1",
    "cf_j_spine02": "Bip01 Spine2",
    "cf_j_neck": "Bip01 Neck",
    "cf_j_head": "Bip01 Head",

    # Left Arm
    "cf_j_shoulder_L": "Bip01 L Clavicle",
    "cf_j_arm00_L": "Bip01 L UpperArm",
    "cf_j_forearm01_L": "Bip01 L Forearm",
    "cf_j_hand_L": "Bip01 L Hand",

    # Right Arm
    "cf_j_shoulder_R": "Bip01 R Clavicle",
    "cf_j_arm00_R": "Bip01 R UpperArm",
    "cf_j_forearm01_R": "Bip01 R Forearm",
    "cf_j_hand_R": "Bip01 R Hand",

    # Left Leg
    "cf_j_thigh00_L": "Bip01 L Thigh",
    "cf_j_leg01_L": "Bip01 L Calf",
    "cf_j_leg03_L": "Bip01 L Foot",
    "cf_j_toes_L": "Bip01 L Toe0",

    # Right Leg
    "cf_j_thigh00_R": "Bip01 R Thigh",
    "cf_j_leg01_R": "Bip01 R Calf",
    "cf_j_leg03_R": "Bip01 R Foot",
    "cf_j_toes_R": "Bip01 R Toe0",

    # Left Fingers
    "cf_j_thumb01_L": "Bip01 L Finger0",
    "cf_j_thumb02_L": "Bip01 L Finger01",
    "cf_j_thumb03_L": "Bip01 L Finger02",
    "cf_j_index01_L": "Bip01 L Finger1",
    "cf_j_index02_L": "Bip01 L Finger11",
    "cf_j_index03_L": "Bip01 L Finger12",
    "cf_j_middle01_L": "Bip01 L Finger2",
    "cf_j_middle02_L": "Bip01 L Finger21",
    "cf_j_middle03_L": "Bip01 L Finger22",
    "cf_j_ring01_L": "Bip01 L Finger3",
    "cf_j_ring02_L": "Bip01 L Finger31",
    "cf_j_ring03_L": "Bip01 L Finger32",
    "cf_j_little01_L": "Bip01 L Finger4",
    "cf_j_little02_L": "Bip01 L Finger41",
    "cf_j_little03_L": "Bip01 L Finger42",

    # Right Fingers
    "cf_j_thumb01_R": "Bip01 R Finger0",
    "cf_j_thumb02_R": "Bip01 R Finger01",
    "cf_j_thumb03_R": "Bip01 R Finger02",
    "cf_j_index01_R": "Bip01 R Finger1",
    "cf_j_index02_R": "Bip01 R Finger11",
    "cf_j_index03_R": "Bip01 R Finger12",
    "cf_j_middle01_R": "Bip01 R Finger2",
    "cf_j_middle02_R": "Bip01 R Finger21",
    "cf_j_middle03_R": "Bip01 R Finger22",
    "cf_j_ring01_R": "Bip01 R Finger3",
    "cf_j_ring02_R": "Bip01 R Finger31",
    "cf_j_ring03_R": "Bip01 R Finger32",
    "cf_j_little01_R": "Bip01 R Finger4",
    "cf_j_little02_R": "Bip01 R Finger41",
    "cf_j_little03_R": "Bip01 R Finger42",

    # Breasts
    "cf_j_bust01_L": "Mune_L",
    "cf_j_bust01_R": "Mune_R",
}

def build_kk_armature(scene_path, char_dickey, skeleton_path, bone_maps_path):
    sys.path.append(r'k:\com plugins\kk_studio_to_blender_importer')
    from kk_studio_scene_importer import KKStudioParser

    parser = KKStudioParser(scene_path)
    char_node = parser.parsed_tree[char_dickey]

    with open(skeleton_path, 'r', encoding='utf-8') as f:
        skeleton = json.load(f)
    with open(bone_maps_path, 'r', encoding='utf-8') as f:
        maps = json.load(f)

    bone_map = {int(k): v for k, v in maps['bones'].items()}

    arm_data = bpy.data.armatures.new(f"KK_Armature_{char_dickey}")
    arm_obj = bpy.data.objects.new(f"KK_Character_{char_dickey}", arm_data)
    bpy.context.scene.collection.objects.link(arm_obj)
    bpy.context.view_layer.objects.active = arm_obj

    # Char root transform in Blender
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

    # Apply FK Pose
    bpy.ops.object.mode_set(mode='POSE')
    pose_bones = arm_obj.pose.bones
    for b_idx, b_info in char_node.get("bones", {}).items():
        b_name = bone_map.get(b_idx)
        if not b_name or b_name not in pose_bones:
            continue
        pb = pose_bones[b_name]
        b_rot = b_info["rot"]
        pb.rotation_mode = 'ZXY'
        pb.rotation_euler = Euler((
            math.radians(b_rot[0]),
            math.radians(-b_rot[1]),
            math.radians(-b_rot[2])
        ), 'ZXY')

    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.context.view_layer.update()
    return arm_obj


def append_com_body(com_blend_path):
    with bpy.data.libraries.load(com_blend_path) as (data_from, data_to):
        data_to.objects = ['body001.body', 'body001.body.armature']

    body_mesh = data_to.objects[0]
    body_arm = data_to.objects[1]

    bpy.context.scene.collection.objects.link(body_arm)
    bpy.context.scene.collection.objects.link(body_mesh)
    bpy.context.view_layer.update()
    return body_arm, body_mesh


def setup_kk_to_com_transfer(kk_arm, com_arm):
    """
    Creates Driver Empty pairs (_drv_parent and _drv_child) and hooks up
    Copy Rotation constraints from KK to COM body.
    """
    col_name = "KK_COM_Transfer_Drivers"
    if col_name not in bpy.data.collections:
        drv_col = bpy.data.collections.new(col_name)
        bpy.context.scene.collection.children.link(drv_col)
    else:
        drv_col = bpy.data.collections[col_name]

    # Ensure transforms are up to date
    bpy.context.view_layer.update()

    # Root Bip01 driver
    # Bip01 handles position and orientation of the character root
    bip_parent = bpy.data.objects.new("Bip01_drv_parent", None)
    bip_parent.empty_display_type = 'PLAIN_AXES'
    bip_parent.empty_display_size = 0.1
    drv_col.objects.link(bip_parent)

    c_rot = bip_parent.constraints.new('COPY_ROTATION')
    c_rot.target = kk_arm
    c_rot.subtarget = "cf_j_hips"
    c_rot.target_space = 'WORLD'
    c_rot.owner_space = 'WORLD'

    c_loc = bip_parent.constraints.new('COPY_LOCATION')
    c_loc.target = kk_arm
    c_loc.subtarget = "cf_j_hips"
    c_loc.target_space = 'WORLD'
    c_loc.owner_space = 'WORLD'

    bip_child = bpy.data.objects.new("Bip01_drv_child", None)
    bip_child.empty_display_type = 'PLAIN_AXES'
    bip_child.empty_display_size = 0.08
    drv_col.objects.link(bip_child)
    bip_child.parent = bip_parent

    # Calibrate Bip01 rest rotation
    bip_child.rotation_euler = Euler((-math.pi, -math.pi/2, 0), 'XYZ')

    def clear_constraints(pb):
        for c in list(pb.constraints):
            pb.constraints.remove(c)

    # Hook Bip01 on COM armature
    bip_pb = com_arm.pose.bones.get("Bip01")
    if bip_pb:
        clear_constraints(bip_pb)
        c = bip_pb.constraints.new('COPY_LOCATION')
        c.target = bip_child
        c.target_space = 'WORLD'
        c.owner_space = 'WORLD'
        c = bip_pb.constraints.new('COPY_ROTATION')
        c.target = bip_child
        c.target_space = 'WORLD'
        c.owner_space = 'WORLD'

    # Now hook each mapped bone
    linked_count = 0
    for kk_bone, com_bone in KK_TO_COM_BONES.items():
        if kk_bone not in kk_arm.pose.bones or com_bone not in com_arm.pose.bones:
            continue

        parent_name = f"{com_bone}_drv_parent"
        child_name = f"{com_bone}_drv_child"

        drv_parent = bpy.data.objects.new(parent_name, None)
        drv_parent.empty_display_type = 'PLAIN_AXES'
        drv_parent.empty_display_size = 0.05
        drv_col.objects.link(drv_parent)

        c = drv_parent.constraints.new('COPY_ROTATION')
        c.target = kk_arm
        c.subtarget = kk_bone
        c.target_space = 'WORLD'
        c.owner_space = 'WORLD'

        drv_child = bpy.data.objects.new(child_name, None)
        drv_child.empty_display_type = 'PLAIN_AXES'
        drv_child.empty_display_size = 0.04
        drv_col.objects.link(drv_child)
        drv_child.parent = drv_parent

        # Compute rest orientation offset
        # In rest pose, kk_bone rest matrix -> com_bone rest matrix
        kk_rest_mat = kk_arm.matrix_world @ kk_arm.data.bones[kk_bone].matrix_local
        com_rest_mat = com_arm.matrix_world @ com_arm.data.bones[com_bone].matrix_local

        r_kk = kk_rest_mat.to_quaternion()
        r_com = com_rest_mat.to_quaternion()
        # R_offset = R_kk^{-1} @ R_com
        r_offset = r_kk.inverted() @ r_com
        drv_child.rotation_euler = r_offset.to_euler('XYZ')

        # Hook COM pose bone
        pb = com_arm.pose.bones[com_bone]
        clear_constraints(pb)
        c = pb.constraints.new('COPY_ROTATION')
        c.target = drv_child
        c.target_space = 'WORLD'
        c.owner_space = 'WORLD'
        linked_count += 1

    bpy.context.view_layer.update()
    print(f"Successfully linked {linked_count} bones from KK to COM body!")


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)

    scene_path = r'K:\KK\UserData\Studio\scene\2021_0614_1058_19_167.png'
    com_blend_path = r'C:\Users\harri\AppData\Roaming\Blender Foundation\Blender\3.3\scripts\addons\CM3D2 Converter\append_data.blend'
    skeleton_path = r'K:\com plugins\kk_studio_to_blender_importer\kk_base_skeleton.json'
    bone_maps_path = r'K:\com plugins\kk_studio_to_blender_importer\kk_studio_bone_maps.json'

    # Build KK armature
    kk_arm = build_kk_armature(scene_path, 1518, skeleton_path, bone_maps_path)

    # Append lightweight COM body
    com_arm, com_mesh = append_com_body(com_blend_path)

    # Setup transfer rig
    setup_kk_to_com_transfer(kk_arm, com_arm)

    # Add Camera and Sun Light looking at COM body
    bpy.context.view_layer.update()
    pelvis = com_arm.pose.bones.get('Bip01 Pelvis')
    p_loc = com_arm.matrix_world @ pelvis.matrix.translation

    cam_data = bpy.data.cameras.new('TestCam')
    cam_data.lens = 45
    cam_obj = bpy.data.objects.new('TestCam', cam_data)
    bpy.context.scene.collection.objects.link(cam_obj)
    cam_obj.location = (p_loc.x, p_loc.y - 6.5, p_loc.z + 0.3)
    cam_obj.rotation_euler = (1.57, 0, 0)
    bpy.context.scene.camera = cam_obj

    sun_data = bpy.data.lights.new('TestSun', 'SUN')
    sun_data.energy = 3.0
    sun_obj = bpy.data.objects.new('TestSun', sun_data)
    bpy.context.scene.collection.objects.link(sun_obj)
    sun_obj.location = (p_loc.x + 3, p_loc.y - 5, p_loc.z + 5)
    sun_obj.rotation_euler = (0.8, 0.4, 0.2)

    # Render image
    render_out = r'C:\Users\harri\.gemini\antigravity-ide\brain\72001821-3278-42f2-8276-1af64794842a\scratch\kk_to_com_transfer_full.png'
    bpy.context.scene.render.image_settings.file_format = 'PNG'
    bpy.context.scene.render.filepath = render_out
    bpy.ops.render.render(write_still=True)
    print(f"Rendered pose image to: {render_out}")

    # Save test blend
    out_blend = r'C:\Users\harri\.gemini\antigravity-ide\brain\72001821-3278-42f2-8276-1af64794842a\scratch\kk_to_com_transfer_test.blend'
    bpy.ops.wm.save_as_mainfile(filepath=out_blend)
    print(f"Saved test blend to: {out_blend}")

if __name__ == '__main__':
    main()

