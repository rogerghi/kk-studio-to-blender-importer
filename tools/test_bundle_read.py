import os, sys, site, zipfile, io
sys.path.append(site.getusersitepackages())
import UnityPy
from PIL import Image

kk_dir = r"K:\KK"
res_path = os.path.join(kk_dir, "CharaStudio_Data", "Resources", "unity default resources")

# Test vanilla item: studio/00.unity3d
bpath = os.path.join(kk_dir, "abdata", "studio", "00.unity3d")
if os.path.exists(bpath):
    env = UnityPy.Environment()
    if os.path.exists(res_path):
        env.load_file(res_path, name="unity default resources")
    env.load_file(bpath)
    print(f"Loaded {bpath}, objects count: {len(env.objects)}")
    
    meshes = []
    game_objects = []
    textures = []
    for obj in env.objects:
        if obj.type.name == "Mesh":
            meshes.append(obj.read().m_Name)
        elif obj.type.name == "GameObject":
            game_objects.append(obj.read().m_Name)
        elif obj.type.name == "Texture2D":
            textures.append(obj.read().m_Name)
            
    print(f"Meshes ({len(meshes)}): {meshes[:10]}")
    print(f"GameObjects ({len(game_objects)}): {game_objects[:10]}")
    print(f"Textures ({len(textures)}): {textures[:10]}")
