import sys
sys.path.insert(0, r'c:\Users\harri\AppData\Roaming\Blender Foundation\Blender\3.3\scripts\addons')
from kk_studio_scene_importer import KKStudioParser, KKItemResolver

p = r'K:\KK\UserData\Studio\scene\Assets Scenes\Asset-Weapon-Pistol45.png'
parser = KKStudioParser(p)
resolver = KKItemResolver.get_resolver(r'K:\KK')
resolver.index_all()

for k in list(parser.parsed_tree.keys())[:25]:
    n = parser.parsed_tree[k]
    if n['kind'] == 1:
        it = resolver.resolve(n.get('group',0), n.get('category',0), n.get('no',0))
        if it:
            print(f"Key {k}: name='{it.get('name')}', prefab='{it.get('prefab')}'")
