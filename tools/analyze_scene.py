import msgpack, struct
from collections import Counter

file_path = r"K:\KK\UserData\Studio\scene\2026_0222_2203_14_452.png"
f = open(file_path, 'rb')
f.seek(7106674+4)
ver, length = struct.unpack('<II', f.read(8))
mp = f.read(length)
res = msgpack.unpackb(mp, raw=False, strict_map_key=False)

tnn = res.get('org.njaecha.plugins.treenodenaming')
names = {}
if tnn and len(tnn) > 1 and 'names' in tnn[1]:
    names = msgpack.unpackb(tnn[1]['names'], raw=False, strict_map_key=False)

uar = res.get('com.bepis.sideloader.universalautoresolver')
uar_items = []
uar_patterns = []
if uar and len(uar) > 1:
    for raw_item in uar[1].get('itemInfo', []):
        uar_items.append(msgpack.unpackb(raw_item, raw=False))
    for raw_pat in uar[1].get('patternInfo', []):
        uar_patterns.append(msgpack.unpackb(raw_pat, raw=False, strict_map_key=False))

print(f"Total objects in TreeNodeNaming: {len(names)}")
print(f"Total modded items in UAR: {len(uar_items)}")
print(f"Total modded patterns in UAR: {len(uar_patterns)}")

# Count name patterns/groups
name_counts = Counter()
import re
for dic_key, name in names.items():
    # strip trailing numbers (e.g., 'Cylinder (General) 12' -> 'Cylinder (General)')
    clean_name = re.sub(r'\s+\d+$', '', name)
    name_counts[clean_name] += 1

print("\n--- Top Object Types / Names in Scene ---")
for name, count in name_counts.most_common(35):
    print(f"  {name:35s}: {count:4d}")

print("\n--- Modded Items (UAR) ---")
for it in uar_items:
    print(f"  DicKey {it.get('SceneDicKey')}: ModID='{it.get('ModID')}', Name='{it.get('Name')}', Slot={it.get('Slot')}")

