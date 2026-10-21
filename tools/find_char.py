import struct, io, json, traceback

scene_path = r"K:\KK\UserData\Studio\scene\2026_0222_2203_14_452.png"
with open(scene_path, "rb") as f:
    data = f.read()

iend_pos = data.find(b"IEND") + 8
stream = io.BytesIO(data[iend_pos:])

def rs(s):
    l = 0; sh = 0
    while True:
        b = s.read(1)[0]; l |= (b & 0x7F) << sh
        if (b & 0x80) == 0: break
        sh += 7
    return s.read(l).decode("utf-8", errors="ignore")

def r_v3(s): return struct.unpack("<fff", s.read(12))
def r_b(s): return struct.unpack("<?", s.read(1))[0]
def r_i(s): return struct.unpack("<i", s.read(4))[0]
def r_f(s): return struct.unpack("<f", s.read(4))[0]

version = rs(stream)
root_count = r_i(stream)

def parse_change_amount(s):
    return {"pos": r_v3(s), "rot": r_v3(s), "scale": r_v3(s)}

def parse_object_info(s, other=True):
    dic_key = r_i(s)
    ca = parse_change_amount(s)
    if other:
        tree_state = r_i(s)
        visible = r_b(s)
    else:
        visible = True
    return dic_key, ca, visible

def parse_pattern_info(s):
    key = r_i(s)
    file_path = rs(s)
    clamp = r_b(s)
    uv_str = rs(s)
    rot = r_f(s)
    return {"key": key, "file": file_path, "rot": rot}

def get_png_size(s):
    start = s.tell()
    sig = s.read(8)
    if sig != b"\x89PNG\r\n\x1a\n":
        s.seek(start)
        return 0
    while True:
        len_bytes = s.read(4)
        if len(len_bytes) < 4: break
        chunk_len = struct.unpack(">I", len_bytes)[0]
        chunk_type = s.read(4)
        s.seek(chunk_len + 4, io.SEEK_CUR)
        if chunk_type == b"IEND":
            break
    end = s.tell()
    return end - start

all_nodes = {}

def parse_child(s, parent_key):
    child_count = r_i(s)
    for i in range(child_count):
        kind = r_i(s)
        parse_node(s, kind, parent_key)

def parse_node(s, kind, parent_key):
    dic_key, ca, visible = parse_object_info(s)
    node_data = {
        "dic_key": dic_key,
        "kind": kind,
        "parent_key": parent_key,
        "pos": ca["pos"],
        "rot": ca["rot"],
        "scale": ca["scale"],
        "visible": visible
    }
    all_nodes[dic_key] = node_data

    if kind == 3: # Folder
        folder_name = rs(s)
        node_data["name"] = folder_name
        parse_child(s, dic_key)

    elif kind == 1: # Item
        group = r_i(s)
        category = r_i(s)
        no = r_i(s)
        anime_speed = r_f(s)
        colors = [rs(s) for _ in range(8)]
        patterns = [parse_pattern_info(s) for _ in range(3)]
        alpha = r_f(s)
        line_color = rs(s)
        line_width = r_f(s)
        emission_color = rs(s)
        emission_power = r_f(s)
        light_cancel = r_f(s)
        panel = parse_pattern_info(s)
        enable_fk = r_b(s)
        bone_count = r_i(s)
        for _ in range(bone_count):
            bone_name = rs(s)
            b_key = r_i(s)
            b_ca = parse_change_amount(s)
        enable_db = r_b(s)
        anime_nml_time = r_f(s)
        node_data["group"] = group
        node_data["category"] = category
        node_data["no"] = no
        node_data["colors"] = colors
        parse_child(s, dic_key)

    elif kind == 2: # Light
        no = r_i(s)
        c_r, c_g, c_b, c_a = struct.unpack("<ffff", s.read(16))
        intensity = r_f(s)
        range_val = r_f(s)
        spot_angle = r_f(s)
        shadow = r_b(s)
        enable = r_b(s)
        draw_target = r_b(s)
        node_data["name"] = f"Light_{dic_key}"

    elif kind == 4: # Route
        route_name = rs(s)
        node_data["name"] = route_name
        parse_child(s, dic_key)
        pt_count = r_i(s)
        for _ in range(pt_count):
            pt_key, pt_ca, pt_vis = parse_object_info(s)
        active = r_b(s)
        loop = r_b(s)
        vis_line = r_b(s)
        orient = r_i(s)
        color_str = rs(s)

    elif kind == 5: # Camera
        cam_name = rs(s)
        node_data["name"] = cam_name
        active = r_b(s)

    elif kind == 0: # Character
        sex = r_i(s)
        png_size = get_png_size(s)
        prod_no = r_i(s)
        chara_tag = rs(s)
        chara_ver = rs(s)
        face_len = r_i(s)
        if face_len > 0:
            face_data = s.read(face_len)
        header_len = r_i(s)
        header_data = s.read(header_len)
        total_block_size = struct.unpack("<q", s.read(8))[0]
        s.seek(total_block_size, io.SEEK_CUR)

        # Bones: b_key(4) + dic_key(4) + changeAmount(36) = 44 bytes per bone
        bone_count = r_i(s)
        print(f"Char {dic_key}: bone_count={bone_count}")
        for _ in range(bone_count):
            b_key = r_i(s)
            b_dickey = r_i(s)
            b_ca = parse_change_amount(s)

        # IK: ik_key(4) + dic_key(4) + changeAmount(36) = 44 bytes per ik target
        ik_count = r_i(s)
        print(f"Char {dic_key}: ik_count={ik_count}")
        for _ in range(ik_count):
            ik_key = r_i(s)
            ik_dickey = r_i(s)
            ik_ca = parse_change_amount(s)

        # Attached child props
        child_dict_count = r_i(s)
        print(f"Char {dic_key}: child_dict_count={child_dict_count}")
        for _ in range(child_dict_count):
            attach_point = r_i(s)
            child_list_count = r_i(s)
            print(f"  attach_point {attach_point}: {child_list_count} props")
            for _ in range(child_list_count):
                ckind = r_i(s)
                parse_node(s, ckind, dic_key)

        # Rest of char info
        kinematic_mode = r_i(s)
        anim_group = r_i(s)
        anim_cat = r_i(s)
        anim_no = r_i(s)
        hptn0 = r_i(s)
        hptn1 = r_i(s)
        nipple = r_f(s)
        siru = s.read(5)
        mouth_open = r_f(s)
        lip_sync = r_b(s)
        lookat_obj = parse_object_info(s, other=False)
        enable_ik = r_b(s)
        for _ in range(5): r_b(s)
        enable_fk = r_b(s)
        for _ in range(7): r_b(s)
        for _ in range(8): r_b(s)
        anime_speed = r_f(s)
        anime_pattern = r_f(s)
        anime_opt_vis = r_b(s)
        anime_force_loop = r_b(s)
        
        # VoiceCtrl
        voice_count = r_i(s)
        for _ in range(voice_count):
            r_i(s); r_i(s); r_i(s)
        voice_repeat = r_i(s)

        visible_son = r_b(s)
        son_length = r_f(s)
        visible_simple = r_b(s)
        simple_color = rs(s)
        opt0 = r_f(s)
        opt1 = r_f(s)
        neck_len = r_i(s)
        if neck_len > 0: s.read(neck_len)
        eyes_len = r_i(s)
        if eyes_len > 0: s.read(eyes_len)
        anime_nml_time = r_f(s)
        acc_grp_cnt = r_i(s)
        for _ in range(acc_grp_cnt):
            r_i(s); r_i(s)
        acc_no_cnt = r_i(s)
        for _ in range(acc_no_cnt):
            r_i(s); r_i(s)
        print(f"Char {dic_key} SUCCESS! Offset: {s.tell()}")

try:
    for i in range(root_count):
        k = r_i(stream)
        kind = r_i(stream)
        print(f"Root {i}: key={k}, kind={kind} offset={stream.tell()}")
        parse_node(stream, kind, None)
    print(f"FINISHED ALL ROOTS! Total nodes: {len(all_nodes)}")
except Exception as e:
    print(f"Exception: {e}")
    traceback.print_exc()

items = [v for v in all_nodes.values() if v["kind"] == 1]
folders = [v for v in all_nodes.values() if v["kind"] == 3]
chars = [v for v in all_nodes.values() if v["kind"] == 0]
print(f"Summary: {len(folders)} Folders, {len(items)} Items, {len(chars)} Characters")
