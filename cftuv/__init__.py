"""Constraint-First Trim UV (CFTUV) — Blender addon for architectural trim sheet UV mapping.

bl_info, register/unregister, and top-level imports.
"""

import bpy
from bpy.props import PointerProperty

from .config import HOTSPOTUV_Settings
from .operators.unwrap_faces import HOTSPOTUV_OT_UnwrapFaces
from .operators.manual_dock import HOTSPOTUV_OT_ManualDock
from .operators.select_similar import HOTSPOTUV_OT_SelectSimilar
from .operators.stack_similar import HOTSPOTUV_OT_StackSimilar
from .operators.debug import HOTSPOTUV_OT_DebugAnalysis, HOTSPOTUV_OT_DebugClear, GP_DEBUG_PREFIX
from .operators.dev import HOTSPOTUV_OT_RefreshAddon
from .ui.panel import HOTSPOTUV_PT_Panel

bl_info = {
    "name": "Hotspot UV + Mesh Decals (Unified Adaptive)",
    "author": "Tech Artist & AI",
    "version": (2, 5, 7),
    "blender": (3, 0, 0),
    "location": "View3D > Sidebar > Hotspot UV",
    "description": "Constraint-First Trim UV: Three-layer (Form/Semantic/Topology) system for trim sheet workflows.",
    "category": "UV",
}

classes = (
    HOTSPOTUV_Settings,
    HOTSPOTUV_OT_UnwrapFaces,
    HOTSPOTUV_OT_ManualDock,
    HOTSPOTUV_OT_SelectSimilar,
    HOTSPOTUV_OT_StackSimilar,
    HOTSPOTUV_OT_DebugAnalysis,
    HOTSPOTUV_OT_DebugClear,
    HOTSPOTUV_OT_RefreshAddon,
    HOTSPOTUV_PT_Panel,
)


def register():
    """Register all addon classes with Blender."""
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.hotspotuv_settings = PointerProperty(type=HOTSPOTUV_Settings)


def unregister():
    """Unregister all addon classes from Blender."""
    for obj in list(bpy.data.objects):
        if obj.name.startswith(GP_DEBUG_PREFIX):
            bpy.data.objects.remove(obj, do_unlink=True)
    if hasattr(bpy.types.Scene, "hotspotuv_settings"):
        del bpy.types.Scene.hotspotuv_settings
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
