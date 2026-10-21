import os, sys, site
sys.path.append(site.getusersitepackages())
import UnityPy

kk_dir = r"K:\KK"
res_path = os.path.join(kk_dir, "CharaStudio_Data", "Resources", "unity default resources")
bpath = os.path.join(kk_dir, "abdata", "studio", "00.unity3d")

env = UnityPy.Environment()
env.load_file(res_path, name="unity default resources")
env.load_file(bpath)

# Let us find GameObject 'p_koi_stu_tesuri00_00'
for obj in env.objects:
    if obj.type.name == "GameObject":
        go = obj.read()
        if go.m_Name == "p_koi_stu_tesuri00_00":
            print(f"Found GameObject: {go.m_Name}")
            for comp in go.m_Components:
                c = comp.read()
                print(f"  Component: {c.type.name}")
            # Check transform & children
            trans = go.m_Transform.read()
            print(f"  Children count: {len(trans.m_Children)}")
            for child_ptr in trans.m_Children:
                child_trans = child_ptr.read()
                child_go = child_trans.m_GameObject.read()
                print(f"    Child: {child_go.m_Name}")
                for cc in child_go.m_Components:
                    cdata = cc.read()
                    print(f"      Comp: {cdata.type.name}")
                    if cdata.type.name == "MeshFilter":
                        mesh_ptr = getattr(cdata, "m_Mesh", None)
                        if mesh_ptr:
                            m = mesh_ptr.read()
                            print(f"        Mesh: {m.m_Name}, verts: {len(m.m_Vertices)}")
                    elif cdata.type.name == "MeshRenderer":
                        mats = getattr(cdata, "m_Materials", [])
                        for mat_ptr in mats:
                            mat = mat_ptr.read()
                            print(f"        Material: {mat.m_Name}")
                            # Inspect textures
                            if hasattr(mat, "m_SavedProperties"):
                                for tex_name, tex_val in getattr(mat.m_SavedProperties, "m_TexEnvs", []):
                                    tptr = tex_val.m_Texture
                                    if tptr:
                                        t = tptr.read()
                                        print(f"          Tex {tex_name}: {getattr(t, 'm_Name', 'unknown')}")
            break
