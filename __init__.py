from .kk_studio_scene_importer import (
    bl_info,
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
