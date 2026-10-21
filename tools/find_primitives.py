import glob, os, UnityPy

studio_dir = r"K:\KK\abdata\studio"
bundles = glob.glob(os.path.join(studio_dir, "*.unity3d"))

print(f"Searching {len(bundles)} studio bundles for primitives...")
found = {}
for bpath in bundles:
    bname = os.path.basename(bpath)
    try:
        env = UnityPy.load(bpath)
        for obj in env.objects:
            if obj.type.name == "Mesh":
                m = obj.read()
                name = m.m_Name.lower()
                for kw in ["cylinder", "sphere", "cube", "hoop", "arc", "capsule", "trapezoid", "ring"]:
                    if kw in name:
                        if kw not in found:
                            found[kw] = []
                        if len(found[kw]) < 3:
                            found[kw].append((bname, m.m_Name))
    except Exception as e:
        pass

for kw, items in found.items():
    print(f"\nKeyword '{kw}':")
    for bname, mname in items:
        print(f"  [{bname}] {mname}")
