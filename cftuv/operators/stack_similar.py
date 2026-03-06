"""HOTSPOTUV_OT_StackSimilar — Stack similar islands operator."""

import bpy
import bmesh
import math
from mathutils import Vector

from cftuv.config import validate_edit_mesh, _apply_settings_to_globals
from cftuv.analysis.geometry import get_expanded_islands, IslandInfo, analyze_island_properties


class HOTSPOTUV_OT_StackSimilar(bpy.types.Operator):
    bl_idname = "hotspotuv.stack_similar"
    bl_label = "Stack Similar Islands"
    bl_description = "Groups selected islands by area and perfectly aligns them with 4-way rotation lock."
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        _apply_settings_to_globals(context.scene.hotspotuv_settings)

        valid, error, bm = validate_edit_mesh(context, require_selection=True, selection_type='FACE')
        if not valid:
            self.report({"WARNING"}, error)
            return {"CANCELLED"}

        try:
            sel_faces = [f for f in bm.faces if f.select]

            islands = []
            for idx, group in enumerate(get_expanded_islands(bm, sel_faces)):
                isl = IslandInfo(group['full'], idx)
                analyze_island_properties(isl)
                islands.append(isl)

            uv_layer = bm.loops.layers.uv.verify()
            islands.sort(key=lambda x: x.area, reverse=True)

            groups, current_group = [], []
            for isl in islands:
                if not current_group or (current_group[0].area > 0 and abs(isl.area - current_group[0].area) / current_group[0].area <= 0.02):
                    current_group.append(isl)
                else:
                    groups.append(current_group)
                    current_group = [isl]
            if current_group: groups.append(current_group)

            def get_centered_unique_uvs(island):
                uvs, center, count = [], Vector((0.0, 0.0)), 0
                for f in island.faces:
                    for l in f.loops:
                        uvs.append(l[uv_layer].uv.copy())
                        center += l[uv_layer].uv
                        count += 1
                if count == 0: return [], Vector((0.0, 0.0))
                center /= count
                unique_uvs = []
                for uv in uvs:
                    uv_centered = uv - center
                    if not any((uv_centered - u).length_squared < 1e-5 for u in unique_uvs): unique_uvs.append(uv_centered)
                return unique_uvs, center

            stacked_count = 0
            for group in groups:
                if len(group) < 2: continue
                anchor_uvs, anchor_center = get_centered_unique_uvs(group[0])
                if not anchor_uvs: continue

                for i in range(1, len(group)):
                    source_isl = group[i]
                    source_uvs, source_center = get_centered_unique_uvs(source_isl)
                    if not source_uvs: continue

                    best_angle, min_err = 0.0, float('inf')
                    for angle in [0.0, math.pi/2, math.pi, 3*math.pi/2]:
                        err, cos_a, sin_a = 0.0, math.cos(angle), math.sin(angle)
                        for suv in source_uvs:
                            rx, ry = suv.x * cos_a - suv.y * sin_a, suv.x * sin_a + suv.y * cos_a
                            err += min((rx - auv.x)**2 + (ry - auv.y)**2 for auv in anchor_uvs)
                        if err < min_err:
                            min_err, best_angle = err, angle

                    cos_a, sin_a = math.cos(best_angle), math.sin(best_angle)
                    for f in source_isl.faces:
                        for l in f.loops:
                            uv = l[uv_layer].uv - source_center
                            rx, ry = uv.x * cos_a - uv.y * sin_a, uv.x * sin_a + uv.y * cos_a
                            l[uv_layer].uv = Vector((rx, ry)) + anchor_center
                    stacked_count += 1

            bmesh.update_edit_mesh(context.edit_object.data)
            self.report({"INFO"}, f"Stacked {stacked_count} identical islands.")
            return {"FINISHED"}

        except Exception as e:
            self.report({"ERROR"}, f"Stack similar failed: {str(e)}")
            return {"CANCELLED"}
