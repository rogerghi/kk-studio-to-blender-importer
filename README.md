# Koikatsu Studio Scene Importer for Blender

Blender 3.0+ add-on to import Koikatsu Studio scene cards (.png) directly into Blender, preserving exact hierarchy, transforms, multi-part meshes, and material tints.

## Branches
- main: **v1.4.1** - Stable version. Imports scene props and environment cleanly without characters.
- test-char-pose: **v1.5.3** - Full COM3D2 material and shader alignment, vectorized CIELAB ColorMask texture baking, scene deduplication, and character pose retargeting.

### Version History
- **v1.5.3**:
  - Implemented full COM3D2 material standard compliance for CM3D2 Converter in Blender 4.2 (`_MainTex`, `_ShadowTex`, `_ToonRamp`, `_ShadowRateToon`, `_Color`, `_ShadowColor`, `_RimColor`, `_OutlineColor`, `_Shininess`, `_OutlineWidth`, `_RimPower`, `_RimShift`).
  - Added automatic hook into CM3D2 Converter's `COM3D2 Shader` and `Toon Vector` node trees for viewport toon shading and 100% compliant `.model` export.
  - Implemented vectorized CIELAB ($L^*, a^*, b^*$) ColorMask texture baking using NumPy, preserving base texture luminance, highlights, and shadow folds without color muddiness.
  - Added scene-wide prop texture pre-scan and deduplication: hundreds of identical objects share single baked textures and materials (e.g. 1,594 objects map cleanly to just 40 unique materials).
- **v1.5.2**:
  - Added "Simplify Bone Hierarchy" UI toggle (default: ON) to exclude KK internal physics collision capsules (`k_f_*`), hitboxes (`cf_hit_*`), IK widget bones (`cf_pv_*`), and unused facial expression morph bones (`cf_J_Eye*`, `cf_J_Cheek*`, etc.).
  - Preserves 100% of essential COM body retargeting bones and all 54 accessory attachment points (`a_n_*`) with fully intact parent chains up to root.
  - Reduces KK armature clutter from 435 bones down to 167 clean bones while preserving exact 0.000000m world transforms for all attached accessories and props.
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
