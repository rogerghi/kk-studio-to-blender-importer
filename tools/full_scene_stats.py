import msgpack, struct, re
from collections import Counter

file_path = r"K:\KK\UserData\Studio\scene\2026_0222_2203_14_452.png"

with open(file_path, "rb") as f:
    data = f.read()

total_bytes = len(data)

# PNG header & IEND
iend_pos = data.find(b"IEND") + 8
png_image_size = iend_pos
extra_size = total_bytes - iend_pos

# Embedded character cards
chara_cards = [m.start() for m in re.finditer(rb'\xe3\x80\x90KoiKatuChara\xe3\x80\x91', data)]

# ExtendedSave payload
extsave_pos = data.find(b"\xe3\x80\x90Studio\xe3\x80\x91\x04KKEx")
if extsave_pos == -1:
    extsave_pos = data.find(b'KKEx', 7000000)
else:
    extsave_pos += len(b"\xe3\x80\x90Studio\xe3\x80\x91")

f = open(file_path, "rb")
f.seek(extsave_pos + 4)
ver, length = struct.unpack("<II", f.read(8))
mp = f.read(length)
res = msgpack.unpackb(mp, raw=False, strict_map_key=False)

tnn = res.get('org.njaecha.plugins.treenodenaming', [])
names = {}
if len(tnn) > 1 and 'names' in tnn[1]:
    names = msgpack.unpackb(tnn[1]['names'], raw=False, strict_map_key=False)

uar = res.get('com.bepis.sideloader.universalautoresolver', [])
uar_items = []
uar_patterns = []
if len(uar) > 1:
    for raw_item in uar[1].get('itemInfo', []):
        uar_items.append(msgpack.unpackb(raw_item, raw=False, strict_map_key=False))
    for raw_pat in uar[1].get('patternInfo', []):
        uar_patterns.append(msgpack.unpackb(raw_pat, raw=False, strict_map_key=False))

mat_editor = res.get('com.deathweasel.bepinex.materialeditor', [])
embedded_textures_count = 0
if len(mat_editor) > 1 and 'TextureDictionary' in mat_editor[1]:
    td = msgpack.unpackb(mat_editor[1]['TextureDictionary'], raw=False, strict_map_key=False)
    embedded_textures_count = len(td)

# Group names into categories
folders = [n for n in names.values() if 'folder' in n.lower() or n in ['01', 'bondage', 'fixed', 'dai', 'circly', 'machine', 'Rotator']]
clean_counts = Counter()
for n in names.values():
    cn = re.sub(r'\s+\d+$', '', n)
    clean_counts[cn] += 1

print(f"=== SCENE FILE METRICS ===")
print(f"Total File Size: {total_bytes / (1024*1024):.2f} MB")
print(f"PNG Preview Image: {png_image_size / 1024:.2f} KB")
print(f"Serialized Payload: {extra_size / (1024*1024):.2f} MB")
print(f"Embedded Characters: {len(chara_cards)}")
print(f"Total Scene Hierarchy Nodes: {len(names)}")
print(f"Embedded Textures in MaterialEditor: {embedded_textures_count}")
print(f"Custom Modded Patterns: {len(uar_patterns)}")

print(f"\n=== TOP OBJECT CATEGORIES ===")
categories = {
    "Folders & Structure": 0,
    "Primitives (Cylinder, Cube, Sphere, etc.)": 0,
    "Mechanical & Kitbash (Piston, Rod, Pipe, etc.)": 0,
    "Modded Items (BDSM, Cables, Maps, etc.)": len(uar_items),
    "Others / Custom Named": 0
}

primitive_keywords = ['cylinder', 'cube', 'sphere', 'arc', 'hoop', 'ring', 'trapezoid', 'hemisphere', 'tube', 'capsule', 'hexagon', 'fin']
mech_keywords = ['rod', 'pipe', 'piston', 'mecha', 'joint', 'furball', 'shadow', 'chain']

for cn, count in clean_counts.items():
    lcn = cn.lower()
    if 'folder' in lcn:
        categories["Folders & Structure"] += count
    elif any(pk in lcn for pk in primitive_keywords):
        categories["Primitives (Cylinder, Cube, Sphere, etc.)"] += count
    elif any(mk in lcn for mk in mech_keywords):
        categories["Mechanical & Kitbash (Piston, Rod, Pipe, etc.)"] += count
    else:
        categories["Others / Custom Named"] += count

for cat, count in categories.items():
    print(f"  {cat:45s}: {count}")

print(f"\n=== MODS REQUIRED BY UAR ===")
mod_groups = Counter()
for it in uar_items:
    mod_groups[f"{it.get('Name')} (GUID/ModID: {it.get('ModID')})"] += 1
for pat in uar_patterns:
    mod_groups[f"Pattern: {pat.get('Name')} (GUID: {pat.get('GUID')})"] += 1

for mod, count in mod_groups.items():
    print(f"  [{count} items/patterns] {mod}")
