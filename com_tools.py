import bpy
import bmesh
from mathutils import Matrix, Vector

class KK_OT_CleanOccludedGeometry(bpy.types.Operator):
    bl_idname = "kk_studio.clean_occluded_geometry"
    bl_label = "Clean Occluded / Hidden Faces"
    bl_description = "Removes interior hidden faces and cleans loose geometry without affecting UVs or materials"
    bl_options = {'REGISTER', 'UNDO'}

    merge_dist: bpy.props.FloatProperty(
        name="Weld Threshold",
        default=0.0001,
        min=0.0,
        max=0.01,
        precision=5,
        description="Threshold to merge duplicate coincident vertices"
    )

    remove_loose: bpy.props.BoolProperty(
        name="Delete Loose Verts/Edges",
        default=True,
        description="Clean unlinked vertices and edges"
    )

    delete_interior: bpy.props.BoolProperty(
        name="Delete Interior Hidden Faces",
        default=True,
        description="Detect and delete interior faces hidden inside closed geometry"
    )

    @classmethod
    def poll(cls, context):
        return any(obj.type == 'MESH' for obj in context.selected_objects)

    def execute(self, context):
        mesh_objs = [obj for obj in context.selected_objects if obj.type == 'MESH']
        if not mesh_objs:
            self.report({'WARNING'}, "No mesh objects selected.")
            return {'CANCELLED'}

        total_cleaned = 0
        for obj in mesh_objs:
            bm = bmesh.new()
            bm.from_mesh(obj.data)

            # 1. Weld coincident vertices without breaking UV boundaries
            if self.merge_dist > 0.0:
                bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=self.merge_dist)

            # 2. Delete loose vertices and edges
            if self.remove_loose:
                loose_verts = [v for v in bm.verts if not v.link_edges]
                bmesh.ops.delete(bm, geom=loose_verts, context='VERTS')
                loose_edges = [e for e in bm.edges if not e.link_faces]
                bmesh.ops.delete(bm, geom=loose_edges, context='EDGES')

            # 3. Delete zero-area / degenerate faces
            degen_faces = [f for f in bm.faces if f.calc_area() < 1e-7]
            if degen_faces:
                bmesh.ops.delete(bm, geom=degen_faces, context='FACES')

            # 4. Remove completely enclosed interior faces (faces where all edges connect to 3+ faces)
            if self.delete_interior:
                interior_faces = [f for f in bm.faces if all(len(e.link_faces) > 2 for e in f.edges)]
                if interior_faces:
                    total_cleaned += len(interior_faces)
                    bmesh.ops.delete(bm, geom=interior_faces, context='FACES')

            bm.to_mesh(obj.data)
            bm.free()
            obj.data.update()

        self.report({'INFO'}, f"Cleaned geometry across {len(mesh_objs)} objects! ({total_cleaned} interior faces removed)")
        return {'FINISHED'}


class KK_OT_MergeSelectedProps(bpy.types.Operator):
    bl_idname = "kk_studio.merge_selected_props"
    bl_label = "Merge Selected Meshes into COM3D2 Model"
    bl_description = "Non-destructively duplicates and joins selected mesh objects into a single COM3D2 .model-ready mesh"
    bl_options = {'REGISTER', 'UNDO'}

    merged_name: bpy.props.StringProperty(
        name="Model Name",
        default="Merged_Prop",
        description="Name of the merged COM3D2 object and root bone"
    )

    clean_first: bpy.props.BoolProperty(
        name="Auto-Clean Loose Geometry",
        default=True,
        description="Weld duplicate vertices and remove degenerate faces"
    )

    add_root_bone: bpy.props.BoolProperty(
        name="Add COM3D2 Root Armature",
        default=True,
        description="Creates a base armature and assigns 100% vertex weights for COM3D2 export"
    )

    def execute(self, context):
        selected_meshes = [obj for obj in context.selected_objects if obj.type == 'MESH']
        if not selected_meshes:
            self.report({'WARNING'}, "Please select at least one mesh object to merge.")
            return {'CANCELLED'}

        # Target collection for merged exports
        col_name = "COM3D2_Merged_Exports"
        if col_name not in bpy.data.collections:
            target_col = bpy.data.collections.new(col_name)
            bpy.context.scene.collection.children.link(target_col)
        else:
            target_col = bpy.data.collections[col_name]

        # Duplicate selected meshes non-destructively with world transforms applied
        copies = []
        for obj in selected_meshes:
            new_mesh = obj.data.copy()
            new_obj = bpy.data.objects.new(f"{obj.name}_merge_copy", new_mesh)
            new_obj.matrix_world = obj.matrix_world.copy()
            target_col.objects.link(new_obj)

            # Apply world transforms to mesh data directly
            new_obj.data.transform(new_obj.matrix_world)
            new_obj.matrix_world = Matrix.Identity(4)

            # Copy materials from object slots (or mesh data)
            new_obj.data.materials.clear()
            for slot in obj.material_slots:
                if slot.material:
                    new_obj.data.materials.append(slot.material)

            copies.append(new_obj)

        # Deselect all and select copies
        for obj in context.selected_objects:
            obj.select_set(False)

        for c in copies:
            c.select_set(True)
        context.view_layer.objects.active = copies[0]

        # Join objects into one mesh
        if len(copies) > 1:
            bpy.ops.object.join()

        merged_obj = context.view_layer.objects.active
        merged_obj.name = self.merged_name

        # Ensure all materials have valid COM3D2 properties
        for slot in merged_obj.material_slots:
            if slot.material:
                if "shader1" not in slot.material:
                    slot.material["shader1"] = "CM3D2/Toony_Lighted"
                if "shader2" not in slot.material:
                    slot.material["shader2"] = "CM3D2__Toony_Lighted"

        # Auto-clean geometry
        if self.clean_first:
            bm = bmesh.new()
            bm.from_mesh(merged_obj.data)
            bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.0001)
            loose_verts = [v for v in bm.verts if not v.link_edges]
            bmesh.ops.delete(bm, geom=loose_verts, context='VERTS')
            loose_edges = [e for e in bm.edges if not e.link_faces]
            bmesh.ops.delete(bm, geom=loose_edges, context='EDGES')
            degen_faces = [f for f in bm.faces if f.calc_area() < 1e-7]
            if degen_faces:
                bmesh.ops.delete(bm, geom=degen_faces, context='FACES')
            bm.to_mesh(merged_obj.data)
            bm.free()
            merged_obj.data.update()

        # Add single root bone armature & weight for COM3D2 static prop
        if self.add_root_bone:
            arm_data = bpy.data.armatures.new(f"{self.merged_name}_Armature")
            arm_obj = bpy.data.objects.new(f"{self.merged_name}_Armature", arm_data)
            target_col.objects.link(arm_obj)

            # Edit mode: create root bone
            context.view_layer.objects.active = arm_obj
            bpy.ops.object.mode_set(mode='EDIT')
            bone_name = "BaseBone"
            eb = arm_data.edit_bones.new(bone_name)
            eb.head = Vector((0.0, 0.0, 0.0))
            eb.tail = Vector((0.0, 0.0, 0.2))
            bpy.ops.object.mode_set(mode='OBJECT')

            arm_data["BaseBone"] = bone_name

            # Parent mesh to armature & assign 100% weight
            context.view_layer.objects.active = merged_obj
            vg = merged_obj.vertex_groups.new(name=bone_name)
            all_verts = [v.index for v in merged_obj.data.vertices]
            vg.add(all_verts, 1.0, 'REPLACE')

            merged_obj.parent = arm_obj
            mod = merged_obj.modifiers.new(name="Armature", type='ARMATURE')
            mod.object = arm_obj

        vert_count = len(merged_obj.data.vertices)
        if vert_count > 65535:
            self.report({'WARNING'}, f"Merged object has {vert_count} vertices (exceeds COM3D2 65,535 limit by {vert_count - 65535}!). Split into smaller parts before export.")
        else:
            self.report({'INFO'}, f"Successfully created '{self.merged_name}' with {vert_count} vertices and {len(merged_obj.material_slots)} materials!")

        return {'FINISHED'}
