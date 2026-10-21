import msgpack, struct

with open(r'K:\KK\UserData\Studio\scene\2026_0222_2203_14_452.png', 'rb') as f:
    data = f.read()

offsets = [666222, 6198125]
for i, off in enumerate(offsets):
    print(f"\n--- Character {i+1} at offset {off} ---")
    chunk = data[off:off+2000]
    # In Koikatu cards: 【KoiKatuChara】 followed by version, product_no, etc.
    # ChaFile has block header info
    # Let's search for Parameter or name
    # ChaFile uses msgpack or BlockHeader
    import re
    # find names in block
    for m in re.finditer(rb'firstname\xa[0-9a-f]([^\x00-\x1f]+)|lastname\xa[0-9a-f]([^\x00-\x1f]+)', data[off:off+100000]):
        print(m.group(0))
