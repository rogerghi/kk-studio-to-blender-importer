import os
import json
import glob
import zipfile
import numpy as np
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


def rgb_to_lab(rgb_arr):
    """Vectorized sRGB [0..1] to CIELAB (L*, a*, b*)."""
    mask = rgb_arr > 0.04045
    rgb_lin = np.where(mask, np.power((rgb_arr + 0.055) / 1.055, 2.4), rgb_arr / 12.92)
    M = np.array([
        [0.4124564, 0.3575761, 0.1804375],
        [0.2126729, 0.7151522, 0.0721750],
        [0.0193339, 0.1191920, 0.9503041]
    ], dtype=np.float32)
    xyz = np.dot(rgb_lin, M.T)
    xyz[..., 0] /= 0.95047
    xyz[..., 1] /= 1.00000
    xyz[..., 2] /= 1.08883
    delta = 6.0 / 29.0
    f_xyz = np.where(xyz > (delta ** 3), np.cbrt(xyz), (xyz / (3 * delta ** 2)) + (4.0 / 29.0))
    L = 116.0 * f_xyz[..., 1] - 16.0
    a = 500.0 * (f_xyz[..., 0] - f_xyz[..., 1])
    b = 200.0 * (f_xyz[..., 1] - f_xyz[..., 2])
    return np.stack([L, a, b], axis=-1)


def lab_to_rgb(lab_arr):
    """Vectorized CIELAB to sRGB [0..1]."""
    L = lab_arr[..., 0]
    a = lab_arr[..., 1]
    b = lab_arr[..., 2]
    fY = (L + 16.0) / 116.0
    fX = fY + (a / 500.0)
    fZ = fY - (b / 200.0)
    delta = 6.0 / 29.0
    def inv_f(f_val):
        return np.where(f_val > delta, np.power(f_val, 3), 3 * (delta ** 2) * (f_val - 4.0 / 29.0))
    X = inv_f(fX) * 0.95047
    Y = inv_f(fY) * 1.00000
    Z = inv_f(fZ) * 1.08883
    xyz = np.stack([X, Y, Z], axis=-1)
    M_inv = np.array([
        [ 3.2404542, -1.5371385, -0.4985314],
        [-0.9692660,  1.8760108,  0.0415560],
        [ 0.0556434, -0.2040259,  1.0572252]
    ], dtype=np.float32)
    rgb_lin = np.dot(xyz, M_inv.T)
    rgb = np.where(rgb_lin > 0.0031308, 1.055 * np.power(np.maximum(rgb_lin, 0.0), 1.0 / 2.4) - 0.055, 12.92 * rgb_lin)
    return np.clip(rgb, 0.0, 1.0)


def apply_cielab_colormask(base_img_pil, mask_img_pil, colors):
    """
    Applies 3-channel ColorMask tinting in CIELAB space to preserve texture shading and contrast.
    colors: list of [r, g, b] floats (0.0 to 1.0) for [R-mask, G-mask, B-mask].
    """
    base_arr = np.array(base_img_pil.convert("RGBA"), dtype=np.float32)
    rgb = base_arr[..., :3] / 255.0
    alpha = base_arr[..., 3:4]

    c_arr = np.array(colors, dtype=np.float32)
    target_labs = rgb_to_lab(c_arr.reshape(1, 3, 3))[0]

    if mask_img_pil:
        mask_resized = mask_img_pil.convert("RGBA").resize(base_img_pil.size, Image.Resampling.BILINEAR)
        mask_arr = np.array(mask_resized, dtype=np.float32) / 255.0
        w_r = mask_arr[..., 0]
        w_g = mask_arr[..., 1]
        w_b = mask_arr[..., 2]
    else:
        w_r = np.ones((base_img_pil.size[1], base_img_pil.size[0]), dtype=np.float32)
        w_g = np.zeros_like(w_r)
        w_b = np.zeros_like(w_r)

    w_total = w_r + w_g + w_b
    w_sum = np.clip(w_total, 0.0, 1.0)[..., np.newaxis]

    base_lab = rgb_to_lab(rgb)
    L_base = base_lab[..., 0:1]
    a_base = base_lab[..., 1:2]
    b_base = base_lab[..., 2:3]

    safe_w = np.maximum(w_total[..., np.newaxis], 1e-5)
    target_a = (w_r[..., np.newaxis] * target_labs[0, 1] +
                w_g[..., np.newaxis] * target_labs[1, 1] +
                w_b[..., np.newaxis] * target_labs[2, 1]) / safe_w
    target_b = (w_r[..., np.newaxis] * target_labs[0, 2] +
                w_g[..., np.newaxis] * target_labs[1, 2] +
                w_b[..., np.newaxis] * target_labs[2, 2]) / safe_w
    target_L = (w_r[..., np.newaxis] * target_labs[0, 0] +
                w_g[..., np.newaxis] * target_labs[1, 0] +
                w_b[..., np.newaxis] * target_labs[2, 0]) / safe_w

    L_mod = np.clip(L_base * (target_L / 100.0), 0.0, 100.0)

    final_L = (1.0 - w_sum) * L_base + w_sum * L_mod
    final_a = (1.0 - w_sum) * a_base + w_sum * target_a
    final_b = (1.0 - w_sum) * b_base + w_sum * target_b

    final_lab = np.concatenate([final_L, final_a, final_b], axis=-1)
    final_rgb = lab_to_rgb(final_lab)

    out_arr = np.concatenate([final_rgb * 255.0, alpha], axis=-1).astype(np.uint8)
    return Image.fromarray(out_arr, mode="RGBA")


def get_cm3d2_toon_textures():
    toon_gray_path = None
    shadow_rate_path = None
    try:
        datafiles_dir = bpy.utils.user_resource('DATAFILES')
        candidate_dir = os.path.join(datafiles_dir, 'CM3D2 Converter', 'toon')
        if os.path.isdir(candidate_dir):
            p1 = os.path.join(candidate_dir, 'toongraya1.png')
            p2 = os.path.join(candidate_dir, 'toondress_shadow.png')
            if os.path.isfile(p1): toon_gray_path = p1
            if os.path.isfile(p2): shadow_rate_path = p2
    except Exception:
        pass
    return toon_gray_path, shadow_rate_path


def get_cm3d2_converter_module():
    try:
        import cm3d2_converter
        return cm3d2_converter
    except ImportError:
        pass

    try:
        ext_dir = bpy.utils.user_resource('EXTENSIONS')
        if ext_dir and os.path.exists(ext_dir):
            for root, dirs, _ in os.walk(ext_dir):
                if 'cm3d2_converter' in dirs:
                    if root not in sys.path:
                        sys.path.insert(0, root)
                    import cm3d2_converter
                    return cm3d2_converter
    except Exception:
        pass

    try:
        addons_dir = bpy.utils.user_resource('SCRIPTS', path="addons")
        candidate = os.path.join(addons_dir, "CM3D2 Converter")
        if os.path.isdir(candidate):
            if addons_dir not in sys.path:
                sys.path.insert(0, addons_dir)
            import cm3d2_converter
            return cm3d2_converter
    except Exception:
        pass

    return None


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

        self.cm3d2_converter = get_cm3d2_converter_module()
        self.toon_gray_img = None
        self.shadow_rate_img = None
        toon_p, shadow_p = get_cm3d2_toon_textures()
        if toon_p and os.path.exists(toon_p):
            try:
                self.toon_gray_img = bpy.data.images.load(toon_p, check_existing=True)
            except Exception:
                pass
        if shadow_p and os.path.exists(shadow_p):
            try:
                self.shadow_rate_img = bpy.data.images.load(shadow_p, check_existing=True)
            except Exception:
                pass

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
        """Creates a COM3D2-standard material with CIELAB ColorMask tinting and CM3D2 Converter nodes."""
        c1 = [1.0, 1.0, 1.0]
        c2 = [1.0, 1.0, 1.0]
        c3 = [1.0, 1.0, 1.0]
        if colors:
            for idx, c_arr in enumerate([c1, c2, c3]):
                if idx < len(colors) and colors[idx]:
                    try:
                        c_json = json.loads(colors[idx]) if isinstance(colors[idx], str) else colors[idx]
                        c_arr[0] = float(c_json.get("r", 1.0))
                        c_arr[1] = float(c_json.get("g", 1.0))
                        c_arr[2] = float(c_json.get("b", 1.0))
                    except Exception:
                        pass

        is_tinted = any(abs(x - 1.0) > 0.01 for x in c1 + c2 + c3)
        if is_tinted:
            c1_hex = f"{int(c1[0]*255):02X}{int(c1[1]*255):02X}{int(c1[2]*255):02X}"
            c2_hex = f"{int(c2[0]*255):02X}{int(c2[1]*255):02X}{int(c2[2]*255):02X}"
            c3_hex = f"{int(c3[0]*255):02X}{int(c3[1]*255):02X}{int(c3[2]*255):02X}"
            tex_hash = f"{c1_hex}_{c2_hex}_{c3_hex}"
        else:
            tex_hash = "orig"

        mat_prefix = getattr(unity_mat, "m_Name", item_name) if unity_mat else item_name
        mat_name = f"M_{mat_prefix}_{tex_hash}"

        if mat_name in self.mat_cache:
            return self.mat_cache[mat_name]

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
        is_transparent = False
        if base_tex:
            try:
                base_name = getattr(base_tex, "m_Name", mat_prefix)
                img_filename = f"T_{base_name}_{tex_hash}.png"
                img_path = os.path.join(self.tex_cache_dir, img_filename)

                if os.path.exists(img_path):
                    try:
                        with Image.open(img_path) as chk_img:
                            if chk_img.mode == "RGBA":
                                extrema = chk_img.getextrema()
                                if extrema and len(extrema) >= 4 and extrema[3][0] < 250:
                                    is_transparent = True
                    except Exception:
                        pass
                else:
                    img_pil = base_tex.image.convert("RGBA")
                    if is_tinted:
                        mask_pil = color_mask_tex.image.convert("RGBA") if color_mask_tex else None
                        tinted_pil = apply_cielab_colormask(img_pil, mask_pil, [c1, c2, c3])
                        tinted_pil.save(img_path)
                        chk_arr = np.array(tinted_pil)
                        if bool(np.any(chk_arr[..., 3] < 250)):
                            is_transparent = True
                    else:
                        img_pil.save(img_path)
                        chk_arr = np.array(img_pil)
                        if bool(np.any(chk_arr[..., 3] < 250)):
                            is_transparent = True

                b_img = bpy.data.images.load(img_path, check_existing=True)
            except Exception as e:
                print(f"[KK Importer] Texture process error for {mat_name}: {e}")

        # Determine COM shader
        if is_transparent:
            shader1 = "CM3D2/Toony_Lighted_Trans"
            shader2 = "CM3D2__Toony_Lighted_Trans"
        else:
            shader1 = "CM3D2/Toony_Lighted"
            shader2 = "CM3D2__Toony_Lighted"

        mat = bpy.data.materials.new(name=mat_name)
        mat.use_nodes = True
        mat["shader1"] = shader1
        mat["shader2"] = shader2
        mat["CM3D2 Texture Expand"] = True
        mat["COM3D2 Shader Rev"] = 1

        nodes = mat.node_tree.nodes
        links = mat.node_tree.links
        nodes.clear()

        def add_tex_node(name, img=None, loc=(-800, 0)):
            n = nodes.new("ShaderNodeTexImage")
            n.name = name
            n.label = name
            n.location = loc
            if img: n.image = img
            return n

        def add_col_node(name, color, loc=(-550, 0)):
            n = nodes.new("ShaderNodeRGB")
            n.name = name
            n.label = name
            n.location = loc
            n.outputs[0].default_value = color
            return n

        def add_val_node(name, val, loc=(-350, 0)):
            n = nodes.new("ShaderNodeValue")
            n.name = name
            n.label = name
            n.location = loc
            n.outputs[0].default_value = val
            return n

        main_tex_node = add_tex_node("_MainTex", b_img, loc=(-800, 300))
        add_tex_node("_ShadowTex", b_img, loc=(-800, 0))

        if self.toon_gray_img:
            add_tex_node("_ToonRamp", self.toon_gray_img, loc=(-800, -300))
        if self.shadow_rate_img:
            add_tex_node("_ShadowRateToon", self.shadow_rate_img, loc=(-800, -600))

        add_col_node("_Color", (1.0, 1.0, 1.0, 1.0), loc=(-550, 400))
        add_col_node("_ShadowColor", (0.7, 0.7, 0.7, 1.0), loc=(-550, 200))
        add_col_node("_RimColor", (0.0, 0.0, 0.0, 0.0), loc=(-550, 0))
        add_col_node("_OutlineColor", (0.16, 0.16, 0.16, 1.0), loc=(-550, -200))

        add_val_node("_Shininess", 0.0, loc=(-350, 400))
        add_val_node("_OutlineWidth", 0.002, loc=(-350, 200))
        add_val_node("_RimPower", 25.0, loc=(-350, 0))
        add_val_node("_RimShift", 0.0, loc=(-350, -200))
        add_val_node("_HiRate", 0.0, loc=(-350, -400))
        add_val_node("_HiPow", 0.0, loc=(-350, -600))

        decorated = False
        if self.cm3d2_converter:
            try:
                self.cm3d2_converter.common.decorate_material(mat, True)
                decorated = True
            except Exception:
                pass

        if not decorated:
            out_node = nodes.new("ShaderNodeOutputMaterial")
            out_node.location = (300, 0)
            bsdf = nodes.new("ShaderNodeBsdfPrincipled")
            bsdf.location = (0, 0)
            links.new(bsdf.outputs["BSDF"], out_node.inputs["Surface"])
            if b_img:
                links.new(main_tex_node.outputs["Color"], bsdf.inputs["Base Color"])
                if is_transparent and "Alpha" in main_tex_node.outputs:
                    links.new(main_tex_node.outputs["Alpha"], bsdf.inputs["Alpha"])
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
