"""HOTSPOTUV_OT_ManualDock — Manual dock operator."""

import bpy
import bmesh
from bpy.props import EnumProperty, BoolProperty

from cftuv.config import validate_edit_mesh
from cftuv.solver.docking import build_island_graph, dock_all_chains


class HOTSPOTUV_OT_ManualDock(bpy.types.Operator):
    bl_idname = "hotspotuv.manual_dock"
    bl_label = "Manual Dock Islands"
    bl_description = "Dock UV islands based on selected boundary edges (sharp/seam)."
    bl_options = {"REGISTER", "UNDO"}

    direction: EnumProperty(
        name="Direction",
        items=[
            ('AUTO', 'Auto', 'Larger 3D area island becomes root anchor'),
            ('REVERSE', 'Reverse', 'Smaller 3D area island becomes root anchor')
        ],
        default='AUTO'
    )

    fit_vertices: BoolProperty(
        name="Fit Vertices",
        description="Move target edge vertices to match anchor edge positions",
        default=True
    )

    unwrap_interior: BoolProperty(
        name="Unwrap Interior (Conformal)",
        description="Relax the rest of the island while keeping fitted vertices pinned",
        default=False
    )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "direction")
        layout.prop(self, "fit_vertices")

        col = layout.column()
        col.enabled = self.fit_vertices
        col.prop(self, "unwrap_interior")

    def execute(self, context):
        valid, error, bm = validate_edit_mesh(context, require_selection=True, selection_type='EDGE')
        if not valid:
            self.report({"WARNING"}, error)
            return {"CANCELLED"}

        try:
            orig_edge_sel = [e.index for e in bm.edges if e.select]

            sel_edges = [e for e in bm.edges if e.select and (not e.smooth or e.seam)]

            if not sel_edges:
                self.report({"WARNING"}, "No boundary edges selected (must be sharp or seam)")
                return {"CANCELLED"}

            islands, graph, face_to_island = build_island_graph(sel_edges, bm)
            if not islands:
                self.report({"WARNING"}, "No valid islands found")
                return {"CANCELLED"}

            docked_count, bm = dock_all_chains(
                islands, graph, bm, context, self.direction, self.fit_vertices, self.unwrap_interior
            )

            if docked_count == 0:
                self.report({"WARNING"}, "No island pairs found for docking")
                return {"CANCELLED"}

            for f in bm.faces:
                f.select = False
            for e_idx in orig_edge_sel:
                if e_idx < len(bm.edges):
                    bm.edges[e_idx].select = True

            bmesh.update_edit_mesh(context.edit_object.data)
            self.report({"INFO"}, f"Docked {docked_count} island(s) across all chains")
            return {"FINISHED"}

        except Exception as e:
            self.report({"ERROR"}, f"Docking failed: {str(e)}")
            return {"CANCELLED"}
