import bpy, math, os, sys
sys.path.insert(0, r'c:\Users\harri\AppData\Roaming\Blender Foundation\Blender\3.3\scripts\addons')
from kk_studio_scene_importer import KKStudioParser, KKItemResolver, KKMeshLoader

kk_dir = r"K:\KK"
scene_path = r"K:\KK\UserData\Studio\scene\Assets Scenes\Asset-Weapon-Pistol45.png"

parser = KKStudioParser(scene_path)
resolver = KKItemResolver.get_resolver(kk_dir)
resolver.index_all()
loader = KKMeshLoader(kk_dir)

node_529 = parser.parsed_tree[529]
print("Node 529 scale in scene:", node_529["scale"])

item_def = resolver.resolve(node_529["group"], node_529["category"], node_529["no"])
parts = loader.get_meshes_and_materials(item_def)
mesh = parts[0]["mesh"]

# Test A: Current scale (sx, sz, sy)
sx, sy, sz = node_529["scale"]
obj_a = bpy.data.objects.new("Test_A", mesh)
obj_a.scale = (sx, sz, sy)
bpy.context.scene.collection.objects.link(obj_a)
bpy.context.view_layer.update()
dims_a = obj_a.dimensions
print(f"Test A (sx, sz, sy) dimensions in Blender: X={dims_a.x:.4f}, Y={dims_a.y:.4f}, Z={dims_a.z:.4f}")

# Test B: Direct scale (sx, sy, sz)
obj_b = bpy.data.objects.new("Test_B", mesh)
obj_b.scale = (sx, sy, sz)
bpy.context.scene.collection.objects.link(obj_b)
bpy.context.view_layer.update()
dims_b = obj_b.dimensions
print(f"Test B (sx, sy, sz) dimensions in Blender: X={dims_b.x:.4f}, Y={dims_b.y:.4f}, Z={dims_b.z:.4f}")
