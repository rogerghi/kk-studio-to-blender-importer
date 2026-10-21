import msgpack, struct

f = open(r'K:\KK\UserData\Studio\scene\2026_0222_2203_14_452.png', 'rb')
f.seek(7106674+4)
ver, length = struct.unpack('<II', f.read(8))
mp = f.read(length)
res = msgpack.unpackb(mp, raw=False)

uar = res.get('com.bepis.sideloader.universalautoresolver')
print(f"UAR length: {len(uar)}")
for i, item in enumerate(uar):
    print(f"Item {i}: type={type(item)}")
    if isinstance(item, dict):
        for k, v in item.items():
            if isinstance(v, list):
                print(f"  {k}: list of len {len(v)}")
                if len(v) > 0:
                    print(f"    sample[0]: {type(v[0])}")
                    if isinstance(v[0], bytes):
                        # try unpack msgpack if it's nested msgpack
                        try:
                            unp = msgpack.unpackb(v[0], raw=False)
                            print(f"    sample[0] unpacked: {unp}")
                        except Exception as e:
                            print(f"    sample[0] raw bytes: {v[0][:50]}")
            else:
                print(f"  {k}: {v}")
