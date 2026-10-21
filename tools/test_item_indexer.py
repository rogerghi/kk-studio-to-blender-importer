import glob
import os
import UnityPy
import json

def build_vanilla_item_index(kk_dir: str):
    studio_info_dir = os.path.join(kk_dir, "abdata", "studio", "info")
    info_bundles = glob.glob(os.path.join(studio_info_dir, "*.unity3d"))
    
    item_index = {} # (group, category, no) -> {bundle, prefab, name}
    name_index = {} # prefab_name.lower() -> {bundle, prefab, name}
    
    print(f"Scanning {len(info_bundles)} info bundles in {studio_info_dir}...")
    for bpath in info_bundles:
        try:
            env = UnityPy.load(bpath)
            for obj in env.objects:
                if obj.type.name == "MonoBehaviour":
                    mb = obj.read()
                    name = getattr(mb, "m_Name", "")
                    if name.startswith("ItemList_"):
                        # mb.list contains rows
                        if hasattr(mb, "list") and mb.list:
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
                                            "no": no,
                                            "group": group,
                                            "category": cat,
                                            "name": disp_name,
                                            "bundle": bundle_path,
                                            "prefab": prefab_name
                                        }
                                        item_index[f"{group}_{cat}_{no}"] = info
                                        name_index[prefab_name.lower()] = info
                                    except (ValueError, IndexError):
                                        continue
        except Exception as e:
            pass
            
    print(f"Total vanilla items indexed: {len(item_index)}")
    return item_index, name_index

if __name__ == "__main__":
    item_idx, name_idx = build_vanilla_item_index(r"K:\KK")
    
    # Test lookups for primitives: Sphere (0_0_0), Cube (0_0_1), Cylinder (0_0_4)
    for test_key in ["0_0_0", "0_0_1", "0_0_4", "0_0_469"]:
        print(f"Lookup {test_key}:", item_idx.get(test_key))
        
    # Test name lookup for acs_meka_h
    print("Lookup 'p_acs_meka_h_stu':", name_idx.get("p_acs_meka_h_stu"))
