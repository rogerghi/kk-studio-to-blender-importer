import msgpack, struct

f = open(r'K:\KK\UserData\Studio\scene\2026_0222_2203_14_452.png', 'rb')
f.seek(7106674+4)
ver, length = struct.unpack('<II', f.read(8))
mp = f.read(length)
res = msgpack.unpackb(mp, raw=False)

uar = res.get('com.bepis.sideloader.universalautoresolver')
print("UAR structure:")
if isinstance(uar, dict):
    for k, v in uar.items():
        if k == 'data' and isinstance(v, dict):
            print("  data keys:", list(v.keys()))
            for dk, dv in v.items():
                if isinstance(dv, (list, dict)):
                    print(f"    {dk}: type {type(dv)}, len {len(dv)}")
                else:
                    print(f"    {dk}: {dv}")
        else:
            print(f"  {k}: {type(v)}")
