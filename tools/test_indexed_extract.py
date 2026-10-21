import os, time, UnityPy

kk_dir = r"K:\KK"
bundle_path = os.path.join(kk_dir, "abdata", "studio", "00.unity3d")

t0 = time.time()
env = UnityPy.load(bundle_path)
print(f"Loaded bundle in {time.time() - t0:.2f}s")

# Index bundle
gos_map = {}
meshes_map = {}
tex_map = {}

t0 = time.time()
for obj in env.objects:
    if obj.type.name == "GameObject":
        go = obj.read()
        gos_map.setdefault(go.m_Name.lower(), []).append(go)
    elif obj.type.name == "Mesh":
        m = obj.read()
        meshes_map[m.m_Name.lower()] = m
    elif obj.type.name == "Texture2D":
        t = obj.read()
        tex_map[t.m_Name.lower()] = t

print(f"Indexed bundle in {time.time() - t0:.2f}s: {len(gos_map)} GOs, {len(meshes_map)} Meshes, {len(tex_map)} Textures")

def get_parts(prefab_name):
    extracted = []
    targets = gos_map.get(prefab_name.lower(), [])
    
    def process_go(go):
        for comp in getattr(go, "m_Components", []):
            try:
                c = comp.read()
                if c.__class__.__name__ in ["MeshFilter", "SkinnedMeshRenderer"]:
                    mesh_ptr = getattr(c, "m_Mesh", None)
                    if mesh_ptr:
                        m = mesh_ptr.read()
                        extracted.append((go.m_Name, m.m_Name))
            except Exception:
                pass
        try:
            trans = go.m_Transform.read()
            for c_ptr in getattr(trans, "m_Children", []):
                process_go(c_ptr.read().m_GameObject.read())
        except Exception:
            pass

    for go in targets:
        process_go(go)

    if not extracted:
        # Fallback to mesh name
        for m_name, m in meshes_map.items():
            if prefab_name.lower() in m_name or m_name in prefab_name.lower():
                extracted.append(("FallbackMesh", m.m_Name))
                break

    return extracted

test_prefabs = [
    "p_koi_stu_cube01_02",
    "p_koi_stu_cylinder01_02",
    "p_koi_stu_gtable00_00",
    "p_koi_stu_reel00_00"
]

for p in test_prefabs:
    t1 = time.time()
    parts = get_parts(p)
    dt = (time.time() - t1) * 1000
    print(f"Prefab '{p}' -> {len(parts)} parts in {dt:.3f}ms:")
    for go_name, m_name in parts:
        print(f"   GO: {go_name} -> Mesh: {m_name}")
