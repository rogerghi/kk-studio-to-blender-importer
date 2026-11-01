import os
import json
import math
import bpy
from mathutils import Matrix, Vector, Quaternion, Euler

KK_TO_COM_BONES = {
    # Core Spine & Head
    "cf_j_hips": "Bip01",
    "cf_j_waist02": "Bip01 Pelvis",
    "cf_j_spine01": "Bip01 Spine",
    "cf_j_spine02": "Bip01 Spine1",
    "cf_j_spine03": "Bip01 Spine1a",
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
    "cf_j_bust02_L": "Mune_L_sub",
    "cf_j_bust01_R": "Mune_R",
    "cf_j_bust02_R": "Mune_R_sub",
}

# Full COM-to-KK bone pairing (allows multiple COM bones such as Spine0a and twist bones to follow KK bones)
COM_TO_KK_BONES = {
    "Bip01": "cf_j_hips",
    "Bip01 Pelvis": "cf_j_waist02",
    "Bip01 Spine": "cf_j_spine01",
    "Bip01 Spine0a": "cf_j_spine01",
    "Bip01 Spine1": "cf_j_spine02",
    "Bip01 Spine1a": "cf_j_spine03",
    "Bip01 Neck": "cf_j_neck",
    "Bip01 Head": "cf_j_head",

    "Bip01 L Clavicle": "cf_j_shoulder_L",
    "Bip01 L UpperArm": "cf_j_arm00_L",
    "Bip01 L Forearm": "cf_j_forearm01_L",
    "Bip01 L Hand": "cf_j_hand_L",

    "Bip01 R Clavicle": "cf_j_shoulder_R",
    "Bip01 R UpperArm": "cf_j_arm00_R",
    "Bip01 R Forearm": "cf_j_forearm01_R",
    "Bip01 R Hand": "cf_j_hand_R",

    "Bip01 L Thigh": "cf_j_thigh00_L",
    "Bip01 L Calf": "cf_j_leg01_L",
    "Bip01 L Foot": "cf_j_leg03_L",
    "Bip01 L Toe0": "cf_j_toes_L",

    "Bip01 R Thigh": "cf_j_thigh00_R",
    "Bip01 R Calf": "cf_j_leg01_R",
    "Bip01 R Foot": "cf_j_leg03_R",
    "Bip01 R Toe0": "cf_j_toes_R",

    "Bip01 L Finger0": "cf_j_thumb01_L",
    "Bip01 L Finger01": "cf_j_thumb02_L",
    "Bip01 L Finger02": "cf_j_thumb03_L",
    "Bip01 L Finger1": "cf_j_index01_L",
    "Bip01 L Finger11": "cf_j_index02_L",
    "Bip01 L Finger12": "cf_j_index03_L",
    "Bip01 L Finger2": "cf_j_middle01_L",
    "Bip01 L Finger21": "cf_j_middle02_L",
    "Bip01 L Finger22": "cf_j_middle03_L",
    "Bip01 L Finger3": "cf_j_ring01_L",
    "Bip01 L Finger31": "cf_j_ring02_L",
    "Bip01 L Finger32": "cf_j_ring03_L",
    "Bip01 L Finger4": "cf_j_little01_L",
    "Bip01 L Finger41": "cf_j_little02_L",
    "Bip01 L Finger42": "cf_j_little03_L",

    "Bip01 R Finger0": "cf_j_thumb01_R",
    "Bip01 R Finger01": "cf_j_thumb02_R",
    "Bip01 R Finger02": "cf_j_thumb03_R",
    "Bip01 R Finger1": "cf_j_index01_R",
    "Bip01 R Finger11": "cf_j_index02_R",
    "Bip01 R Finger12": "cf_j_index03_R",
    "Bip01 R Finger2": "cf_j_middle01_R",
    "Bip01 R Finger21": "cf_j_middle02_R",
    "Bip01 R Finger22": "cf_j_middle03_R",
    "Bip01 R Finger3": "cf_j_ring01_R",
    "Bip01 R Finger31": "cf_j_ring02_R",
    "Bip01 R Finger32": "cf_j_ring03_R",
    "Bip01 R Finger4": "cf_j_little01_R",
    "Bip01 R Finger41": "cf_j_little02_R",
    "Bip01 R Finger42": "cf_j_little03_R",

    "Mune_L": "cf_j_bust01_L",
    "Mune_L_sub": "cf_j_bust02_L",
    "Mune_R": "cf_j_bust01_R",
    "Mune_R_sub": "cf_j_bust02_R",

    # Twist & Volume preservation helper bones (compensate for COM3D2 bent-limb bind pose)
    "Kata_L": "cf_j_arm00_L",
    "Uppertwist_L": "cf_j_arm00_L",
    "Uppertwist1_L": "cf_j_arm00_L",
    "Foretwist_L": "cf_j_forearm01_L",
    "Foretwist1_L": "cf_j_forearm01_L",
    "Kata_R": "cf_j_arm00_R",
    "Uppertwist_R": "cf_j_arm00_R",
    "Uppertwist1_R": "cf_j_arm00_R",
    "Foretwist_R": "cf_j_forearm01_R",
    "Foretwist1_R": "cf_j_forearm01_R",
    "Hip_L": "cf_j_thigh00_L",
    "momotwist_L": "cf_j_thigh00_L",
    "momotwist2_L": "cf_j_thigh00_L",
    "Hip_R": "cf_j_thigh00_R",
    "momotwist_R": "cf_j_thigh00_R",
    "momotwist2_R": "cf_j_thigh00_R",
}

# Canonical COM3D2 T-pose bone orientations in Blender armature space (from CM3D2 Tスタンス素体.armature).
# Because body001.body.armature is bound in a bent-elbow / crouching-knee rest pose, using the
# canonical T-pose orientation as the target reference ensures that a T-posed KK rig maps to a
# T-posed COM3D2 rig and all posed limbs match the exact world pose without resizing COM bones.
COM_TPOSE_QUATS = {
    "Bip01": (0.000001, 0.707107, 0.000001, 0.707107),
    "Bip01 Pelvis": (0.658173, 0.752867, 0.000001, 0.000001),
    "Bip01 Spine": (0.673942, 0.738784, -0.0, -0.000001),
    "Bip01 Spine0a": (0.732489, 0.680779, -0.000001, -0.000001),
    "Bip01 Spine1": (0.771715, 0.635969, -0.000001, -0.000001),
    "Bip01 Spine1a": (0.754785, 0.655972, -0.000001, -0.0),
    "Bip01 Neck": (0.644761, 0.764384, -0.0, -0.000001),
    "Bip01 Head": (0.707108, 0.707106, -0.0, -0.000001),

    "Bip01 L Clavicle": (0.420501, -0.503618, -0.562516, -0.503114),
    "Bip01 L UpperArm": (0.502152, -0.499335, -0.496648, -0.501845),
    "Bip01 L Forearm": (0.504963, -0.496492, -0.499473, -0.499034),
    "Bip01 L Hand": (0.016857, -0.703775, -0.710189, -0.006943),

    "Bip01 R Clavicle": (0.420501, -0.503619, 0.562515, 0.503114),
    "Bip01 R UpperArm": (0.502151, -0.499335, 0.496647, 0.501846),
    "Bip01 R Forearm": (0.504963, -0.496493, 0.499473, 0.499034),
    "Bip01 R Hand": (0.016857, -0.703776, 0.710188, 0.006942),

    "Bip01 L Thigh": (0.003278, 0.013051, -0.712511, 0.701532),
    "Bip01 L Calf": (0.002964, 0.013125, -0.69554, 0.718362),
    "Bip01 L Foot": (0.028155, -0.04115, 0.710148, -0.702285),
    "Bip01 L Toe0": (0.049538, -0.01787, 0.093175, -0.994256),

    "Bip01 R Thigh": (0.003278, 0.013049, 0.712511, -0.701532),
    "Bip01 R Calf": (0.002965, 0.013124, 0.695539, -0.718362),
    "Bip01 R Foot": (0.028156, -0.041148, -0.710148, 0.702285),
    "Bip01 R Toe0": (0.049535, -0.017871, -0.093174, 0.994256),

    "Bip01 L Finger0": (0.27972, -0.831659, -0.430742, -0.211095),
    "Bip01 L Finger01": (0.240454, -0.843849, -0.42038, -0.231044),
    "Bip01 L Finger02": (0.240455, -0.843849, -0.42038, -0.231042),
    "Bip01 L Finger1": (0.00257, 0.744577, 0.66713, 0.023158),
    "Bip01 L Finger11": (0.002566, 0.744576, 0.66713, 0.023164),
    "Bip01 L Finger12": (0.002569, 0.744577, 0.66713, 0.023162),
    "Bip01 L Finger2": (0.014327, -0.70594, -0.708071, -0.008893),
    "Bip01 L Finger21": (0.009589, 0.706021, 0.707363, 0.032864),
    "Bip01 L Finger22": (0.009587, 0.70602, 0.707363, 0.032871),
    "Bip01 L Finger3": (0.013658, -0.649583, -0.760087, -0.011117),
    "Bip01 L Finger31": (0.001651, -0.649724, -0.759752, -0.025165),
    "Bip01 L Finger32": (0.004035, 0.649714, 0.759502, 0.031812),
    "Bip01 L Finger4": (0.004734, -0.592985, -0.804893, -0.022215),
    "Bip01 L Finger41": (0.004734, -0.592985, -0.804893, -0.022215),
    "Bip01 L Finger42": (0.015407, 0.592803, 0.803675, 0.049539),

    "Bip01 R Finger0": (0.27972, -0.83166, 0.43074, 0.211096),
    "Bip01 R Finger01": (0.240453, -0.843852, 0.420378, 0.231039),
    "Bip01 R Finger02": (0.240454, -0.84385, 0.420379, 0.231042),
    "Bip01 R Finger1": (0.002565, 0.744577, -0.66713, -0.023163),
    "Bip01 R Finger11": (0.002564, 0.744577, -0.66713, -0.023167),
    "Bip01 R Finger12": (0.002568, 0.744578, -0.667129, -0.023159),
    "Bip01 R Finger2": (0.014327, -0.705941, 0.70807, 0.008891),
    "Bip01 R Finger21": (0.009589, 0.706022, -0.707362, -0.032864),
    "Bip01 R Finger22": (0.009588, 0.706021, -0.707363, -0.032863),
    "Bip01 R Finger3": (0.013659, -0.649584, 0.760086, 0.011118),
    "Bip01 R Finger31": (0.001652, -0.649725, 0.759751, 0.025165),
    "Bip01 R Finger32": (0.004034, 0.649714, -0.759502, -0.031816),
    "Bip01 R Finger4": (0.004736, -0.592986, 0.804892, 0.022214),
    "Bip01 R Finger41": (0.004735, -0.592986, 0.804892, 0.022216),
    "Bip01 R Finger42": (0.015407, 0.592805, -0.803673, -0.04954),

    "Mune_L": (0.1748, -0.002317, -0.125029, -0.976631),
    "Mune_L_sub": (0.003559, 0.174779, -0.977494, 0.11809),
    "Mune_R": (0.124918, 0.976645, -0.174799, 0.002338),
    "Mune_R_sub": (0.977454, -0.118422, -0.0035, -0.17478),

    "Kata_L": (0.495369, -0.502116, -0.501074, -0.501412),
    "Uppertwist_L": (0.54351, -0.453716, -0.451013, -0.543439),
    "Uppertwist1_L": (0.355209, -0.612958, -0.610445, -0.354212),
    "Foretwist_L": (0.025291, -0.730057, -0.682916, 0.001576),
    "Foretwist1_L": (0.358487, -0.61017, -0.591233, -0.386811),

    "Kata_R": (0.495367, -0.502118, 0.501072, 0.501414),
    "Uppertwist_R": (0.54351, -0.453717, 0.451012, 0.543439),
    "Uppertwist1_R": (0.355208, -0.612959, 0.610444, 0.354212),
    "Foretwist_R": (0.025292, -0.730059, 0.682914, -0.001579),
    "Foretwist1_R": (0.591233, 0.386811, -0.358488, 0.61017),

    "Hip_L": (0.004966, 0.014709, -0.696282, 0.7176),
    "momotwist_L": (0.095026, -0.110204, 0.6881, -0.710875),
    "momotwist2_L": (0.007046, 0.019766, -0.68361, 0.729546),
    "Hip_R": (0.004965, 0.014709, 0.696282, -0.7176),
    "momotwist_R": (0.688101, -0.710875, 0.095027, -0.110202),
    "momotwist2_R": (0.683609, -0.729547, -0.007045, -0.019767),
}

KK_PRIMARY_BONE_CHAIN = {
    'cf_j_root': 'cf_j_hips',
    'cf_j_hips': 'cf_j_spine01',
    'cf_j_spine01': 'cf_j_spine02',
    'cf_j_spine02': 'cf_j_spine03',
    'cf_j_spine03': 'cf_j_neck',
    'cf_j_neck': 'cf_j_head',
    'cf_j_shoulder_L': 'cf_j_arm00_L',
    'cf_j_arm00_L': 'cf_j_forearm01_L',
    'cf_j_forearm01_L': 'cf_j_hand_L',
    'cf_j_shoulder_R': 'cf_j_arm00_R',
    'cf_j_arm00_R': 'cf_j_forearm01_R',
    'cf_j_forearm01_R': 'cf_j_hand_R',
    'cf_j_waist01': 'cf_j_waist02',
    'cf_j_thigh00_L': 'cf_j_leg01_L',
    'cf_j_leg01_L': 'cf_j_leg03_L',
    'cf_j_leg03_L': 'cf_j_foot_L',
    'cf_j_foot_L': 'cf_j_toes_L',
    'cf_j_thigh00_R': 'cf_j_leg01_R',
    'cf_j_leg01_R': 'cf_j_leg03_R',
    'cf_j_leg03_R': 'cf_j_foot_R',
    'cf_j_foot_R': 'cf_j_toes_R',
}

def load_base_skeleton_data():
    addon_dir = os.path.dirname(os.path.abspath(__file__))
    sk_path = os.path.join(addon_dir, "kk_base_skeleton.json")
    maps_path = os.path.join(addon_dir, "kk_studio_bone_maps.json")
    if not os.path.exists(sk_path) or not os.path.exists(maps_path):
        return None, None, None
    try:
        with open(sk_path, "r", encoding="utf-8") as f:
            sk = json.load(f)
        with open(maps_path, "r", encoding="utf-8") as f:
            mp = json.load(f)
        acc_m = {int(k): v for k, v in mp.get("accessory_points", {}).items()}
        bone_m = {int(k): v for k, v in mp.get("bones", {}).items()}
        return sk, acc_m, bone_m
    except Exception:
        return None, None, None


def get_essential_skeleton_bones(sk_dict, acc_map=None):
    """Compute the minimal set of essential bones required for COM retargeting and prop attachment."""
    targets = set(COM_TO_KK_BONES.values()) | set(KK_TO_COM_BONES.keys())
    if acc_map:
        targets.update(acc_map.values())
    else:
        _, acc_m, _ = load_base_skeleton_data()
        if acc_m:
            targets.update(acc_m.values())

    essential = set()
    for b in targets:
        curr = b
        while curr:
            essential.add(curr)
            curr = sk_dict.get(curr, {}).get("p")
    return essential


def build_char_skeleton(base_skeleton, char_node=None, simplify=True, acc_map=None):
    """Build a per-character skeleton with Koikatsu ShapeBodyInfoFemale sliders and KKABMX bone modifiers applied."""
    if not base_skeleton:
        return {}
    sk = {
        k: {
            "p": v["p"],
            "t": list(v["t"]),
            "r": list(v["r"]),
            "s": list(v.get("s", [1.0, 1.0, 1.0])),
        }
        for k, v in base_skeleton.items()
    }
    if "p_cf_head_bone" in sk and "cf_s_head" in sk:
        sk["p_cf_head_bone"]["p"] = "cf_s_head"

    sex = char_node.get("sex", 1) if char_node else 1
    sv = char_node.get("shape_body") if char_node else None
    if not sv or len(sv) < 36:
        sv = [0.5] * 44

    correct_head = 0.91 if sex == 0 else 1.0
    correct_neck = 0.91 if sex == 0 else 1.0
    h = sv[0]
    aid = 1.10 - 0.10 * h

    def set_bs(bname, s=None, ty=None, tz=None):
        if bname not in sk:
            return
        if s is not None:
            sk[bname]["s"] = list(s)
        if ty is not None:
            sk[bname]["t"][1] = ty
        if tz is not None:
            sk[bname]["t"][2] = tz

    h_s = 0.84 + 0.16 * h
    set_bs("cf_n_height", s=(h_s, h_s, h_s))
    set_bs("cf_s_hand_L", s=(aid, aid, aid))
    set_bs("cf_s_hand_R", s=(aid, aid, aid))

    head_s = (0.86 + 0.16 * sv[1]) * aid * correct_head
    set_bs("cf_s_head", s=(head_s, head_s, head_s), ty=-0.005 + 0.0058 * sv[1])

    set_bs(
        "cf_s_neck",
        s=((0.65 + 0.75 * sv[2]) * aid * correct_neck, 1.0, (0.65 + 0.75 * sv[3]) * aid * correct_neck),
        tz=-0.007 + 0.014 * sv[3],
    )
    set_bs(
        "cf_s_spine03",
        s=((0.85 + 0.45 * sv[14]) * aid, 1.0, (0.80 + 0.50 * sv[15]) * aid),
        ty=-0.011 + 0.014 * sv[15],
        tz=0.008 - 0.016 * sv[15],
    )
    set_bs("cf_s_spine02", s=((0.85 + 0.55 * sv[16]) * aid, 1.0, (0.85 + 0.55 * sv[17]) * aid))
    set_bs(
        "cf_s_spine01",
        s=((0.88 + 0.72 * sv[18]) * aid, 1.0, (0.92 + 0.53 * sv[19]) * aid),
        tz=0.003 - 0.006 * sv[19],
    )
    set_bs("cf_s_waist01", s=((0.80 + 0.70 * sv[22]) * aid, 1.0, (0.80 + 0.75 * sv[23]) * aid))
    set_bs(
        "cf_s_waist02",
        s=((0.83 + 0.57 * sv[24]) * aid, 1.0, (0.83 + 0.62 * sv[25]) * aid),
        ty=-0.0108 + 0.0028 * sv[25],
    )

    abm_bones = char_node.get("abm_bones", {}) if char_node else {}
    for bname, mod in abm_bones.items():
        if bname not in sk:
            continue
        info = sk[bname]
        sc = mod.get("scale", [1.0, 1.0, 1.0])
        ln = mod.get("length", 1.0)
        po = mod.get("pos", [0.0, 0.0, 0.0])
        ro = mod.get("rot", [0.0, 0.0, 0.0])

        info["s"] = [info["s"][0] * sc[0], info["s"][1] * sc[1], info["s"][2] * sc[2]]
        info["t"] = [info["t"][0] * ln + po[0], info["t"][1] * ln + po[1], info["t"][2] * ln + po[2]]
        if any(abs(x) > 1e-5 for x in ro):
            info["abm_rot"] = list(ro)

    if simplify:
        essential = get_essential_skeleton_bones(sk, acc_map)
        sk = {k: v for k, v in sk.items() if k in essential}

    return sk


def find_com_append_blend():
    # Check Blender 4.2+ Extensions directory first
    try:
        ext_dir = bpy.utils.user_resource('EXTENSIONS')
        if ext_dir and os.path.isdir(ext_dir):
            for root, _, files in os.walk(ext_dir):
                if "append_data.blend" in files and "cm3d2" in root.lower():
                    return os.path.join(root, "append_data.blend")
    except Exception:
        pass

    addons_dir = bpy.utils.user_resource('SCRIPTS', path="addons")
    candidate = os.path.join(addons_dir, "CM3D2 Converter", "append_data.blend")
    if os.path.isfile(candidate):
        return candidate
    for p in bpy.utils.script_paths():
        c = os.path.join(p, "addons", "CM3D2 Converter", "append_data.blend")
        if os.path.isfile(c):
            return c
    return None

def append_com_body(com_blend_path, target_col=None):
    with bpy.data.libraries.load(com_blend_path) as (data_from, data_to):
        data_to.objects = ['body001.body', 'body001.body.armature']

    body_mesh = data_to.objects[0]
    body_arm = data_to.objects[1]

    col = target_col or bpy.context.scene.collection
    col.objects.link(body_arm)
    col.objects.link(body_mesh)
    bpy.context.view_layer.update()
    return body_arm, body_mesh

def setup_kk_to_com_transfer(kk_arm, com_arm):
    col_name = "KK_COM_Transfer_Drivers"
    if col_name not in bpy.data.collections:
        drv_col = bpy.data.collections.new(col_name)
        bpy.context.scene.collection.children.link(drv_col)
    else:
        drv_col = bpy.data.collections[col_name]

    bpy.context.view_layer.update()

    def clear_constraints(pb):
        for c in list(pb.constraints):
            pb.constraints.remove(c)

    # Canonical upright transform from KK armature local space (Y-up, facing +Z) to Blender world space (Z-up, facing -Y)
    R_canonical = Euler((math.pi / 2, 0.0, 0.0), 'XYZ').to_matrix().to_4x4()
    com_mw_quat = com_arm.matrix_world.to_quaternion()

    linked_count = 0
    for com_bone, kk_bone in COM_TO_KK_BONES.items():
        if kk_bone not in kk_arm.pose.bones or com_bone not in com_arm.pose.bones:
            continue

        parent_name = f"{kk_arm.name}_{com_bone}_drv_parent"
        child_name = f"{kk_arm.name}_{com_bone}_drv_child"

        drv_parent = bpy.data.objects.new(parent_name, None)
        drv_parent.empty_display_type = 'PLAIN_AXES'
        drv_parent.empty_display_size = 0.05
        drv_col.objects.link(drv_parent)

        c = drv_parent.constraints.new('COPY_ROTATION')
        c.target = kk_arm
        c.subtarget = kk_bone
        c.target_space = 'WORLD'
        c.owner_space = 'WORLD'

        if com_bone == "Bip01":
            c_loc = drv_parent.constraints.new('COPY_LOCATION')
            c_loc.target = kk_arm
            c_loc.subtarget = kk_bone
            c_loc.target_space = 'WORLD'
            c_loc.owner_space = 'WORLD'

        drv_child = bpy.data.objects.new(child_name, None)
        drv_child.empty_display_type = 'PLAIN_AXES'
        drv_child.empty_display_size = 0.04
        drv_col.objects.link(drv_child)
        drv_child.parent = drv_parent

        kk_rest_mat = R_canonical @ kk_arm.data.bones[kk_bone].matrix_local
        r_kk = kk_rest_mat.to_quaternion()
        if com_bone in COM_TPOSE_QUATS:
            r_com = com_mw_quat @ Quaternion(COM_TPOSE_QUATS[com_bone])
        else:
            com_rest_mat = com_arm.matrix_world @ com_arm.data.bones[com_bone].matrix_local
            r_com = com_rest_mat.to_quaternion()

        r_offset = r_kk.inverted() @ r_com
        drv_child.rotation_mode = 'QUATERNION'
        drv_child.rotation_quaternion = r_offset

        pb = com_arm.pose.bones[com_bone]
        clear_constraints(pb)
        if com_bone == "Bip01":
            cl = pb.constraints.new('COPY_LOCATION')
            cl.target = drv_child
            cl.target_space = 'WORLD'
            cl.owner_space = 'WORLD'
        c = pb.constraints.new('COPY_ROTATION')
        c.target = drv_child
        c.target_space = 'WORLD'
        c.owner_space = 'WORLD'
        linked_count += 1

    bpy.context.view_layer.update()
    return linked_count


class KK_OT_TransferToCOM(bpy.types.Operator):
    bl_idname = "kk_studio.transfer_to_com"
    bl_label = "Transfer Selected KK Rig to COM Body"
    bl_description = "Appends lightweight COM body and links the selected KK armature to it via driver constraints"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        ob = context.active_object
        return ob and ob.type == 'ARMATURE'

    def execute(self, context):
        kk_arm = context.active_object
        com_blend = find_com_append_blend()
        if not com_blend:
            self.report({'ERROR'}, "CM3D2 Converter append_data.blend not found! Make sure CM3D2 Converter addon is installed.")
            return {'CANCELLED'}

        com_arm, com_mesh = append_com_body(com_blend)
        count = setup_kk_to_com_transfer(kk_arm, com_arm)
        self.report({'INFO'}, f"Successfully linked {count} bones to COM body!")
        return {'FINISHED'}
