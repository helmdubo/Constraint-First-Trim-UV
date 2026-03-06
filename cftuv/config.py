"""Configuration globals and settings PropertyGroup for CFTUV."""

import bpy
import bmesh
from mathutils import Vector
from bpy.props import PointerProperty, IntProperty, FloatProperty, EnumProperty, BoolProperty

# ============================================================
# CONFIGURATION GLOBALS
# ============================================================

TARGET_TEXEL_DENSITY = 512
TEXTURE_SIZE         = 2048
UV_SCALE_MULTIPLIER  = 1.0
FINAL_UV_SCALE       = 0.25
UV_RANGE_LIMIT       = 16.0
WORLD_UP             = Vector((0, 0, 1))

# ============================================================
# UI SETTINGS
# ============================================================

class HOTSPOTUV_Settings(bpy.types.PropertyGroup):
    target_texel_density: IntProperty(name="Target Texel Density (px/m)", default=512, min=1)
    texture_size: IntProperty(name="Texture Size", default=2048, min=1)
    uv_scale: FloatProperty(name="Custom Scale Multiplier", default=1.0, min=0.0001)
    uv_range_limit: IntProperty(name="UV Range Limit (Tiles)", default=16, min=0)

def _apply_settings_to_globals(settings):
    global TARGET_TEXEL_DENSITY, TEXTURE_SIZE, UV_SCALE_MULTIPLIER, FINAL_UV_SCALE, UV_RANGE_LIMIT
    TARGET_TEXEL_DENSITY = int(settings.target_texel_density)
    TEXTURE_SIZE         = int(settings.texture_size)
    UV_SCALE_MULTIPLIER  = float(settings.uv_scale)
    UV_RANGE_LIMIT       = float(settings.uv_range_limit)
    FINAL_UV_SCALE = (TARGET_TEXEL_DENSITY / TEXTURE_SIZE) * UV_SCALE_MULTIPLIER

# ============================================================
# VALIDATION HELPERS
# ============================================================

def validate_edit_mesh(context, require_selection=True, selection_type='FACE'):
    """
    Валидация контекста для операторов.
    Возвращает (success, error_message, bm)
    """
    obj = context.object
    if obj is None:
        return False, "No active object", None
    if obj.type != 'MESH':
        return False, "Active object is not a mesh", None
    if obj.mode != 'EDIT':
        return False, "Must be in Edit Mode", None

    mesh = obj.data
    if len(mesh.vertices) == 0:
        return False, "Mesh has no vertices", None

    bm = bmesh.from_edit_mesh(mesh)
    bm.faces.ensure_lookup_table()
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()

    if require_selection:
        if selection_type == 'FACE':
            if not any(f.select for f in bm.faces):
                return False, "No faces selected", bm
        elif selection_type == 'EDGE':
            if not any(e.select for e in bm.edges):
                return False, "No edges selected", bm

    return True, "", bm
