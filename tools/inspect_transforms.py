import struct, io, json

file_path = r"K:\KK\UserData\Studio\scene\2026_0222_2203_14_452.png"

with open(file_path, "rb") as f:
    data = f.read()

iend_pos = data.find(b"IEND") + 8
stream = io.BytesIO(data[iend_pos:])

def read_string(s):
    # .NET BinaryReader 7-bit encoded int length
    length = 0
    shift = 0
    while True:
        b = s.read(1)[0]
        length |= (b & 0x7F) << shift
        if (b & 0x80) == 0:
            break
        shift += 7
    return s.read(length).decode("utf-8", errors="ignore")

def read_vec3(s):
    return struct.unpack("<fff", s.read(12))

def read_bool(s):
    return struct.unpack("<?", s.read(1))[0]

def read_int(s):
    return struct.unpack("<i", s.read(4))[0]

def read_float(s):
    return struct.unpack("<f", s.read(4))[0]

version = read_string(stream)
print(f"Data Version: {version}")
root_count = read_int(stream)
print(f"Root object count: {root_count}")

# Let's inspect the first root object and its children
def parse_change_amount(s):
    pos = read_vec3(s)
    rot = read_vec3(s)
    scale = read_vec3(s)
    return {"pos": pos, "rot": rot, "scale": scale}

def parse_object_info(s):
    dic_key = read_int(s)
    ca = parse_change_amount(s)
    tree_state = read_int(s)
    visible = read_bool(s)
    return {"dic_key": dic_key, "ca": ca, "tree_state": tree_state, "visible": visible}

for r in range(min(root_count, 3)):
    key = read_int(stream)
    kind = read_int(stream)
    base = parse_object_info(stream)
    print(f"\nRoot {r}: key={key}, kind={kind}, dic_key={base['dic_key']}")
    print(f"  Pos:   {base['ca']['pos']}")
    print(f"  Rot:   {base['ca']['rot']}")
    print(f"  Scale: {base['ca']['scale']}")
    print(f"  Visible: {base['visible']}")
    if kind == 3: # Folder
        name = read_string(stream)
        child_count = read_int(stream)
        print(f"  Folder Name: '{name}', Children: {child_count}")
        # Parse first child
        if child_count > 0:
            ckind = read_int(stream)
            cbase = parse_object_info(stream)
            print(f"    Child 0: kind={ckind}, dic_key={cbase['dic_key']}")
            print(f"      Pos:   {cbase['ca']['pos']}")
            print(f"      Rot:   {cbase['ca']['rot']}")
            print(f"      Scale: {cbase['ca']['scale']}")
    break
