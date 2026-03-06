"""HOTSPOTUV_OT_SelectSimilar — Select similar islands operator."""

import bpy
import bmesh

from cftuv.config import validate_edit_mesh
from cftuv.analysis.geometry import get_expanded_islands, IslandInfo, analyze_island_properties


class HOTSPOTUV_OT_SelectSimilar(bpy.types.Operator):
    bl_idname = "hotspotuv.select_similar"
    bl_label = "Select Similar Islands"
    bl_description = "Selects all islands in the mesh with the same 3D area as the current selection."
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        valid, error, bm = validate_edit_mesh(context, require_selection=True, selection_type='FACE')
        if not valid:
            self.report({"WARNING"}, error)
            return {"CANCELLED"}

        try:
            sel_faces = set(f for f in bm.faces if f.select)

            visible_faces = [f for f in bm.faces if not f.hide]
            islands = []
            for idx, group in enumerate(get_expanded_islands(bm, visible_faces)):
                isl = IslandInfo(group['full'], idx)
                analyze_island_properties(isl)
                islands.append(isl)

            target_areas = [isl.area for isl in islands if any(f in sel_faces for f in isl.faces)]
            if not target_areas:
                self.report({"WARNING"}, "Could not determine target area from selection")
                return {"CANCELLED"}

            matched_count = 0
            for isl in islands:
                if any(t_area > 0 and abs(isl.area - t_area) / t_area <= 0.02 for t_area in target_areas):
                    matched_count += 1
                    for f in isl.faces: f.select = True

            bmesh.update_edit_mesh(context.edit_object.data)
            self.report({"INFO"}, f"Selected {matched_count} similar islands.")
            return {"FINISHED"}

        except Exception as e:
            self.report({"ERROR"}, f"Select similar failed: {str(e)}")
            return {"CANCELLED"}
