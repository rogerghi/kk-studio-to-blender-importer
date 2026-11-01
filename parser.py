import struct
import io
import json

import site
import sys
site_packages = site.getusersitepackages()
if site_packages not in sys.path:
    sys.path.append(site_packages)

try:
    import msgpack
except ImportError as e:
    print(f"[KK Studio Importer ERROR] Failed to import msgpack in parser: {e}")

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
                node["sex"] = sex
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
                block_data = s.read(total_block_size)
                self._parse_chara_card_blocks(header_data, block_data, node)

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

    @staticmethod
    def _lz4_decompress_block(src: bytes, uncompressed_size: int) -> bytes:
        dst = bytearray(uncompressed_size)
        s_idx = 0
        d_idx = 0
        s_len = len(src)
        while s_idx < s_len:
            token = src[s_idx]
            s_idx += 1
            lit_len = token >> 4
            if lit_len == 15:
                while s_idx < s_len:
                    b = src[s_idx]
                    s_idx += 1
                    lit_len += b
                    if b != 255:
                        break
            if lit_len > 0:
                dst[d_idx:d_idx + lit_len] = src[s_idx:s_idx + lit_len]
                s_idx += lit_len
                d_idx += lit_len
            if s_idx >= s_len:
                break
            offset = src[s_idx] | (src[s_idx + 1] << 8)
            s_idx += 2
            match_len = (token & 0x0F) + 4
            if (token & 0x0F) == 15:
                while s_idx < s_len:
                    b = src[s_idx]
                    s_idx += 1
                    match_len += b
                    if b != 255:
                        break
            m_pos = d_idx - offset
            for _ in range(match_len):
                dst[d_idx] = dst[m_pos]
                d_idx += 1
                m_pos += 1
        return bytes(dst)

    def _parse_chara_card_blocks(self, header_data: bytes, block_data: bytes, node: dict):
        try:
            hdr = msgpack.unpackb(header_data, raw=False, strict_map_key=False)
            lst_info = hdr.get("lstInfo", []) if isinstance(hdr, dict) else []
            blocks = {}
            for info in lst_info:
                b_name = info.get("name")
                pos = info.get("pos", 0)
                size = info.get("size", 0)
                if b_name and size > 0:
                    blocks[b_name] = block_data[pos:pos + size]

            coord_type = 0
            if "Status" in blocks:
                st = msgpack.unpackb(blocks["Status"], raw=False, strict_map_key=False)
                if isinstance(st, dict):
                    coord_type = st.get("coordinateType", 0)
            node["coordinate_type"] = coord_type

            if "Custom" in blocks:
                cb = blocks["Custom"]
                cs = io.BytesIO(cb)
                l1 = struct.unpack("<i", cs.read(4))[0]
                cs.seek(l1, io.SEEK_CUR)
                l2 = struct.unpack("<i", cs.read(4))[0]
                body_mp = msgpack.unpackb(cs.read(l2), raw=False, strict_map_key=False)
                if isinstance(body_mp, dict) and "shapeValueBody" in body_mp:
                    node["shape_body"] = list(body_mp["shapeValueBody"])

            if "KKEx" in blocks:
                kkex = msgpack.unpackb(blocks["KKEx"], raw=False, strict_map_key=False)
                abm_entry = kkex.get("KKABMPlugin.ABMData") if isinstance(kkex, dict) else None
                if abm_entry and len(abm_entry) > 1 and isinstance(abm_entry[1], dict):
                    bdata = abm_entry[1].get("boneData")
                    if isinstance(bdata, bytes):
                        try:
                            bdata = msgpack.unpackb(bdata, raw=False, strict_map_key=False)
                        except Exception:
                            pass
                    raw_abm = None
                    if isinstance(bdata, msgpack.ExtType) and bdata.code == 99:
                        ext_b = bdata.data
                        b0 = ext_b[0]
                        if b0 == 0xD2:
                            u_size = struct.unpack(">i", ext_b[1:5])[0]
                            comp = ext_b[5:]
                        elif b0 == 0xD1:
                            u_size = struct.unpack(">H", ext_b[1:3])[0]
                            comp = ext_b[3:]
                        elif b0 == 0xD0:
                            u_size = ext_b[1]
                            comp = ext_b[2:]
                        elif b0 < 0x80:
                            u_size = b0
                            comp = ext_b[1:]
                        else:
                            u_size = 0
                            comp = b""
                        if u_size > 0:
                            raw_abm = self._lz4_decompress_block(comp, u_size)
                    elif isinstance(bdata, bytes):
                        raw_abm = bdata

                    if raw_abm:
                        abm_list = msgpack.unpackb(raw_abm, raw=False, strict_map_key=False)
                        abm_bones = {}
                        if isinstance(abm_list, list):
                            for item in abm_list:
                                if not isinstance(item, list) or len(item) < 2:
                                    continue
                                bname = item[0]
                                c_mods = item[1]
                                if not isinstance(c_mods, list) or not c_mods:
                                    continue
                                mod = c_mods[coord_type] if coord_type < len(c_mods) else c_mods[0]
                                if isinstance(mod, list) and len(mod) >= 2:
                                    scale = mod[0] if len(mod) > 0 and mod[0] else [1.0, 1.0, 1.0]
                                    length = float(mod[1]) if len(mod) > 1 and mod[1] is not None else 1.0
                                    pos_off = mod[2] if len(mod) > 2 and mod[2] else [0.0, 0.0, 0.0]
                                    rot_off = mod[3] if len(mod) > 3 and mod[3] else [0.0, 0.0, 0.0]
                                    abm_bones[bname] = {
                                        "scale": scale,
                                        "length": length,
                                        "pos": pos_off,
                                        "rot": rot_off,
                                    }
                        if abm_bones:
                            node["abm_bones"] = abm_bones
        except Exception:
            pass
