"""Debug analysis + visualization operators.

HOTSPOTUV_OT_DebugAnalysis, HOTSPOTUV_OT_DebugClear.
Creates Grease Pencil objects for visual debugging of patches, frames, and constraints.
"""

import bpy
import bmesh
from mathutils import Vector

from ..config import validate_edit_mesh
from ..analysis.frame import analyze_all_patches

# ============================================================
# DEBUG VISUALIZATION (Grease Pencil)
# ============================================================

GP_DEBUG_PREFIX = "CFTUV_Debug_"

_GP_STYLES = {
    'U_axis':   (1.0, 0.15, 0.15, 1.0),
    'V_axis':   (0.15, 1.0, 0.15, 1.0),
    'Normal':   (0.2, 0.2, 1.0, 1.0),
    'H_FRAME':  (1.0, 0.85, 0.0, 1.0),
    'V_FRAME':  (0.0, 0.85, 0.85, 1.0),
    'FREE':     (0.5, 0.5, 0.5, 0.6),
    'HOLE':     (0.2, 0.2, 0.6, 0.8),
}


def _get_gp_debug_name(source_obj):
    return GP_DEBUG_PREFIX + source_obj.name


def _get_or_create_gp_object(source_obj):
    """Находит или создаёт GP объект для debug визуализации."""
    gp_name = _get_gp_debug_name(source_obj)

    if gp_name in bpy.data.objects:
        gp_obj = bpy.data.objects[gp_name]
        if gp_obj.type == 'GPENCIL':
            return gp_obj
        bpy.data.objects.remove(gp_obj, do_unlink=True)

    gp_data = bpy.data.grease_pencils.new(gp_name)
    gp_obj = bpy.data.objects.new(gp_name, gp_data)
    bpy.context.scene.collection.objects.link(gp_obj)

    gp_obj.matrix_world = source_obj.matrix_world.copy()

    return gp_obj


def _ensure_gp_layer(gp_data, layer_name, color_rgba):
    """Создаёт или очищает GP layer + material."""
    mat_name = f"CFTUV_{layer_name}"
    if mat_name in bpy.data.materials:
        mat = bpy.data.materials[mat_name]
    else:
        mat = bpy.data.materials.new(mat_name)
        bpy.data.materials.create_gpencil_data(mat)

    mat.grease_pencil.color = color_rgba[:4]
    mat.grease_pencil.show_fill = False

    mat_idx = None
    for i, slot in enumerate(gp_data.materials):
        if slot and slot.name == mat_name:
            mat_idx = i
            break
    if mat_idx is None:
        gp_data.materials.append(mat)
        mat_idx = len(gp_data.materials) - 1

    if layer_name in gp_data.layers:
        layer = gp_data.layers[layer_name]
        layer.clear()
    else:
        layer = gp_data.layers.new(layer_name, set_active=False)

    if not layer.frames:
        frame = layer.frames.new(0)
    else:
        frame = layer.frames[0]

    return frame, mat_idx


def _add_gp_stroke(frame, points, mat_idx, line_width=4):
    """Добавляет stroke из списка Vector точек (local space)."""
    if len(points) < 2:
        return
    stroke = frame.strokes.new()
    stroke.material_index = mat_idx
    stroke.line_width = line_width
    stroke.points.add(len(points))
    for i, p in enumerate(points):
        stroke.points[i].co = (p.x, p.y, p.z)
        stroke.points[i].strength = 1.0
        stroke.points[i].pressure = 1.0


def _clear_gp_debug(source_obj):
    """Удаляет GP debug объект для данного source."""
    gp_name = _get_gp_debug_name(source_obj)
    if gp_name in bpy.data.objects:
        obj = bpy.data.objects[gp_name]
        bpy.data.objects.remove(obj, do_unlink=True)
    if gp_name in bpy.data.grease_pencils:
        bpy.data.grease_pencils.remove(bpy.data.grease_pencils[gp_name])


def create_debug_visualization(patch_results, source_obj):
    """Создаёт GP strokes для визуализации анализа."""
    gp_obj = _get_or_create_gp_object(source_obj)
    gp_data = gp_obj.data
    if hasattr(gp_data, 'pixel_factor'):
        gp_data.pixel_factor = 16.0

    frames_and_mats = {}
    for style_name, color in _GP_STYLES.items():
        frame, mat_idx = _ensure_gp_layer(gp_data, style_name, color)
        frames_and_mats[style_name] = (frame, mat_idx)

    for pi, patch in enumerate(patch_results):
        c = patch['centroid']
        axis_len = 0.15

        f, m = frames_and_mats['U_axis']
        _add_gp_stroke(f, [c, c + patch['seed_t'] * axis_len], m, line_width=8)

        f, m = frames_and_mats['V_axis']
        _add_gp_stroke(f, [c, c + patch['seed_b'] * axis_len], m, line_width=8)

        f, m = frames_and_mats['Normal']
        _add_gp_stroke(f, [c, c + patch['normal'] * axis_len * 0.6], m, line_width=6)

        for lp in patch['loops']:
            for seg in lp.get('segments', []):
                vert_cos = seg.get('vert_cos', [])
                if len(vert_cos) < 2:
                    continue

                kind = seg.get('loop_kind', 'OUTER')
                role = seg.get('frame_role', 'FREE')

                if kind == 'HOLE':
                    style = 'HOLE'
                    width = 3
                elif role == 'H_FRAME':
                    style = 'H_FRAME'
                    width = 6
                elif role == 'V_FRAME':
                    style = 'V_FRAME'
                    width = 6
                else:
                    style = 'FREE'
                    width = 3

                f, m = frames_and_mats[style]
                _add_gp_stroke(f, vert_cos, m, line_width=width)


class HOTSPOTUV_OT_DebugAnalysis(bpy.types.Operator):
    bl_idname = "hotspotuv.debug_analysis"
    bl_label = "Debug: Analyze Patches"
    bl_description = "Run patch/frame analysis and create GP debug strokes"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        valid, error, bm = validate_edit_mesh(context, require_selection=False)
        if not valid:
            self.report({"WARNING"}, error)
            return {"CANCELLED"}

        obj = context.active_object

        original_seams = [e.seam for e in bm.edges]
        for e in bm.edges:
            if not e.smooth:
                e.seam = True

        sel_faces = [f for f in bm.faces if f.select]
        if not sel_faces:
            sel_faces = list(bm.faces)

        patch_results = analyze_all_patches(bm, sel_faces)

        for i, e in enumerate(bm.edges):
            e.seam = original_seams[i]
        bmesh.update_edit_mesh(obj.data)

        bpy.ops.object.mode_set(mode='OBJECT')
        create_debug_visualization(patch_results, obj)
        bpy.ops.object.mode_set(mode='EDIT')

        total_patches = len(patch_results)
        total_h = sum(1 for p in patch_results for s in p['all_segments'] if s['frame_role'] == 'H_FRAME')
        total_v = sum(1 for p in patch_results for s in p['all_segments'] if s['frame_role'] == 'V_FRAME')
        total_free = sum(1 for p in patch_results for s in p['all_segments'] if s['frame_role'] == 'FREE')
        total_holes = sum(1 for p in patch_results for lp in p['loops'] if lp['kind'] == 'HOLE')
        total_segs = sum(len(p['all_segments']) for p in patch_results)

        self.report({"INFO"},
            f"Patches: {total_patches} | Segments: {total_segs} | H-frame: {total_h} V-frame: {total_v} Free: {total_free} Holes: {total_holes}")
        return {"FINISHED"}


class HOTSPOTUV_OT_DebugClear(bpy.types.Operator):
    bl_idname = "hotspotuv.debug_clear"
    bl_label = "Debug: Clear"
    bl_description = "Remove debug GP strokes for active object"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        obj = context.active_object
        if obj:
            was_edit = (obj.mode == 'EDIT')
            if was_edit:
                bpy.ops.object.mode_set(mode='OBJECT')
            _clear_gp_debug(obj)
            if was_edit:
                bpy.ops.object.mode_set(mode='EDIT')
        return {"FINISHED"}
