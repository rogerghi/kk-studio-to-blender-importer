import zipfile
import UnityPy

zip_path = r"K:\KK\mods\NexusBDSM_Pack_v1.1.zipmod"

with zipfile.ZipFile(zip_path, "r") as z:
    bundle_name = "abdata/studio/BDSM_Pack.unity3d"
    print(f"Loading bundle: {bundle_name} with UnityPy...")
    bundle_data = z.read(bundle_name)
    env = UnityPy.load(bundle_data)
    
    objects = list(env.objects)
    print(f"Total objects in bundle: {len(objects)}")
    
    type_counts = {}
    for obj in objects:
        t = obj.type.name
        type_counts[t] = type_counts.get(t, 0) + 1
    print("Object types in bundle:", type_counts)
    
    # Inspect meshes
    for obj in objects:
        if obj.type.name == "Mesh":
            data = obj.read()
            print(f"\nSuccessfully read Mesh: '{data.name}'")
            print(f"  Vertices count: {len(data.m_Vertices)}")
            print(f"  Indices count : {len(data.m_Indices)}")
            # Let's inspect the first vertex
            if len(data.m_Vertices) > 0:
                print(f"  Sample vertex 0: ({data.m_Vertices[0].x}, {data.m_Vertices[0].y}, {data.m_Vertices[0].z})")
            break
