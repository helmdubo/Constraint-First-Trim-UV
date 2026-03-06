"""HOTSPOTUV_PT_Panel — Main sidebar panel in View3D."""

import bpy


class HOTSPOTUV_PT_Panel(bpy.types.Panel):
    bl_label = "Hotspot UV"
    bl_idname = "HOTSPOTUV_PT_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Hotspot UV"

    def draw(self, context):
        layout = self.layout
        s = context.scene.hotspotuv_settings
        col = layout.column(align=True)
        col.prop(s, "target_texel_density")
        col.prop(s, "texture_size")
        col.prop(s, "uv_scale")
        col.prop(s, "uv_range_limit")
        layout.separator()
        col = layout.column(align=True)
        col.label(text="Face Tools:")
        col.operator("hotspotuv.unwrap_faces", text="UV Unwrap Faces", icon="UV")

        layout.separator()
        col = layout.column(align=True)
        col.label(text="Edge Tools:")
        col.operator("hotspotuv.manual_dock", text="Manual Dock Islands", icon="SNAP_ON")

        layout.separator()
        col = layout.column(align=True)
        col.label(text="Utility Tools:")
        col.operator("hotspotuv.select_similar", text="Select Similar Islands", icon="RESTRICT_SELECT_OFF")
        col.operator("hotspotuv.stack_similar", text="Stack Similar Islands", icon="ALIGN_CENTER")

        layout.separator()
        col = layout.column(align=True)
        col.label(text="Debug:")
        row = col.row(align=True)
        row.operator("hotspotuv.debug_analysis", text="Analyze", icon="VIEWZOOM")
        row.operator("hotspotuv.debug_clear", text="Clear", icon="X")
