import bpy, sys, os
sys.path.insert(0, r'c:\Users\harri\AppData\Roaming\Blender Foundation\Blender\3.3\scripts\addons')
import kk_studio_scene_importer
from kk_studio_scene_importer import KKMeshLoader

kk_dir = r"K:\KK"
loader = KKMeshLoader(kk_dir)

items = [
    {'no': 1, 'group': 0, 'category': 0, 'name': 'キューブ(通常）', 'bundle': 'studio/00.unity3d', 'prefab': 'p_koi_stu_cube01_02', 'source': 'vanilla'},
    {'no': 4, 'group': 0, 'category': 0, 'name': 'シリンダー(通常）', 'bundle': 'studio/00.unity3d', 'prefab': 'p_koi_stu_cylinder01_02', 'source': 'vanilla'},
    {'no': 1007, 'group': 14, 'category': 77, 'name': 'リング(細)', 'bundle': 'studio/02.unity3d', 'prefab': 'p_koi_stu_glow06_00', 'source': 'vanilla'}
]

for item in items:
    parts = loader.get_meshes_and_materials(item)
    print(f"Item {item['prefab']}: {len(parts)} parts extracted")
    for p in parts:
        print(f"   part name={p['name']}, mesh_name={p['mesh'].name}, verts={len(p['mesh'].vertices)}, polys={len(p['mesh'].polygons)}")
