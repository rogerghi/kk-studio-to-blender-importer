"""
Koikatsu Studio Scene Parser
Reads Koikatsu Studio Scene PNG files, extracts hierarchy, transforms, and mod requirements.
"""

import struct
import io
import re
import os
import sys
import msgpack
from collections import Counter


class KKSceneParser:
    def __init__(self, scene_path: str):
        self.scene_path = scene_path
        if not os.path.exists(scene_path):
            raise FileNotFoundError(f"Scene file not found: {scene_path}")
        with open(scene_path, "rb") as f:
            self.raw_data = f.read()

        self.png_end_offset = self._find_png_end()
        self.extsave_offset = self._find_extsave_offset()
        self.version = ""
        self.tree_names = {}
        self.mod_items = []
        self.mod_patterns = []
        self.embedded_textures_count = 0
        self.plugins_data = {}

        self._parse_extsave()

    def _find_png_end(self) -> int:
        idx = self.raw_data.find(b"IEND")
        if idx == -1:
            raise ValueError("Invalid PNG: IEND chunk not found")
        return idx + 8

    def _find_extsave_offset(self) -> int:
        # Search for KKEx marker in the trailing data
        pos = 0
        last_found = -1
        while True:
            pos = self.raw_data.find(b"KKEx", pos)
            if pos == -1:
                break
            last_found = pos
            pos += 4
        return last_found

    def _parse_extsave(self):
        if self.extsave_offset == -1:
            return

        stream = io.BytesIO(self.raw_data[self.extsave_offset + 4:])
        version, length = struct.unpack("<II", stream.read(8))
        self.extsave_version = version

        mp_bytes = stream.read(length)
        self.plugins_data = msgpack.unpackb(mp_bytes, raw=False, strict_map_key=False)

        # Extract TreeNodeNaming
        tnn = self.plugins_data.get("org.njaecha.plugins.treenodenaming", [])
        if len(tnn) > 1 and "names" in tnn[1]:
            self.tree_names = msgpack.unpackb(tnn[1]["names"], raw=False, strict_map_key=False)

        # Extract UniversalAutoResolver (UAR)
        uar = self.plugins_data.get("com.bepis.sideloader.universalautoresolver", [])
        if len(uar) > 1:
            for item in uar[1].get("itemInfo", []):
                self.mod_items.append(msgpack.unpackb(item, raw=False, strict_map_key=False))
            for pat in uar[1].get("patternInfo", []):
                self.mod_patterns.append(msgpack.unpackb(pat, raw=False, strict_map_key=False))

        # Extract MaterialEditor textures
        me = self.plugins_data.get("com.deathweasel.bepinex.materialeditor", [])
        if len(me) > 1 and "TextureDictionary" in me[1]:
            td = msgpack.unpackb(me[1]["TextureDictionary"], raw=False, strict_map_key=False)
            self.embedded_textures_count = len(td)

    def print_summary(self):
        chara_matches = re.findall(rb"\xe3\x80\x90KoiKatuChara\xe3\x80\x91", self.raw_data)
        file_mb = len(self.raw_data) / (1024 * 1024)
        png_kb = self.png_end_offset / 1024
        payload_mb = (len(self.raw_data) - self.png_end_offset) / (1024 * 1024)

        print("=" * 60)
        print(" KOIKATSU STUDIO SCENE ANALYSIS")
        print("=" * 60)
        print(f"File Path           : {self.scene_path}")
        print(f"Total File Size     : {file_mb:.2f} MB")
        print(f"PNG Preview Image   : {png_kb:.2f} KB")
        print(f"Data Payload Size   : {payload_mb:.2f} MB")
        print(f"Embedded Characters : {len(chara_matches)}")
        print(f"Total Scene Nodes   : {len(self.tree_names)}")
        print(f"Embedded Textures   : {self.embedded_textures_count}")
        print(f"Modded Items (UAR)  : {len(self.mod_items)}")
        print(f"Modded Patterns     : {len(self.mod_patterns)}")

        # Group object names
        clean_counts = Counter()
        for name in self.tree_names.values():
            cn = re.sub(r"\s+\d+$", "", name)
            clean_counts[cn] += 1

        print("\n--- TOP OBJECTS IN SCENE ---")
        for name, count in clean_counts.most_common(20):
            print(f"  {name:35s}: {count:4d}")

        if self.mod_items:
            print("\n--- REQUIRED MODS (ZIPMODS) ---")
            for it in self.mod_items:
                print(f"  - [{it.get('Name')}] (ModID: {it.get('ModID')}, Slot: {it.get('Slot')})")


if __name__ == "__main__":
    test_path = r"K:\KK\UserData\Studio\scene\2026_0222_2203_14_452.png"
    target = sys.argv[1] if len(sys.argv) > 1 else test_path
    parser = KKSceneParser(target)
    parser.print_summary()
