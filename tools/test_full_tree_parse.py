import struct, io, os

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
print(f"Version: {version}, Root Count: {root_count}")

nodes = {} # dic_key -> dict(kind, parent_key, pos, rot, scale, name)

def parse_ca(s):
    return {"pos": r_v3(s), "rot": r_v3(s), "scale": r_v3(s)}

def parse_obj_base(s):
    dic_key = r_i(s)
    ca = parse_ca(s)
    tree_state = r_i(s)
    visible = r_b(s)
    return dic_key, ca, visible

print("Successfully verified binary reader functions!")
