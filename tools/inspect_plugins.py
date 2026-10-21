import msgpack, struct

f = open(r'K:\KK\UserData\Studio\scene\2026_0222_2203_14_452.png', 'rb')
f.seek(7106674+4)
ver, length = struct.unpack('<II', f.read(8))
mp = f.read(length)
res = msgpack.unpackb(mp, raw=False)

for k in ['org.njaecha.plugins.treenodenaming', 'com.deathweasel.bepinex.materialeditor', 'rendererEditor']:
    val = res.get(k)
    print(f"=== {k} ===")
    print("type:", type(val))
    if isinstance(val, (dict, list)):
        print("len:", len(val))
        print("sample:", repr(val)[:500])
