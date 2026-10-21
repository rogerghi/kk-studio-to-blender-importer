import bpy, math, os, sys
from mathutils import Matrix, Vector, Quaternion, Euler

sys.path.insert(0, r'c:\Users\harri\AppData\Roaming\Blender Foundation\Blender\3.3\scripts\addons')
from kk_studio_scene_importer import KKStudioParser, KKItemResolver, KKMeshLoader

kk_dir = r"K:\KK"
scene_path = r"K:\KK\UserData\Studio\scene\Assets Scenes\Asset-Weapon-Pistol45.png"

parser = KKStudioParser(scene_path)
resolver = KKItemResolver.get_resolver(kk_dir)
resolver.index_all()
loader = KKMeshLoader(kk_dir)

# Clear existing test collection
test_col_name = "Test_Pistol_TRS"
if test_col_name in bpy.data.collections:
    bpy.data.collections.remove(bpy.data.collections[test_col_name])
col = bpy.data.collections.new(test_col_name)
bpy.context.scene.collection.children.link(col)

def unity_trs_matrix(pos, rot_deg, scale):
    # Unity TRS: Translation * Rotation * Scale
    # rot_deg in Unity is Quaternion.Euler(rot.x, rot.y, rot.z)
    # Unity Euler is ZXY intrinsic:
    # First Z, then X, then Y
    # In mathutils Euler: 'ZXY'
    # angles in radians
    rx = math.radians(rot_deg[0])
    ry = math.radians(rot_deg[1])
    rz = math.radians(rot_deg[2])
    e = Euler((rx, ry, rz), 'ZXY')
    q = e.to_quaternion()
    
    # TRS matrix in Unity local space:
    T = Matrix.Translation(Vector(pos))
    R = q.to_matrix().to_4x4()
    S = Matrix.Diagonal(Vector((scale[0], scale[1], scale[2], 1.0)))
    return T @ R @ S

created_objs = {}

# 1. Create all objects
for dic_key, node in parser.parsed_tree.items():
    kind = node["kind"]
    disp_name = parser.tree_names.get(dic_key, f"Obj_{dic_key}")
    
    if kind == 1: # Item
        item_def = resolver.resolve(node.get("group",0), node.get("category",0), node.get("no",0))
        parts = []
        if item_def:
            parts = loader.get_meshes_and_materials(item_def)
        
        if parts:
            obj = bpy.data.objects.new(disp_name, parts[0]["mesh"])
            col.objects.link(obj)
            created_objs[dic_key] = obj
        else:
            empty = bpy.data.objects.new(disp_name, None)
            col.objects.link(empty)
            created_objs[dic_key] = empty
    else:
        empty = bpy.data.objects.new(disp_name, None)
        col.objects.link(empty)
        created_objs[dic_key] = empty

# 2. Set local transforms and link hierarchy
for dic_key, node in parser.parsed_tree.items():
    obj = created_objs.get(dic_key)
    if not obj:
        continue
    
    # Calculate local TRS matrix
    M_local = unity_trs_matrix(node["pos"], node["rot"], node["scale"])
    obj.matrix_basis = M_local
    
    parent_key = node.get("parent_key")
    if parent_key is not None and parent_key in created_objs:
        p_obj = created_objs[parent_key]
        if p_obj != obj:
            obj.parent = p_obj
            # Keep matrix_basis as local TRS
            obj.matrix_basis = M_local

bpy.context.view_layer.update()

# Check bounding box of all created objects
all_verts_world = []
for obj in created_objs.values():
    if obj.type == 'MESH':
        for v in obj.data.vertices:
            all_verts_world.append(obj.matrix_world @ v.co)

if all_verts_world:
    xs = [v.x for v in all_verts_world]
    ys = [v.y for v in all_verts_world]
    zs = [v.z for v in all_verts_world]
    print(f"Overall Pistol Bounding Box in Unity Space:")
    print(f"X: {min(xs):.3f} to {max(xs):.3f} (size: {max(xs)-min(xs):.3f}m = {(max(xs)-min(xs))*100:.1f}cm)")
    print(f"Y: {min(ys):.3f} to {max(ys):.3f} (size: {max(ys)-min(ys):.3f}m = {(max(ys)-min(ys))*100:.1f}cm)")
    print(f"Z: {min(zs):.3f} to {max(zs):.3f} (size: {max(zs)-min(zs):.3f}m = {(max(zs)-min(zs))*100:.1f}cm)")

# Save test blend file so we can inspect it!
blend_out = r"c:\Users\harri\AppData\Roaming\Blender Foundation\Blender\3.3\scripts\addons\extra_files\kk_scene_reader\test_pistol.blend"
bpy.ops.wm.save_as_mainfile(filepath=blend_out)
print(f"Saved test blend to: {blend_out}")
