bl_info = {
    "name": "Koikatsu Studio Scene Importer",
    "author": "rinasaurus",
    "version": (1, 5, 3),
    "blender": (3, 0, 0),
    "location": "3D Viewport > Sidebar (N) > KK Studio",
    "description": "Imports Koikatsu Studio scene cards into Blender with character pose armatures, preserving exact hierarchy, transforms, multi-part meshes, and tinted textures for COM3D2 export.",
    "category": "Import-Export",
}

import site, sys, os
site_packages = site.getusersitepackages()
if site_packages not in sys.path:
    sys.path.append(site_packages)

if "bpy" in locals():
    import importlib
    if "parser" in locals():
        importlib.reload(parser)
    if "resolver" in locals():
        importlib.reload(resolver)
    if "mesh_loader" in locals():
        importlib.reload(mesh_loader)
    if "retarget" in locals():
        importlib.reload(retarget)
    if "com_tools" in locals():
        importlib.reload(com_tools)
    if "kk_studio_scene_importer" in locals():
        importlib.reload(kk_studio_scene_importer)

import bpy
from . import parser
from . import resolver
from . import mesh_loader
from . import retarget
from . import com_tools
from . import kk_studio_scene_importer

from .parser import KKStudioParser
from .resolver import KKItemResolver
from .mesh_loader import KKMeshLoader
from .retarget import (
    load_base_skeleton_data,
    find_com_append_blend,
    append_com_body,
    setup_kk_to_com_transfer,
    KK_OT_TransferToCOM,
)
from .com_tools import (
    KK_OT_CleanOccludedGeometry,
    KK_OT_MergeSelectedProps,
)
from .kk_studio_scene_importer import (
    KKStudioSceneProperties,
    KK_OT_ReindexDatabase,
    KK_OT_ImportScene,
    KK_PT_StudioImporterPanel,
    register,
    unregister,
)

if __name__ == '__main__':
    register()
