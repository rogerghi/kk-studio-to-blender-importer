import os
import json
import glob
import zipfile
import bpy
from mathutils import Matrix, Vector, Quaternion

import site
import sys
site_packages = site.getusersitepackages()
if site_packages not in sys.path:
    sys.path.append(site_packages)

try:
    import UnityPy
    from PIL import Image
except ImportError as e:
    print(f"[KK Studio Importer ERROR] Failed to import UnityPy/PIL in mesh_loader: {e}")

class KKMeshLoader:
    def __init__(self, kk_dir: str, use_fallback_cubes: bool = False):
        self.kk_dir = kk_dir
        self.use_fallback_cubes = use_fallback_cubes
        self.bundle_cache = {} # cache_key -> {"gos": {name_lower: [go, ...]}, "textures": {name_lower: tex}, "meshes": {name_lower: mesh}}
        self.mesh_cache = {}   # cache_key -> bpy.types.Mesh
        self.mat_cache = {}    # mat_key -> bpy.types.Material
        self.shared_env = None

        addon_dir = os.path.dirname(os.path.abspath(__file__))
        self.tex_cache_dir = os.path.join(addon_dir, "cache", "textures")
        os.makedirs(self.tex_cache_dir, exist_ok=True)

    def _get_shared_env(self):
        """Loads shared studio/mat bundles so cross-bundle materials and textures resolve properly."""
        if self.shared_env is not None:
            return self.shared_env

        env = UnityPy.Environment()
        res_path = os.path.join(self.kk_dir, "CharaStudio_Data", "Resources", "unity default resources")
        if os.path.exists(res_path):
            try:
                env.load_file(res_path, name="unity default resources")
            except Exception:
                pass

        mat_dir = os.path.join(self.kk_dir, "abdata", "studio", "mat")
        if os.path.isdir(mat_dir):
            for mfile in glob.glob(os.path.join(mat_dir, "*.unity3d")):
                try:
                    env.load_file(mfile)
                except Exception:
                    pass

        self.shared_env = env
        return self.shared_env

    def _get_bundle_index(self, item_info: dict):
        bundle_rel = item_info["bundle"]
        cache_key = f"{item_info.get('source')}:{item_info.get('zipmod', '')}:{bundle_rel}"
        if cache_key in self.bundle_cache:
            return self.bundle_cache[cache_key]

        bundle_data = None
        if item_info.get("source") == "zipmod" and "zipmod" in item_info:
            try:
                with zipfile.ZipFile(item_info["zipmod"], "r") as z:
                    for name in z.namelist():
                        if name.endswith(bundle_rel.replace("\\", "/")) or bundle_rel.replace("\\", "/") in name:
                            bundle_data = z.read(name)
                            break
            except Exception:
                pass
        else:
            full_path = os.path.join(self.kk_dir, "abdata", bundle_rel)
            if os.path.exists(full_path):
                try:
                    with open(full_path, "rb") as f:
                        bundle_data = f.read()
                except Exception:
                    pass

        if not bundle_data:
            return None

        try:
            shared_env = self._get_shared_env()
            if shared_env:
                env = shared_env
                env.load_file(bundle_data, name=bundle_rel)
            else:
                env = UnityPy.load(bundle_data)
        except Exception:
            try:
                env = UnityPy.load(bundle_data)
            except Exception:
                return None

        gos_map = {}
        meshes_map = {}
        tex_map = {}

        for obj in env.objects:
            if obj.type.name == "GameObject":
                try:
                    go = obj.read()
                    gos_map.setdefault(go.m_Name.lower(), []).append(go)
                except Exception:
                    pass
            elif obj.type.name == "Mesh":
                try:
                    m = obj.read()
                    meshes_map[m.m_Name.lower()] = m
                except Exception:
                    pass
            elif obj.type.name == "Texture2D":
                try:
                    t = obj.read()
                    tex_map[t.m_Name.lower()] = t
                except Exception:
                    pass

        index = {
            "gos": gos_map,
            "meshes": meshes_map,
            "textures": tex_map
        }
        self.bundle_cache[cache_key] = index
        return index

    def get_meshes_and_materials(self, item_info: dict, colors: list = None):
        """
        Loads meshes and materials for an item.
        Returns a list of dicts: [{"name": subpart_name, "mesh": b_mesh, "material": b_mat}]
        Supports multi-mesh prefabs without merging!
        """
        prefab_name = item_info["prefab"]
        bundle_index = self._get_bundle_index(item_info)
        if not bundle_index:
            return []

        tex_map = bundle_index["textures"]
        extracted_parts = []

        def process_go(go, parent_mat=Matrix.Identity(4)):
            curr_mat = parent_mat
            mesh_filter_mesh = None
            for comp in getattr(go, "m_Components", []):
                try:
                    c = comp.read()
                    cname = c.__class__.__name__
                    if cname == "MeshFilter":
                        mesh_ptr = getattr(c, "m_Mesh", None)
                        if mesh_ptr:
                            mesh_filter_mesh = mesh_ptr.read()
                except Exception:
                    pass

            for comp in getattr(go, "m_Components", []):
                try:
                    c = comp.read()
                    cname = c.__class__.__name__
                    if cname in ["MeshFilter", "MeshRenderer", "SkinnedMeshRenderer"]:
                        if cname == "MeshFilter" and any(cc.read().__class__.__name__ in ["MeshRenderer", "SkinnedMeshRenderer"] for cc in getattr(go, "m_Components", [])):
                            continue

                        is_skinned = (cname == "SkinnedMeshRenderer")
                        if is_skinned:
                            mesh_ptr = getattr(c, "m_Mesh", None)
                            m = mesh_ptr.read() if mesh_ptr else None
                        else:
                            m = mesh_filter_mesh
                            if not m and hasattr(c, "m_Mesh"):
                                mesh_ptr = getattr(c, "m_Mesh", None)
                                m = mesh_ptr.read() if mesh_ptr else None

                        if not m:
                            continue

                        if is_skinned:
                            b_mesh = self._create_blender_mesh(m)
                            l_mat = curr_mat
                        else:
                            b_key = f"{prefab_name}_{getattr(go, 'm_Name', '')}_{m.m_Name}"
                            b_mesh = self._create_blender_mesh(m, mesh_key=b_key, transform_mat=curr_mat)
                            l_mat = Matrix.Identity(4)

                        if b_mesh is None:
                            continue

                        u_mat = None
                        if hasattr(c, "m_Materials") and c.m_Materials:
                            try:
                                u_mat = c.m_Materials[0].read()
                            except Exception:
                                pass

                        b_mat = self._create_blender_material(prefab_name, tex_map, colors, unity_mat=u_mat)
                        part = {
                            "name": getattr(go, "m_Name", m.m_Name),
                            "mesh": b_mesh,
                            "material": b_mat,
                            "local_matrix": l_mat
                        }
                        if is_skinned and getattr(c, "m_Bones", None):
                            ubones = [b.read() for b in c.m_Bones]
                            bnames = [b.m_GameObject.read().m_Name for b in ubones]
                            pmap = {}
                            for b in ubones:
                                bn = b.m_GameObject.read().m_Name
                                pb = b.m_Father.read() if getattr(b, 'm_Father', None) else None
                                pmap[bn] = pb.m_GameObject.read().m_Name if pb else None
                            bposes = []
                            for bp in getattr(m, "m_BindPose", []):
                                bposes.append((
                                    (bp.e00, bp.e01, bp.e02, bp.e03),
                                    (bp.e10, bp.e11, bp.e12, bp.e13),
                                    (bp.e20, bp.e21, bp.e22, bp.e23),
                                    (bp.e30, bp.e31, bp.e32, bp.e33)
                                ))
                            part["armature_data"] = {
                                "bone_names": bnames,
                                "parent_map": pmap,
                                "bind_poses": bposes,
                                "skin": getattr(m, "m_Skin", [])
                            }
                        extracted_parts.append(part)
                except Exception:
                    pass

            # Recursively traverse all children preserving local TRS!
            try:
                trans = go.m_Transform.read()
                for c_ptr in getattr(trans, "m_Children", []):
                    c_trans = c_ptr.read()
                    c_go = c_trans.m_GameObject.read()
                    pos = c_trans.m_LocalPosition
                    rot = c_trans.m_LocalRotation
                    scale = c_trans.m_LocalScale
                    
                    T = Matrix.Translation(Vector((-pos.x, pos.y, pos.z)))
                    q = Quaternion((rot.w, rot.x, -rot.y, -rot.z))
                    R = q.to_matrix().to_4x4()
                    S = Matrix.Diagonal(Vector((scale.x, scale.y, scale.z, 1.0)))
                    c_mat = parent_mat @ (T @ R @ S)
                    process_go(c_go, c_mat)
            except Exception:
                pass

        # 1. Exact match in indexed GameObjects
        target_gos = bundle_index["gos"].get(prefab_name.lower(), [])

        # 2. Substring match in indexed GameObjects if exact match not found
        if not target_gos:
            for gname, gos in bundle_index["gos"].items():
                if prefab_name.lower() in gname or gname in prefab_name.lower():
                    target_gos.extend(gos)

        for go in target_gos:
            process_go(go)

        # 3. Fallback: only if a mesh specifically matches the prefab name
        if not extracted_parts:
            for m_name, m in bundle_index["meshes"].items():
                if prefab_name.lower() in m_name or m_name in prefab_name.lower():
                    b_mesh = self._create_blender_mesh(m)
                    if b_mesh is not None:
                        b_mat = self._create_blender_material(prefab_name, tex_map, colors)
                        extracted_parts.append({
                            "name": m.m_Name,
                            "mesh": b_mesh,
                            "material": b_mat,
                            "local_matrix": Matrix.Identity(4)
                        })
                        break

        return extracted_parts

    def _create_blender_mesh(self, unity_mesh, mesh_key=None, transform_mat=None):
        name_key = mesh_key if mesh_key else unity_mesh.m_Name
        if name_key in self.mesh_cache:
            return self.mesh_cache[name_key]

        try:
            obj_str = unity_mesh.export()
        except Exception:
            if self.use_fallback_cubes:
                return self.create_fallback_cube(name_key)
            return None

        verts, uvs, faces = [], [], []
        for line in obj_str.splitlines():
            if line.startswith("v "):
                p = line.split()
                verts.append((float(p[1]), float(p[2]), float(p[3])))
            elif line.startswith("vt "):
                p = line.split()
                uvs.append((float(p[1]), float(p[2])))
            elif line.startswith("f "):
                face = [int(p.split("/")[0]) - 1 for p in line.split()[1:]]
                faces.append(face)

        mesh_data = bpy.data.meshes.new(name_key)
        mesh_data.from_pydata(verts, [], faces)
        if transform_mat and transform_mat != Matrix.Identity(4):
            mesh_data.transform(transform_mat)
        mesh_data.update()

        if uvs and len(mesh_data.polygons) > 0:
            uv_layer = mesh_data.uv_layers.new(name="UVMap")
            loop_idx = 0
            for poly in mesh_data.polygons:
                for v_idx in poly.vertices:
                    if loop_idx < len(uv_layer.data) and v_idx < len(uvs):
                        uv_layer.data[loop_idx].uv = uvs[v_idx]
                    loop_idx += 1

        self.mesh_cache[name_key] = mesh_data
        return mesh_data

    def _create_blender_material(self, item_name: str, tex_map: dict, colors: list, unity_mat=None):
        """Creates a COM3D2-ready Principled BSDF material with accurate ColorMask tinting."""
        c1 = [1.0, 1.0, 1.0]
        c2 = [1.0, 1.0, 1.0]
        c3 = [1.0, 1.0, 1.0]
        if colors:
            for idx, c_arr in enumerate([c1, c2, c3]):
                if idx < len(colors) and colors[idx]:
                    try:
                        c_json = json.loads(colors[idx])
                        c_arr[0] = float(c_json.get("r", 1.0))
                        c_arr[1] = float(c_json.get("g", 1.0))
                        c_arr[2] = float(c_json.get("b", 1.0))
                    except Exception:
                        pass

        mat_prefix = getattr(unity_mat, "m_Name", item_name) if unity_mat else item_name
        color_hash = f"{c1[0]:.2f}_{c1[1]:.2f}_{c1[2]:.2f}_{c2[0]:.2f}_{c2[1]:.2f}_{c2[2]:.2f}"
        mat_name = f"M_{mat_prefix}_{color_hash}"

        if mat_name in self.mat_cache:
            return self.mat_cache[mat_name]

        mat = bpy.data.materials.new(name=mat_name)
        mat.use_nodes = True
        nodes = mat.node_tree.nodes
        links = mat.node_tree.links
        nodes.clear()

        # Set custom properties for CM3D2 Converter export
        mat["shader1"] = "CM3D2/Toony_Lighted"
        mat["shader2"] = "CM3D2__Toony_Lighted"

        output_node = nodes.new(type="ShaderNodeOutputMaterial")
        output_node.location = (300, 0)
        bsdf = nodes.new(type="ShaderNodeBsdfPrincipled")
        bsdf.location = (0, 0)
        links.new(bsdf.outputs["BSDF"], output_node.inputs["Surface"])

        base_tex = None
        color_mask_tex = None
        if unity_mat and hasattr(unity_mat, "m_SavedProperties"):
            sp = unity_mat.m_SavedProperties
            for t_k, t_v in getattr(sp, "m_TexEnvs", []):
                if t_k == "_MainTex" and t_v.m_Texture:
                    try: base_tex = t_v.m_Texture.read()
                    except Exception: pass
                elif t_k == "_ColorMask" and t_v.m_Texture:
                    try: color_mask_tex = t_v.m_Texture.read()
                    except Exception: pass

        if not base_tex:
            def is_aux_texture(name):
                nl = name.lower()
                return any(k in nl for k in ["_n", "_norm", "normal", "bump", "noise", "wave", "spec", "mask", "colormask", "_mc", "emission"])

            # 1. Prioritize diffuse texture matching item name
            for tname, tex in tex_map.items():
                if not is_aux_texture(tname) and item_name.lower() in tname:
                    base_tex = tex
                    break

            # 2. Otherwise pick any valid diffuse texture in bundle that is not a normal/noise/mask map
            if not base_tex:
                for tname, tex in tex_map.items():
                    if not is_aux_texture(tname):
                        base_tex = tex
                        break

        b_img = None
        if base_tex:
            try:
                img_pil = base_tex.image.convert("RGBA")
                is_tinted = any(abs(x - 1.0) > 0.01 for x in c1 + c2 + c3)

                if is_tinted and color_mask_tex:
                    mask_pil = color_mask_tex.image.convert("RGBA").resize(img_pil.size, Image.NEAREST)
                    main_data = img_pil.load()
                    mask_data = mask_pil.load()
                    w, h = img_pil.size
                    for y in range(h):
                        for x in range(w):
                            mr, mg, mb, _ = mask_data[x, y]
                            pr, pg, pb, pa = main_data[x, y]
                            r_w = mr / 255.0
                            g_w = mg / 255.0
                            b_w = mb / 255.0
                            base_w = max(0.0, 1.0 - (r_w + g_w + b_w))

                            tf_r = base_w + r_w * c1[0] + g_w * c2[0] + b_w * c3[0]
                            tf_g = base_w + r_w * c1[1] + g_w * c2[1] + b_w * c3[1]
                            tf_b = base_w + r_w * c1[2] + g_w * c2[2] + b_w * c3[2]

                            nr = int(min(255, max(0, pr * tf_r)))
                            ng = int(min(255, max(0, pg * tf_g)))
                            nb = int(min(255, max(0, pb * tf_b)))
                            main_data[x, y] = (nr, ng, nb, pa)

                    img_filename = f"{mat_name}.png"
                    img_path = os.path.join(self.tex_cache_dir, img_filename)
                    img_pil.save(img_path)
                elif is_tinted:
                    r, g, b, a = img_pil.split()
                    r = r.point(lambda i: int(min(255, i * c1[0])))
                    g = g.point(lambda i: int(min(255, i * c1[1])))
                    b = b.point(lambda i: int(min(255, i * c1[2])))
                    tinted_pil = Image.merge("RGBA", (r, g, b, a))
                    img_filename = f"{mat_name}.png"
                    img_path = os.path.join(self.tex_cache_dir, img_filename)
                    tinted_pil.save(img_path)
                else:
                    img_filename = f"T_{base_tex.m_Name}.png"
                    img_path = os.path.join(self.tex_cache_dir, img_filename)
                    if not os.path.exists(img_path):
                        img_pil.save(img_path)

                b_img = bpy.data.images.load(img_path, check_existing=True)
            except Exception as e:
                print(f"[KK Importer] Texture process error for {mat_name}: {e}")

        tex_node = nodes.new(type="ShaderNodeTexImage")
        tex_node.name = "_MainTex"
        tex_node.label = "_MainTex"
        tex_node.location = (-350, 0)
        if b_img:
            tex_node.image = b_img
            links.new(tex_node.outputs["Color"], bsdf.inputs["Base Color"])
            if "Alpha" in bsdf.inputs and "Alpha" in tex_node.outputs:
                links.new(tex_node.outputs["Alpha"], bsdf.inputs["Alpha"])
        else:
            bsdf.inputs["Base Color"].default_value = (c1[0], c1[1], c1[2], 1.0)

        self.mat_cache[mat_name] = mat
        return mat

    def create_fallback_cube(self, name: str):
        mesh_name = f"Placeholder_{name}"
        if mesh_name in self.mesh_cache:
            return self.mesh_cache[mesh_name]
        mesh_data = bpy.data.meshes.new(mesh_name)
        verts = [(-0.5,-0.5,-0.5), (0.5,-0.5,-0.5), (0.5,0.5,-0.5), (-0.5,0.5,-0.5),
                 (-0.5,-0.5,0.5), (0.5,-0.5,0.5), (0.5,0.5,0.5), (-0.5,0.5,0.5)]
        faces = [(0,1,2,3), (4,7,6,5), (0,4,5,1), (1,5,6,2), (2,6,7,3), (4,0,3,7)]
        mesh_data.from_pydata(verts, [], faces)
        mesh_data.update()
        self.mesh_cache[mesh_name] = mesh_data
        return mesh_data
