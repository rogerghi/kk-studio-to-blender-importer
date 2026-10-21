import site, sys, os
sys.path.append(site.getusersitepackages())

import bpy
import UnityPy

# Test loading a vanilla primitive from studio/00.unity3d directly into Blender
bundle_path = r"K:\KK\abdata\studio\00.unity3d"
env = UnityPy.load(bundle_path)

mesh_obj = None
for obj in env.objects:
    if obj.type.name == "Mesh":
        m = obj.read()
        if m.m_Name == "acs_O_cylinder":
            mesh_obj = m
            break

if not mesh_obj:
    print("Mesh acs_O_cylinder not found!")
    sys.exit(1)

print(f"Found mesh: {mesh_obj.m_Name}")

# In UnityPy, extract vertices and faces
# Let's inspect mesh_obj properties or use export() / vertex data
# Using OBJ parser or raw vertex/index lists
obj_str = mesh_obj.export()
lines = obj_str.splitlines()

verts = []
uvs = []
faces = []

for line in lines:
    if line.startswith("v "):
        parts = line.split()
        verts.append((float(parts[1]), float(parts[2]), float(parts[3])))
    elif line.startswith("vt "):
        parts = line.split()
        uvs.append((float(parts[1]), float(parts[2])))
    elif line.startswith("f "):
        parts = line.split()[1:]
        face = []
        for p in parts:
            idx = int(p.split("/")[0]) - 1 # 1-indexed to 0-indexed
            face.append(idx)
        faces.append(face)

print(f"Parsed OBJ: {len(verts)} vertices, {len(faces)} faces, {len(uvs)} UVs")

# Create Blender mesh
mesh_data = bpy.data.meshes.new(mesh_obj.m_Name)
mesh_data.from_pydata(verts, [], faces)
mesh_data.update()

obj = bpy.data.objects.new("Test_Cylinder", mesh_data)
bpy.context.collection.objects.link(obj)

# Apply transform: Pos (1.0, 2.0, 3.0), Scale (1.0, 2.0, 1.0)
obj.location = (1.0, 2.0, 3.0)
obj.scale = (1.0, 2.0, 1.0)

print(f"SUCCESS: Created Blender object '{obj.name}' with {len(obj.data.vertices)} vertices at location {obj.location}")
