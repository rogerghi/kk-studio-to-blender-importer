# Koikatsu Studio Scene Importer for Blender

Blender 3.0+ add-on to import Koikatsu Studio scene cards (.png) directly into Blender, preserving exact hierarchy, transforms, multi-part meshes, and material tints.

## Branches
- main: **v1.4.1** - Stable version. Imports scene props and environment cleanly without characters.
- test-char-pose: **v1.5.1** - Character armature generation with embedded body slider and KKABMX bone modifier resizing, attached props placement, and COM3D2 pose retargeting.

### Version History
- **v1.5.1**:
  - Resized imported KK character armatures to match scene height and bone lengths by parsing embedded character cards (`shapeValueBody` sliders from `Custom` and `KKABMX` bone modifiers from `KKEx`).
  - Fixed KK-to-COM3D2 bone pairing (`Bip01 Pelvis` to `cf_j_waist02`, spine chains, twist/helper bones) and canonical T-pose offset math so COM3D2 body rig mirrors the scene pose without resizing COM bones.
  - Deferred COM driver setup until final scene world transforms are evaluated.
- **v1.5.0**:
  - Initial experimental character pose armatures, FK sampling, and attached props import.
- **v1.4.3**:
  - Fixed trapezoid object rotation and non-uniform scale distortion by baking internal prefab transforms into mesh data.
- **v1.4.2**:
  - Added "Import Meshless Objects" option to avoid blocking placeholder rectangles.
- **v1.4.1**:
  - Scene props and environment import with hierarchy, multi-part meshes, and tints.

## Requirements
- Blender 3.0+
- UnityPy
- msgpack
- Pillow
