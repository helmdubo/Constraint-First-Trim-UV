"""HOTSPOTUV_OT_UnwrapFaces — Two-Pass unwrap + seam alignment operator."""

import bpy
import bmesh
from mathutils import Vector

from cftuv.config import validate_edit_mesh, _apply_settings_to_globals
from cftuv.analysis.geometry import get_expanded_islands, IslandInfo, analyze_island_properties, build_edge_based_links
from cftuv.solver.orient import orient_scale_and_position_island, normalize_uvs_to_origin
from cftuv.solver.align import align_connected_islands
from cftuv.solver.seam_align import align_split_seams_in_island, align_split_seams_between_islands


class HOTSPOTUV_OT_UnwrapFaces(bpy.types.Operator):
    bl_idname = "hotspotuv.unwrap_faces"
    bl_label = "UV Unwrap Faces"
    bl_description = "Two-Pass Unwrap: Pins selected core faces and seamlessly relaxes unselected chamfers."
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        _apply_settings_to_globals(context.scene.hotspotuv_settings)

        valid, error, bm = validate_edit_mesh(context, require_selection=True, selection_type='FACE')
        if not valid:
            self.report({"WARNING"}, error)
            return {"CANCELLED"}

        mesh = context.edit_object.data
        sel_faces = [f for f in bm.faces if f.select]

        original_seams = [e.seam for e in bm.edges]

        try:
            for e in bm.edges:
                if not e.smooth: e.seam = True

            # 1. АНАЛИЗ ВЫДЕЛЕНИЯ (Ядро vs Полный лоскут)
            islands_data = get_expanded_islands(bm, sel_faces)

            islands_indices = []
            for data in islands_data:
                islands_indices.append({
                    'full': [f.index for f in data['full']],
                    'core': [f.index for f in data['core']]
                })

            # 2. ПЕРВЫЙ ПРОХОД (UNWRAP ТОЛЬКО ЯДЕР)
            for f in bm.faces: f.select = False
            for data_idx in islands_indices:
                for i in data_idx['core']: bm.faces[i].select = True
            bmesh.update_edit_mesh(mesh)

            bpy.ops.uv.unwrap(method='CONFORMAL', margin=0.0)

            bm.free()
            bm = bmesh.from_edit_mesh(mesh)
            bm.faces.ensure_lookup_table(); bm.verts.ensure_lookup_table(); bm.edges.ensure_lookup_table()
            uv_layer = bm.loops.layers.uv.verify()

            for data_idx in islands_indices:
                core_faces = [bm.faces[i] for i in data_idx['core']]
                if not core_faces: continue

                core_island = IslandInfo(core_faces, 0)
                analyze_island_properties(core_island)

                orient_scale_and_position_island(uv_layer, core_island)

                for f in core_faces:
                    for l in f.loops: l[uv_layer].pin_uv = True

            # 3. ВТОРОЙ ПРОХОД (ДОРАЗВЕРТКА ФАСОК)
            for f in bm.faces: f.select = False
            for data_idx in islands_indices:
                for i in data_idx['full']: bm.faces[i].select = True
            bmesh.update_edit_mesh(mesh)

            bpy.ops.uv.unwrap(method='CONFORMAL', margin=0.0)

            bm.free()
            bm = bmesh.from_edit_mesh(mesh)
            bm.faces.ensure_lookup_table(); bm.verts.ensure_lookup_table(); bm.edges.ensure_lookup_table()
            uv_layer = bm.loops.layers.uv.verify()

            # 4. ОЧИСТКА И ДОКИНГ
            for i, e in enumerate(bm.edges): e.seam = original_seams[i]
            for f in bm.faces:
                for l in f.loops: l[uv_layer].pin_uv = False

            final_islands = []
            for idx, data_idx in enumerate(islands_indices):
                full_faces = [bm.faces[i] for i in data_idx['full']]
                isl = IslandInfo(full_faces, idx)
                analyze_island_properties(isl)
                final_islands.append(isl)

            links = build_edge_based_links(final_islands, bm)

            align_connected_islands(final_islands, links, uv_layer)
            align_split_seams_between_islands(final_islands, links, uv_layer)
            for isl in final_islands:
                align_split_seams_in_island(uv_layer, isl)
            normalize_uvs_to_origin(bm, uv_layer)

            for f in bm.faces: f.select = False
            for f_idx in [i for d in islands_indices for i in d['core']]:
                bm.faces[f_idx].select = True

            bmesh.update_edit_mesh(mesh)
            self.report({"INFO"}, "Two-Pass Unwrap: Cores positioned absolutely, chamfers seamlessly expanded.")
            return {"FINISHED"}

        except Exception as e:
            try:
                bm = bmesh.from_edit_mesh(mesh)
                bm.edges.ensure_lookup_table()
                for i, edge in enumerate(bm.edges):
                    if i < len(original_seams):
                        edge.seam = original_seams[i]
                bmesh.update_edit_mesh(mesh)
            except:
                pass
            self.report({"ERROR"}, f"Unwrap failed: {str(e)}")
            return {"CANCELLED"}
