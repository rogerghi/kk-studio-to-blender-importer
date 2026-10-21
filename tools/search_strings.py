import re

file_path = r"K:\KK\UserData\Studio\scene\2026_0222_2203_14_452.png"

with open(file_path, "rb") as f:
    data = f.read()

# Let's search for ASCII strings of length >= 4
matches = re.finditer(b"([a-zA-Z0-9_\-\.\/]{4,})", data)
interesting = []
for m in matches:
    s = m.group(1).decode("ascii", errors="ignore")
    # Filter for things that look like studio items, assetbundles, zipmods, plugins
    if any(k in s.lower() for k in ["unity3d", "studio", "item", "prop", "bepinex", "extsave", "chafile", "png", "scene"]):
        interesting.append((m.start(), s))

print(f"Total interesting strings found: {len(interesting)}")
for pos, s in interesting[:50]:
    print(f"[{pos}] {s}")
if len(interesting) > 50:
    print("...")
    for pos, s in interesting[-30:]:
        print(f"[{pos}] {s}")
