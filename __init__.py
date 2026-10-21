bl_info = {
    "name": "Koikatsu Studio Scene Importer",
    "author": "rinasaurus",
    "version": (1, 4, 3),
    "blender": (3, 0, 0),
    "location": "3D Viewport > Sidebar (N) > KK Studio",
    "description": "Imports Koikatsu Studio scene cards into Blender without characters, preserving exact hierarchy, transforms, multi-part meshes, and tinted textures for COM3D2 export.",
    "category": "Import-Export",
}

from .kk_studio_scene_importer import (
    KKStudioParser,
    KKItemResolver,
    KKMeshLoader,
    KKStudioSceneProperties,
    KK_OT_ReindexDatabase,
    KK_OT_ImportScene,
    KK_PT_StudioImporterPanel,
    register,
    unregister,
)

if __name__ == '__main__':
    register()
