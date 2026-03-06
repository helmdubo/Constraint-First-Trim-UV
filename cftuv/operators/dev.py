"""Development helper operators."""

import bpy


class HOTSPOTUV_OT_RefreshAddon(bpy.types.Operator):
    """Reload Blender scripts to apply local addon file changes."""

    bl_idname = "hotspotuv.refresh_addon"
    bl_label = "Refresh Addon"
    bl_description = "Reload all scripts so local changes in the symlinked addon are applied"
    bl_options = {'REGISTER'}

    def execute(self, context):
        if bpy.ops.script.reload.poll():
            bpy.ops.script.reload()
            self.report({'INFO'}, "Scripts reloaded. Hotspot UV updated from local files.")
            return {'FINISHED'}

        self.report({'ERROR'}, "Script reload is unavailable in the current context")
        return {'CANCELLED'}
