import struct, io, json

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
print(f"Data Version: {version}, Root Count: {root_count}")

parsed_objects = {} # dic_key -> dict

def parse_change_amount(s):
    return {"pos": r_v3(s), "rot": r_v3(s), "scale": r_v3(s)}

def parse_object_info(s):
    dic_key = r_i(s)
    ca = parse_change_amount(s)
    tree_state = r_i(s)
    visible = r_b(s)
    return dic_key, ca, visible

def parse_pattern_info(s):
    key = r_i(s)
    file_path = rs(s)
    clamp = r_b(s)
    uv_str = rs(s)
    rot = r_f(s)
    return {"key": key, "file": file_path, "rot": rot}

def parse_child(s, parent_key):
    child_count = r_i(s)
    for _ in range(child_count):
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
    
    if kind == 3: # Folder
        folder_name = rs(s)
        node_data["name"] = folder_name
        parsed_objects[dic_key] = node_data
        parse_child(s, dic_key)
        
    elif kind == 1: # Item
        group = r_i(s)
        category = r_i(s)
        no = r_i(s)
        # dummy int is only present if version >= 1.1.1.0
        # In this scene, version is 1.0.4.2 so dummy is NOT read
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
        
        # Bones
        bone_count = r_i(s)
        for _ in range(bone_count):
            bone_name = rs(s)
            b_key, b_ca, b_vis = parse_object_info(s)
            
        enable_db = r_b(s)
        anime_nml_time = r_f(s)
        
        node_data["group"] = group
        node_data["category"] = category
        node_data["no"] = no
        node_data["colors"] = colors
        parsed_objects[dic_key] = node_data
        parse_child(s, dic_key)
        
    elif kind == 2: # Light
        no = r_i(s)
        # Utility.LoadColor
        c_r, c_g, c_b, c_a = struct.unpack("<ffff", s.read(16))
        intensity = r_f(s)
        range_val = r_f(s)
        spot_angle = r_f(s)
        shadow = r_b(s)
        enable = r_b(s)
        draw_target = r_b(s)
        node_data["light"] = {"no": no, "color": (c_r, c_g, c_b), "intensity": intensity}
        parsed_objects[dic_key] = node_data
        
    elif kind == 0: # Character
        print(f"Encountered Character at dic_key {dic_key}, skipping character internal card data...")
        # Since character card has binary ChaFileControl, we break the root loop or skip to next root
        parsed_objects[dic_key] = node_data
        return "CHARACTER_STOP"

try:
    for i in range(root_count):
        k = r_i(stream)
        kind = r_i(stream)
        res = parse_node(stream, kind, None)
        if res == "CHARACTER_STOP":
            print(f"Reached character at root index {i}.")
            break
except Exception as e:
    import traceback
    print(f"Error parsing node: {e}")
    traceback.print_exc()

print(f"Total objects successfully parsed from binary tree: {len(parsed_objects)}")
folders = [v for v in parsed_objects.values() if v["kind"] == 3]
items = [v for v in parsed_objects.values() if v["kind"] == 1]
print(f"  Folders: {len(folders)}")
print(f"  Items:   {len(items)}")

# Sample item check
if items:
    sample = items[0]
    print(f"Sample Item (dicKey {sample['dic_key']}):")
    print(f"  Group: {sample['group']}, Cat: {sample['category']}, No: {sample['no']}")
    print(f"  Pos:   {sample['pos']}")
    print(f"  Rot:   {sample['rot']}")
    print(f"  Scale: {sample['scale']}")
    print(f"  Parent Key: {sample['parent_key']}")
