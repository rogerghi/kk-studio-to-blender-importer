import os
import re
import json
import glob
import zipfile

import site
import sys
site_packages = site.getusersitepackages()
if site_packages not in sys.path:
    sys.path.append(site_packages)

try:
    import UnityPy
except ImportError as e:
    print(f"[KK Studio Importer ERROR] Failed to import UnityPy in resolver: {e}")

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
                                        self.item_index[f"{cat}_{subcat}_{slot}"] = info
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
