bl_info = {
    "name": "Koikatsu Studio Scene Importer",
    "author": "rinasaurus",
    "version": (1, 4, 3),
    "blender": (3, 0, 0),
    "location": "3D Viewport > Sidebar (N) > KK Studio",
    "description": "Imports Koikatsu Studio scene cards into Blender without characters, preserving exact hierarchy, transforms, multi-part meshes, and tinted textures for COM3D2 export.",
    "category": "Import-Export",
}

import site, sys, os
sys.path.append(site.getusersitepackages())

import bpy
import struct
import io
import re
import glob
import json
import zipfile
import math
import time
from mathutils import Matrix, Vector, Quaternion, Euler
from bpy.props import StringProperty, BoolProperty

try:
    import msgpack
    import UnityPy
    from PIL import Image
    DEPS_LOADED = True
except ImportError:
    DEPS_LOADED = False


# =========================================================================
# 1. Coordinate & Transform Conversion (Unity -> Blender)
# =========================================================================

def unity_trs_matrix(pos: tuple, rot_deg: tuple, scale: tuple) -> Matrix:
    """Computes exact Unity local TRS affine transformation matrix in right-handed space (X-mirrored)."""
    rx = math.radians(rot_deg[0])
    ry = math.radians(-rot_deg[1])
    rz = math.radians(-rot_deg[2])
    # Intrinsic ZXY rotation order in reflected space
    q = Euler((rx, ry, rz), 'ZXY').to_quaternion()
    
    T = Matrix.Translation(Vector((-pos[0], pos[1], pos[2])))
    R = q.to_matrix().to_4x4()
    S = Matrix.Diagonal(Vector((scale[0], scale[1], scale[2], 1.0)))
    return T @ R @ S



# =========================================================================
# 2. Vanilla & Zipmod Item Database Resolver (with Disk Caching)
# =========================================================================

class KKItemResolver:
    _instance = None

    def __init__(self, kk_dir: str):
        self.kk_dir = kk_dir
        self.item_index = {}       # "group_category_no" -> dict(bundle, prefab, name)
        self.name_index = {}       # prefab_name.lower() -> dict(bundle, prefab, name)
        self.zipmod_index = {}     # guid -> zipmod_path
        self.zipmod_items = {}     # (guid, slot) -> dict(bundle, prefab, name)
        self.is_indexed = False
        addon_dir = os.path.dirname(os.path.abspath(__file__))
        self.cache_dir = os.path.join(addon_dir, "cache")
        os.makedirs(self.cache_dir, exist_ok=True)
        self.cache_path = os.path.join(self.cache_dir, "kk_item_index_cache.json")

    @classmethod
    def get_resolver(cls, kk_dir: str):
        if cls._instance is None or cls._instance.kk_dir != kk_dir:
            cls._instance = KKItemResolver(kk_dir)
        return cls._instance

    def load_cache(self) -> bool:
        if not os.path.exists(self.cache_path):
            return False
        try:
            with open(self.cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.item_index = data.get("item_index", {})
            self.name_index = data.get("name_index", {})
            self.zipmod_index = data.get("zipmod_index", {})
            raw_zm = data.get("zipmod_items", {})
            self.zipmod_items = {}
            for k, v in raw_zm.items():
                if ":" in k:
                    guid, slot_str = k.split(":", 1)
                    try:
                        self.zipmod_items[(guid, int(slot_str))] = v
                    except ValueError:
                        pass
            self.is_indexed = True
            print(f"[KK Studio] Loaded item database from cache: {len(self.item_index)} vanilla items, {len(self.zipmod_items)} mod items.")
            return True
        except Exception as e:
            print(f"[KK Studio] Failed to read cache: {e}")
            return False

    def save_cache(self):
        try:
            serialized_zm = {f"{k[0]}:{k[1]}": v for k, v in self.zipmod_items.items()}
            data = {
                "item_index": self.item_index,
                "name_index": self.name_index,
                "zipmod_index": self.zipmod_index,
                "zipmod_items": serialized_zm
            }
            with open(self.cache_path, "w", encoding="utf-8") as f:
                json.dump(data, f)
            print(f"[KK Studio] Saved item database cache to {self.cache_path}")
        except Exception as e:
            print(f"[KK Studio] Failed to save cache: {e}")

    def index_all(self, force: bool = False):
        if self.is_indexed and not force:
            return
        if not force and self.load_cache():
            return
        print("[KK Studio] Scanning Koikatsu asset bundles and mods from disk...")
        self._index_vanilla()
        self._index_zipmods()
        self.is_indexed = True
        self.save_cache()

    def _index_vanilla(self):
        studio_info_dir = os.path.join(self.kk_dir, "abdata", "studio", "info")
        if not os.path.isdir(studio_info_dir):
            return
        bundles = glob.glob(os.path.join(studio_info_dir, "*.unity3d"))
        for bpath in bundles:
            try:
                env = UnityPy.load(bpath)
                for obj in env.objects:
                    if obj.type.name == "MonoBehaviour":
                        mb = obj.read()
                        name = getattr(mb, "m_Name", "")
                        if name.startswith("ItemList_") and hasattr(mb, "list") and mb.list:
                            for row_obj in mb.list:
                                if hasattr(row_obj, "list") and len(row_obj.list) >= 7:
                                    row = row_obj.list
                                    try:
                                        no = int(row[0])
                                        group = int(row[1])
                                        cat = int(row[2])
                                        disp_name = row[3]
                                        bundle_path = row[5]
                                        prefab_name = row[6]
                                        info = {
                                            "no": no, "group": group, "category": cat,
                                            "name": disp_name, "bundle": bundle_path,
                                            "prefab": prefab_name, "source": "vanilla"
                                        }
                                        self.item_index[f"{group}_{cat}_{no}"] = info
                                        self.name_index[prefab_name.lower()] = info
                                    except (ValueError, IndexError):
                                        continue
            except Exception:
                pass

    def _index_zipmods(self):
        mods_dir = os.path.join(self.kk_dir, "mods")
        if not os.path.isdir(mods_dir):
            return
        zipmods = glob.glob(os.path.join(mods_dir, "**", "*.zipmod"), recursive=True)
        for zpath in zipmods:
            try:
                with zipfile.ZipFile(zpath, "r") as z:
                    names = z.namelist()
                    guid = None
                    if "manifest.xml" in names:
                        content = z.open("manifest.xml").read().decode("utf-8-sig", errors="ignore")
                        m = re.search(r"<guid>(.*?)</guid>", content, re.IGNORECASE)
                        if m:
                            guid = m.group(1).strip()
                            self.zipmod_index[guid] = zpath

                    for fn in names:
                        if "itemlist" in fn.lower() and fn.endswith(".csv"):
                            lines = z.open(fn).read().decode("utf-8-sig", errors="ignore").splitlines()
                            for line in lines[1:]:
                                parts = line.split(",")
                                if len(parts) >= 7:
                                    try:
                                        slot = int(parts[0])
                                        cat = int(parts[1])
                                        subcat = int(parts[2])
                                        disp_name = parts[3]
                                        bundle_path = parts[5]
                                        prefab_name = parts[6]
                                        info = {
                                            "slot": slot, "category": cat, "subcat": subcat,
                                            "name": disp_name, "bundle": bundle_path,
                                            "prefab": prefab_name, "zipmod": zpath,
                                            "source": "zipmod"
                                        }
                                        if guid:
                                            self.zipmod_items[(guid, slot)] = info
                                        self.name_index[prefab_name.lower()] = info
                                    except ValueError:
                                        continue
            except Exception:
                pass

    def resolve(self, group: int, cat: int, no: int, uar_guid: str = None, uar_slot: int = None, node_name: str = None):
        if uar_guid and uar_slot is not None:
            hit = self.zipmod_items.get((uar_guid, uar_slot))
            if hit:
                return hit

        hit = self.item_index.get(f"{group}_{cat}_{no}")
        if hit:
            return hit

        if node_name:
            clean = node_name.split("/")[-1].lower()
            hit = self.name_index.get(clean)
            if hit:
                return hit

        return None


# =========================================================================
# 3. Mesh & Texture Loader (Multi-Mesh & Tint Baking)
# =========================================================================

class KKMeshLoader:
    def __init__(self, kk_dir: str, use_fallback_cubes: bool = False):
        self.kk_dir = kk_dir
        self.use_fallback_cubes = use_fallback_cubes
        self.bundle_cache = {} # cache_key -> {"gos": {name_lower: [go, ...]}, "textures": {name_lower: tex}, "meshes": {name_lower: mesh}}
        self.mesh_cache = {}   # cache_key -> bpy.types.Mesh
        self.mat_cache = {}    # mat_key -> bpy.types.Material

        addon_dir = os.path.dirname(os.path.abspath(__file__))
        self.tex_cache_dir = os.path.join(addon_dir, "cache", "textures")
        os.makedirs(self.tex_cache_dir, exist_ok=True)

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
            for comp in getattr(go, "m_Components", []):
                try:
                    c = comp.read()
                    cname = c.__class__.__name__
                    if cname in ["MeshFilter", "SkinnedMeshRenderer"]:
                        mesh_ptr = getattr(c, "m_Mesh", None)
                        if mesh_ptr:
                            m = mesh_ptr.read()
                            is_skinned = (cname == "SkinnedMeshRenderer")
                            if is_skinned:
                                b_mesh = self._create_blender_mesh(m)
                                l_mat = curr_mat
                            else:
                                b_key = f"{prefab_name}_{getattr(go, 'm_Name', '')}_{m.m_Name}"
                                b_mesh = self._create_blender_mesh(m, mesh_key=b_key, transform_mat=curr_mat)
                                l_mat = Matrix.Identity(4)

                            if b_mesh is None:
                                continue
                            b_mat = self._create_blender_material(prefab_name, tex_map, colors)
                            part = {
                                "name": getattr(go, "m_Name", m.m_Name),
                                "mesh": b_mesh,
                                "material": b_mat,
                                "local_matrix": l_mat
                            }
                            if cname == "SkinnedMeshRenderer" and getattr(c, "m_Bones", None):
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

    def _create_blender_material(self, item_name: str, tex_map: dict, colors: list):
        """Creates a standard COM3D2-ready Principled BSDF material with tinted base color texture."""
        tint_rgb = (1.0, 1.0, 1.0)
        if colors and len(colors) > 0 and colors[0]:
            try:
                c_json = json.loads(colors[0])
                tint_rgb = (float(c_json.get("r", 1.0)), float(c_json.get("g", 1.0)), float(c_json.get("b", 1.0)))
            except Exception:
                pass

        is_tinted = any(abs(c - 1.0) > 0.01 for c in tint_rgb)
        color_hash = f"{tint_rgb[0]:.2f}_{tint_rgb[1]:.2f}_{tint_rgb[2]:.2f}"
        mat_name = f"M_{item_name}_{color_hash}"

        if mat_name in self.mat_cache:
            return self.mat_cache[mat_name]

        mat = bpy.data.materials.new(name=mat_name)
        mat.use_nodes = True
        nodes = mat.node_tree.nodes
        links = mat.node_tree.links
        bsdf = nodes.get("Principled BSDF")

        base_tex = None
        for tname, tex in tex_map.items():
            if item_name.lower() in tname or not base_tex:
                base_tex = tex
                if item_name.lower() in tname:
                    break

        if base_tex:
            try:
                img_pil = base_tex.image
                if is_tinted:
                    img_rgb = img_pil.convert("RGBA")
                    r, g, b, a = img_rgb.split()
                    r = r.point(lambda i: int(i * tint_rgb[0]))
                    g = g.point(lambda i: int(i * tint_rgb[1]))
                    b = b.point(lambda i: int(i * tint_rgb[2]))
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
                tex_node = nodes.new(type="ShaderNodeTexImage")
                tex_node.image = b_img
                tex_node.location = (-300, 200)
                if bsdf:
                    links.new(tex_node.outputs["Color"], bsdf.inputs["Base Color"])
            except Exception:
                if bsdf:
                    bsdf.inputs["Base Color"].default_value = (tint_rgb[0], tint_rgb[1], tint_rgb[2], 1.0)
        else:
            if bsdf:
                bsdf.inputs["Base Color"].default_value = (tint_rgb[0], tint_rgb[1], tint_rgb[2], 1.0)

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


# 4. Binary Tree & ExtendedSave Parser
# =========================================================================

class KKStudioParser:
    def __init__(self, scene_path: str):
        self.scene_path = scene_path
        with open(scene_path, "rb") as f:
            self.data = f.read()

        self.tree_names = {}
        self.uar_items = {}
        self.parsed_tree = {} # dic_key -> dict
        self._parse_extsave()
        self._parse_binary_tree()

    def _parse_extsave(self):
        pos = self.data.rfind(b"KKEx")
        if pos == -1:
            return
        stream = io.BytesIO(self.data[pos + 4:])
        try:
            version, length = struct.unpack("<II", stream.read(8))
            mp = stream.read(length)
            plugins = msgpack.unpackb(mp, raw=False, strict_map_key=False)

            tnn = plugins.get("org.njaecha.plugins.treenodenaming", [])
            if len(tnn) > 1 and "names" in tnn[1]:
                self.tree_names = msgpack.unpackb(tnn[1]["names"], raw=False, strict_map_key=False)

            uar = plugins.get("com.bepis.sideloader.universalautoresolver", [])
            if len(uar) > 1:
                for item_raw in uar[1].get("itemInfo", []):
                    it = msgpack.unpackb(item_raw, raw=False, strict_map_key=False)
                    dic_key = it.get("SceneDicKey")
                    if dic_key is not None:
                        self.uar_items[dic_key] = it
        except Exception:
            pass

    def _parse_binary_tree(self):
        iend_pos = self.data.find(b"IEND") + 8
        s = io.BytesIO(self.data[iend_pos:])

        def rs():
            l, sh = 0, 0
            while True:
                b = s.read(1)[0]
                l |= (b & 0x7F) << sh
                if not (b & 0x80): break
                sh += 7
            return s.read(l).decode("utf-8", errors="ignore")

        def r_v3(): return struct.unpack("<fff", s.read(12))
        def r_b(): return struct.unpack("<?", s.read(1))[0]
        def r_i(): return struct.unpack("<i", s.read(4))[0]
        def r_f(): return struct.unpack("<f", s.read(4))[0]

        def get_png_size():
            start = s.tell()
            sig = s.read(8)
            if sig != b"\x89PNG\r\n\x1a\n":
                s.seek(start)
                return 0
            while True:
                len_bytes = s.read(4)
                if len(len_bytes) < 4: break
                chunk_len = struct.unpack(">I", len_bytes)[0]
                chunk_type = s.read(4)
                s.seek(chunk_len + 4, io.SEEK_CUR)
                if chunk_type == b"IEND":
                    break
            end = s.tell()
            return end - start

        version = rs()
        root_count = r_i()

        def parse_obj_base(other=True):
            dic_key = r_i()
            pos = r_v3()
            rot = r_v3()
            scale = r_v3()
            if other:
                tree_state = r_i()
                visible = r_b()
            else:
                visible = True
            return dic_key, pos, rot, scale, visible

        def parse_pattern():
            key = r_i()
            fpath = rs()
            clamp = r_b()
            uv_str = rs()
            rot = r_f()

        def parse_child(parent_key):
            child_count = r_i()
            for _ in range(child_count):
                ckind = r_i()
                parse_node(ckind, parent_key)

        def parse_node(kind, parent_key, attach_point=None):
            dic_key, pos, rot, scale, visible = parse_obj_base(other=True)
            node = {
                "dic_key": dic_key, "kind": kind, "parent_key": parent_key,
                "attach_point": attach_point,
                "pos": pos, "rot": rot, "scale": scale, "visible": visible
            }
            self.parsed_tree[dic_key] = node

            if kind == 3: # Folder
                node["name"] = rs()
                parse_child(dic_key)

            elif kind == 1: # Item
                node["group"] = r_i()
                node["category"] = r_i()
                node["no"] = r_i()
                anime_speed = r_f()
                colors = [rs() for _ in range(8)]
                node["colors"] = colors
                for _ in range(3): parse_pattern()
                alpha = r_f()
                line_color = rs()
                line_width = r_f()
                emission_color = rs()
                emission_power = r_f()
                light_cancel = r_f()
                parse_pattern()
                enable_fk = r_b()
                bone_count = r_i()
                bones = {}
                for _ in range(bone_count):
                    bname = rs()
                    b_key = r_i()
                    b_pos = r_v3()
                    b_rot = r_v3()
                    b_scale = r_v3()
                    bones[bname] = {"key": b_key, "pos": b_pos, "rot": b_rot, "scale": b_scale}
                node["bones"] = bones
                node["enable_fk"] = enable_fk
                enable_db = r_b()
                anime_nml_time = r_f()
                parse_child(dic_key)

            elif kind == 2: # Light
                no = r_i()
                c_r, c_g, c_b, c_a = struct.unpack("<ffff", s.read(16))
                intensity = r_f()
                range_val = r_f()
                spot_angle = r_f()
                shadow = r_b()
                enable = r_b()
                draw_target = r_b()
                node["name"] = f"Light_{dic_key}"

            elif kind == 4: # Route
                node["name"] = rs()
                parse_child(dic_key)
                pt_count = r_i()
                for _ in range(pt_count):
                    parse_obj_base(other=True)
                active = r_b()
                loop = r_b()
                vis_line = r_b()
                orient = r_i()
                color_str = rs()

            elif kind == 5: # Camera
                node["name"] = rs()
                active = r_b()

            elif kind == 0: # Character
                node["name"] = f"Character_{dic_key}"
                sex = r_i()
                png_size = get_png_size()
                prod_no = r_i()
                chara_tag = rs()
                chara_ver = rs()
                face_len = r_i()
                if face_len > 0:
                    s.seek(face_len, io.SEEK_CUR)
                header_len = r_i()
                header_data = s.read(header_len)
                total_block_size = struct.unpack("<q", s.read(8))[0]
                s.seek(total_block_size, io.SEEK_CUR)

                # Bones (44 bytes per bone)
                bone_count = r_i()
                node["bone_count"] = bone_count
                node["bones"] = {}
                for _ in range(bone_count):
                    b_key = r_i(); b_dickey = r_i(); b_pos = r_v3(); b_rot = r_v3(); b_scale = r_v3()
                    node["bones"][b_key] = {"dic_key": b_dickey, "pos": b_pos, "rot": b_rot, "scale": b_scale}

                # IK (44 bytes per ik)
                ik_count = r_i()
                node["ik_count"] = ik_count
                for _ in range(ik_count):
                    ik_key = r_i(); ik_dickey = r_i(); ik_pos = r_v3(); ik_rot = r_v3(); ik_scale = r_v3()

                # Attached child props on character bones!
                child_dict_count = r_i()
                for _ in range(child_dict_count):
                    attach_point = r_i()
                    child_list_count = r_i()
                    for _ in range(child_list_count):
                        ckind = r_i()
                        parse_node(ckind, dic_key, attach_point)

                # Rest of character data
                kinematic_mode = r_i()
                node["anim_group"] = r_i()
                node["anim_cat"] = r_i()
                node["anim_no"] = r_i()
                hptn0 = r_i(); hptn1 = r_i()
                nipple = r_f()
                siru = s.read(5)
                mouth_open = r_f()
                lip_sync = r_b()
                lookat_obj = parse_obj_base(other=False)
                enable_ik = r_b()
                for _ in range(5): r_b()
                enable_fk = r_b()
                for _ in range(7): r_b()
                for _ in range(8): r_b()
                anime_speed = r_f()
                anime_pattern = r_f()
                anime_opt_vis = r_b()
                anime_force_loop = r_b()

                voice_count = r_i()
                for _ in range(voice_count):
                    r_i(); r_i(); r_i()
                voice_repeat = r_i()

                visible_son = r_b()
                son_length = r_f()
                visible_simple = r_b()
                simple_color = rs()
                opt0 = r_f(); opt1 = r_f()
                neck_len = r_i()
                if neck_len > 0: s.seek(neck_len, io.SEEK_CUR)
                eyes_len = r_i()
                if eyes_len > 0: s.seek(eyes_len, io.SEEK_CUR)
                anime_nml_time = r_f()
                acc_grp_cnt = r_i()
                for _ in range(acc_grp_cnt):
                    r_i(); r_i()
                acc_no_cnt = r_i()
                for _ in range(acc_no_cnt):
                    r_i(); r_i()

        try:
            for _ in range(root_count):
                k = r_i()
                kind = r_i()
                parse_node(kind, None)
        except Exception:
            pass


# =========================================================================
# 5. Blender Operators & UI
# =========================================================================

class KK_OT_ReindexDatabase(bpy.types.Operator):
    bl_idname = "kk_studio.reindex_database"
    bl_label = "Re-index Mods & Bundles"
    bl_description = "Force re-scan all Koikatsu asset bundles and zipmod files to update cache"
    bl_options = {'REGISTER'}

    def execute(self, context):
        props = context.scene.kk_studio_props
        kk_dir = props.kk_dir
        if not os.path.isdir(kk_dir):
            self.report({'ERROR'}, f"Directory not found: {kk_dir}")
            return {'CANCELLED'}

        win = getattr(context, "window", None)
        if win:
            win.cursor_modal_set('WAIT')
        try:
            resolver = KKItemResolver.get_resolver(kk_dir)
            resolver.index_all(force=True)
            count = len(resolver.item_index) + len(resolver.zipmod_items)
            self.report({'INFO'}, f"Re-indexed {count} items successfully!")
        finally:
            if win:
                win.cursor_modal_restore()
        return {'FINISHED'}


class KK_OT_ImportScene(bpy.types.Operator):
    bl_idname = "kk_studio.import_scene"
    bl_label = "Import KK Studio Scene"
    bl_description = "Import Koikatsu Studio Scene into Blender"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        if not DEPS_LOADED:
            self.report({'ERROR'}, "UnityPy, msgpack, and Pillow are required.")
            return {'CANCELLED'}

        props = context.scene.kk_studio_props
        kk_dir = props.kk_dir
        scene_path = props.scene_path

        if not os.path.exists(kk_dir):
            self.report({'ERROR'}, f"Koikatsu directory not found: {kk_dir}")
            return {'CANCELLED'}
        if not os.path.exists(scene_path):
            self.report({'ERROR'}, f"Scene PNG not found: {scene_path}")
            return {'CANCELLED'}

        start_time = time.time()
        wm = context.window_manager
        win = getattr(context, "window", None)
        if win:
            win.cursor_modal_set('WAIT')

        try:
            # 1. Resolve / Index Database (Instant if cached)
            resolver = KKItemResolver.get_resolver(kk_dir)
            resolver.index_all()

            mesh_loader = KKMeshLoader(kk_dir, use_fallback_cubes=props.use_fallback_cubes)
            parser = KKStudioParser(scene_path)

            children_map = {}
            for k, n in parser.parsed_tree.items():
                pk = n.get("parent_key")
                if pk is not None:
                    children_map.setdefault(pk, []).append(k)

            if not props.import_attached_props:
                char_keys = {k for k, v in parser.parsed_tree.items() if v.get("kind") == 0}
                def is_descendant_of_char(k):
                    cur = parser.parsed_tree[k].get("parent_key")
                    while cur is not None:
                        if cur in char_keys:
                            return True
                        cur = parser.parsed_tree.get(cur, {}).get("parent_key")
                    return False

                attached_keys = [k for k in parser.parsed_tree if is_descendant_of_char(k)]
                for k in attached_keys:
                    parser.parsed_tree.pop(k, None)
                    parser.tree_names.pop(k, None)

            scene_name = os.path.splitext(os.path.basename(scene_path))[0]
            scene_col = bpy.data.collections.new(f"KK_Scene_{scene_name}")
            bpy.context.scene.collection.children.link(scene_col)

            scene_root = bpy.data.objects.new(f"KK_Root_{scene_name}", None)
            scene_root.empty_display_type = 'PLAIN_AXES'
            scene_root.empty_display_size = 0.5
            # Rotate +90 degrees on X to convert Unity Y-up to Blender Z-up
            scene_root.rotation_euler = (math.radians(90), 0, 0)
            scene_col.objects.link(scene_root)

            total_nodes = len(parser.parsed_tree)
            wm.progress_begin(0, total_nodes)

            created_objects = {}
            current_progress = 0

            # 2. First Pass: Create Nested Folder Collections & Empty Anchors
            folder_cols = {} # dic_key -> Collection

            def get_or_create_folder_col(f_key):
                if f_key in folder_cols:
                    return folder_cols[f_key]
                f_node = parser.parsed_tree[f_key]
                f_name = parser.tree_names.get(f_key, f_node.get("name", f"Folder_{f_key}"))
                f_col = bpy.data.collections.new(f_name)

                f_parent_key = f_node.get("parent_key")
                if f_parent_key is not None and parser.parsed_tree.get(f_parent_key, {}).get("kind") == 3:
                    parent_f_col = get_or_create_folder_col(f_parent_key)
                    parent_f_col.children.link(f_col)
                else:
                    scene_col.children.link(f_col)

                folder_cols[f_key] = f_col
                return f_col

            for dic_key, node in parser.parsed_tree.items():
                if node["kind"] == 3: # Folder
                    get_or_create_folder_col(dic_key)

            def get_target_collection(n_key):
                cur = parser.parsed_tree[n_key].get("parent_key")
                while cur is not None:
                    if cur in folder_cols:
                        return folder_cols[cur]
                    cur = parser.parsed_tree.get(cur, {}).get("parent_key")
                return scene_col

            def get_eval_order(tree):
                visited = set()
                order = []
                def visit(k):
                    if k in visited:
                        return
                    visited.add(k)
                    pk = tree[k].get("parent_key")
                    if pk is not None and pk in tree:
                        visit(pk)
                    order.append(k)
                for k in tree:
                    visit(k)
                return order

            eval_order = get_eval_order(parser.parsed_tree)

            # Compute absolute Unity world transforms (canceling scale inheritance to match KK Studio LateUpdate)
            unity_world = {}
            for k in eval_order:
                node = parser.parsed_tree[k]
                pos = node["pos"]
                rot = node["rot"]
                scale = node["scale"]

                rx = math.radians(rot[0])
                ry = math.radians(-rot[1])
                rz = math.radians(-rot[2])
                local_q = Euler((rx, ry, rz), 'ZXY').to_quaternion()
                local_pos = Vector((-pos[0], pos[1], pos[2]))
                local_scale = Vector((scale[0], scale[1], scale[2]))

                pk = node.get("parent_key")
                if pk is not None and pk in unity_world:
                    p_pos, p_q, p_scale = unity_world[pk]
                    scaled_offset = Vector((local_pos.x * p_scale.x, local_pos.y * p_scale.y, local_pos.z * p_scale.z))
                    w_pos = p_pos + (p_q @ scaled_offset)
                    w_q = p_q @ local_q
                    w_scale = local_scale
                    unity_world[k] = (w_pos, w_q, w_scale)
                else:
                    unity_world[k] = (local_pos, local_q, local_scale)

            single_part_matrices = {}

            for dic_key in eval_order:
                node = parser.parsed_tree[dic_key]
                current_progress += 1
                wm.progress_update(current_progress)

                kind = node["kind"]
                if kind in [3, 0, 4, 5]: # Folder, Character, Route, Camera
                    display_name = parser.tree_names.get(dic_key, node.get("name", f"Node_{dic_key}"))
                    target_col = folder_cols.get(dic_key) if kind == 3 else get_target_collection(dic_key)

                    empty = bpy.data.objects.new(display_name, None)
                    if kind == 3:
                        empty.empty_display_type = 'PLAIN_AXES'
                        empty.empty_display_size = 0.03 # subtle, clean anchor
                    else:
                        empty.empty_display_type = 'PLAIN_AXES'
                        empty.empty_display_size = 0.1
                    target_col.objects.link(empty)
                    created_objects[dic_key] = empty

                    is_vis = node.get("visible", True)
                    if not is_vis:
                        empty.hide_viewport = True
                        empty.hide_render = True
            # 3. Second Pass: Create Props & Multi-Part Meshes
            item_keys = [k for k, n in parser.parsed_tree.items() if n["kind"] == 1]
            total_items = len(item_keys)

            for item_idx, dic_key in enumerate(item_keys):
                node = parser.parsed_tree[dic_key]
                current_progress += 1
                wm.progress_update(current_progress)

                uar_info = parser.uar_items.get(dic_key)
                uar_guid = uar_info.get("ModID") if uar_info else None
                uar_slot = uar_info.get("Slot") if uar_info else None

                custom_name = parser.tree_names.get(dic_key)
                item_def = resolver.resolve(
                    node.get("group", 0), node.get("category", 0), node.get("no", 0),
                    uar_guid, uar_slot, custom_name
                )

                # Determine actual object name with unique _dic_key suffix
                if custom_name:
                    base_name = custom_name
                elif item_def and item_def.get("name"):
                    base_name = item_def["name"]
                elif item_def and item_def.get("prefab"):
                    base_name = item_def["prefab"]
                else:
                    base_name = "Item"

                if base_name.endswith(f"_{dic_key}"):
                    display_name = base_name
                else:
                    display_name = f"{base_name}_{dic_key}"

                if item_idx % 50 == 0 or item_idx == total_items - 1:
                    print(f"[KK Importer] ({item_idx + 1}/{total_items}) Loading: {display_name}")

                parts = []
                if item_def:
                    parts = mesh_loader.get_meshes_and_materials(item_def, node.get("colors"))

                is_dummy_node = "obj無し" in display_name or "objなし" in display_name or "（obj無し）" in display_name or "回転音" in display_name or "Without Object" in display_name
                has_children = dic_key in children_map and len(children_map[dic_key]) > 0

                if not parts:
                    if props.use_fallback_cubes and props.import_meshless and not is_dummy_node:
                        fallback_mesh = mesh_loader.create_fallback_cube(display_name)
                        parts = [{"name": display_name, "mesh": fallback_mesh, "material": None}]
                    elif not props.import_meshless and not has_children:
                        # Skip leaf meshless objects that have no 3D geometry
                        continue

                target_col = get_target_collection(dic_key)
                is_vis = node.get("visible", True)

                def setup_skinned_part(part, part_display_name, target_col, is_vis, node_bones):
                    arm_info = part["armature_data"]
                    arm_data = bpy.data.armatures.new(f"{part_display_name}_Armature")
                    arm_obj = bpy.data.objects.new(f"{part_display_name}_Armature", arm_data)
                    scene_col.objects.link(arm_obj)

                    if context.view_layer.objects.active and context.view_layer.objects.active.mode != 'OBJECT':
                        bpy.ops.object.mode_set(mode='OBJECT')

                    context.view_layer.objects.active = arm_obj
                    arm_obj.select_set(True)
                    bpy.ops.object.mode_set(mode='EDIT')

                    bnames = arm_info["bone_names"]
                    bposes = arm_info["bind_poses"]
                    pmap = arm_info["parent_map"]

                    head_positions = {}
                    for bn, bp in zip(bnames, bposes):
                        mat = Matrix(bp)
                        inv = mat.inverted()
                        head_positions[bn] = Vector((-inv.translation.x, inv.translation.y, inv.translation.z))

                    for bn in bnames:
                        eb = arm_data.edit_bones.new(bn)
                        h = head_positions[bn]
                        eb.head = h
                        eb.tail = h + Vector((0, 0, 0.02))

                    for bn in bnames:
                        pn = pmap.get(bn)
                        if pn and pn in arm_data.edit_bones:
                            arm_data.edit_bones[bn].parent = arm_data.edit_bones[pn]

                    bpy.ops.object.mode_set(mode='OBJECT')

                    if target_col != scene_col:
                        target_col.objects.link(arm_obj)
                        scene_col.objects.unlink(arm_obj)

                    mesh_copy = part["mesh"].copy()
                    mesh_obj = bpy.data.objects.new(part_display_name, mesh_copy)
                    if part.get("material"):
                        mesh_obj.data.materials.append(part["material"])
                    target_col.objects.link(mesh_obj)

                    for bn in bnames:
                        mesh_obj.vertex_groups.new(name=bn)
                    for v_idx, s_info in enumerate(arm_info["skin"]):
                        for b_attr, w_attr in [('boneIndex_0_', 'weight_0_'), ('boneIndex_1_', 'weight_1_'), ('boneIndex_2_', 'weight_2_'), ('boneIndex_3_', 'weight_3_')]:
                            w = getattr(s_info, w_attr, 0.0)
                            if w and w > 0.0001:
                                bi = getattr(s_info, b_attr, 0)
                                if bi < len(bnames):
                                    mesh_obj.vertex_groups[bnames[bi]].add([v_idx], w, 'REPLACE')

                    mesh_obj.parent = arm_obj
                    mod = mesh_obj.modifiers.new(name="Armature", type='ARMATURE')
                    mod.object = arm_obj

                    for bn, bd in node_bones.items():
                        pb = arm_obj.pose.bones.get(bn)
                        if pb:
                            rot = bd["rot"]
                            rx = math.radians(rot[0])
                            ry = math.radians(-rot[1])
                            rz = math.radians(-rot[2])
                            pb.rotation_mode = 'QUATERNION'
                            pb.rotation_quaternion = Euler((rx, ry, rz), 'ZXY').to_quaternion()
                            if any(abs(x) > 0.0001 for x in bd["pos"]):
                                pb.location = Vector((-bd["pos"][0], bd["pos"][1], bd["pos"][2]))

                    if not is_vis:
                        arm_obj.hide_viewport = True
                        arm_obj.hide_render = True
                        mesh_obj.hide_viewport = True
                        mesh_obj.hide_render = True

                    return arm_obj, mesh_obj

                if len(parts) == 1:
                    part = parts[0]
                    if part.get("armature_data"):
                        arm_obj, mesh_obj = setup_skinned_part(part, display_name, target_col, is_vis, node.get("bones", {}))
                        created_objects[dic_key] = arm_obj
                    else:
                        obj = bpy.data.objects.new(display_name, part["mesh"])
                        if part.get("material"):
                            obj.data.materials.append(part["material"])
                        target_col.objects.link(obj)
                        created_objects[dic_key] = obj
                        if not is_vis:
                            obj.hide_viewport = True
                            obj.hide_render = True
                    single_part_matrices[dic_key] = part.get("local_matrix", Matrix.Identity(4))

                elif len(parts) > 1:
                    parent_obj = bpy.data.objects.new(display_name, None)
                    parent_obj.empty_display_type = 'PLAIN_AXES'
                    parent_obj.empty_display_size = 0.05
                    target_col.objects.link(parent_obj)
                    created_objects[dic_key] = parent_obj
                    if not is_vis:
                        parent_obj.hide_viewport = True
                        parent_obj.hide_render = True

                    for sub_idx, part in enumerate(parts):
                        sub_name = f"{display_name}_{part['name']}"
                        part_lmat = part.get("local_matrix", Matrix.Identity(4))
                        if part.get("armature_data"):
                            arm_obj, mesh_obj = setup_skinned_part(part, sub_name, target_col, is_vis, node.get("bones", {}))
                            arm_obj.parent = parent_obj
                            arm_obj.matrix_basis = part_lmat
                        else:
                            sub_obj = bpy.data.objects.new(sub_name, part["mesh"])
                            if part.get("material"):
                                sub_obj.data.materials.append(part["material"])
                            target_col.objects.link(sub_obj)
                            sub_obj.parent = parent_obj
                            sub_obj.matrix_basis = part_lmat
                            if not is_vis:
                                sub_obj.hide_viewport = True
                                sub_obj.hide_render = True

                elif not parts:
                    empty = bpy.data.objects.new(display_name, None)
                    empty.empty_display_type = 'PLAIN_AXES'
                    empty.empty_display_size = 0.03
                    target_col.objects.link(empty)
                    created_objects[dic_key] = empty
                    if not is_vis:
                        empty.hide_viewport = True
                        empty.hide_render = True

            # 4. Third Pass: Link Hierarchy & Set Exact Transforms without Scale Distortion
            bpy.context.view_layer.update()
            root_mw = scene_root.matrix_world

            for dic_key in eval_order:
                obj = created_objects.get(dic_key)
                if not obj:
                    continue

                node = parser.parsed_tree[dic_key]
                parent_key = node.get("parent_key")
                parent_obj = created_objects.get(parent_key) if parent_key is not None else None

                w_pos, w_q, w_scale = unity_world[dic_key]
                T = Matrix.Translation(w_pos)
                R = w_q.to_matrix().to_4x4()
                S = Matrix.Diagonal(Vector((w_scale.x, w_scale.y, w_scale.z, 1.0)))
                unity_mw = T @ R @ S

                if dic_key in single_part_matrices:
                    l_mat = single_part_matrices[dic_key]
                    if l_mat != Matrix.Identity(4):
                        unity_mw = unity_mw @ l_mat

                blender_mw = root_mw @ unity_mw

                if parent_obj and obj != parent_obj:
                    obj.parent = parent_obj
                    obj.matrix_parent_inverse = parent_obj.matrix_world.inverted()
                else:
                    obj.parent = scene_root
                    obj.matrix_parent_inverse = scene_root.matrix_world.inverted()

                obj.matrix_world = blender_mw

            bpy.context.view_layer.update()

            # 5. Fifth Pass: Apply Inactive Visibility to Folder Collections
            def set_collection_visibility(layer_col, target_col, visible):
                if layer_col.collection == target_col:
                    layer_col.hide_viewport = not visible
                    return True
                for child in layer_col.children:
                    if set_collection_visibility(child, target_col, visible):
                        return True
                return False

            root_lc = context.view_layer.layer_collection
            for f_key, f_col in folder_cols.items():
                f_node = parser.parsed_tree[f_key]
                if not f_node.get("visible", True):
                    f_col.hide_viewport = True
                    f_col.hide_render = True
                    set_collection_visibility(root_lc, f_col, False)

            elapsed = time.time() - start_time
            self.report({'INFO'}, f"Successfully imported {len(created_objects)} objects in {elapsed:.1f}s!")
            print(f"[KK Importer] Finished importing {len(created_objects)} objects in {elapsed:.1f}s.")
        finally:
            wm.progress_end()
            if win:
                win.cursor_modal_restore()

        return {'FINISHED'}


class KKStudioSceneProperties(bpy.types.PropertyGroup):
    kk_dir: StringProperty(
        name="Koikatsu Path",
        description="Path to Koikatsu game directory",
        default=r"K:\KK",
        subtype='DIR_PATH'
    )
    scene_path: StringProperty(
        name="Scene PNG",
        description="Path to Studio Scene PNG file",
        default=r"K:\KK\UserData\Studio\scene\2026_0222_2203_14_452.png",
        subtype='FILE_PATH'
    )
    import_attached_props: BoolProperty(
        name="Import Attached Props",
        description="Load props attached to characters (body/clothes ignored)",
        default=False
    )
    import_meshless: BoolProperty(
        name="Import Meshless Objects",
        description="Load objects without 3D geometry (keeps hierarchy empties for children if disabled, skips leaf meshless objects)",
        default=False
    )
    use_fallback_cubes: BoolProperty(
        name="Fallback Cubes",
        description="Place labeled cubes for missing modded assets",
        default=False
    )


class KK_PT_StudioImporterPanel(bpy.types.Panel):
    bl_label = "KK Studio Importer"
    bl_idname = "KK_PT_studio_importer"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "KK Studio"

    def draw(self, context):
        layout = self.layout
        props = context.scene.kk_studio_props

        if not DEPS_LOADED:
            box = layout.box()
            box.label(text="Dependencies Missing!", icon='ERROR')
            box.label(text="Run: pip install UnityPy msgpack Pillow")
            return

        box = layout.box()
        box.label(text="Paths:", icon='FILE_FOLDER')
        box.prop(props, "kk_dir")
        box.prop(props, "scene_path")
        box.operator("kk_studio.reindex_database", text="Re-index Asset Cache", icon='FILE_REFRESH')

        box = layout.box()
        box.label(text="Settings:", icon='PREFERENCES')
        box.prop(props, "import_attached_props")
        box.prop(props, "import_meshless")
        box.prop(props, "use_fallback_cubes")

        layout.separator()
        layout.operator("kk_studio.import_scene", text="Import Studio Scene", icon='IMPORT')


classes = (
    KKStudioSceneProperties,
    KK_OT_ReindexDatabase,
    KK_OT_ImportScene,
    KK_PT_StudioImporterPanel,
)

def register():
    for c in classes:
        bpy.utils.register_class(c)
    bpy.types.Scene.kk_studio_props = bpy.props.PointerProperty(type=KKStudioSceneProperties)

def unregister():
    for c in reversed(classes):
        bpy.utils.unregister_class(c)
    del bpy.types.Scene.kk_studio_props

if __name__ == "__main__":
    register()
