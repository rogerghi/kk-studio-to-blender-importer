import struct
import msgpack

file_path = r"K:\KK\UserData\Studio\scene\2026_0222_2203_14_452.png"

with open(file_path, "rb") as f:
    data = f.read()

offset = 7106674
# b'\x04KKEx\x03\x00\x00\x00c\xc4\xa0\x00...'
magic = data[offset:offset+5] # \x04KKEx
version, length = struct.unpack("<II", data[offset+5:offset+13])
print(f"Magic: {magic}, Version: {version}, Length: {length}")

mp_data = data[offset+13 : offset+13+length]
unpacked = msgpack.unpackb(mp_data, raw=False)
print(f"Plugins in scene ExtendedSave ({len(unpacked)}):")
for k, v in unpacked.items():
    print(f"  Plugin: {k}")
    if isinstance(v, dict):
        for sub_k, sub_v in v.items():
            if sub_k == "data" and isinstance(sub_v, dict):
                print(f"    data keys: {list(sub_v.keys())}")
            else:
                print(f"    {sub_k}: {type(sub_v)}")
