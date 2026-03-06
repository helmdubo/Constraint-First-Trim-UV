# Constraint-First Trim UV (CFTUV)
## Spec-Driven Design Document

### Overview

**System name:** Constraint-First Trim UV (CFTUV)  
**Core principle:** Constraints before solve, not post-hoc repair.  
**Target user:** 3D Environment/Level Artist in video games development.  
**Target workflow:** Architectural trim sheet UV mapping (tile, trim, decal textures/atlas).  
**Platform:** Blender addon (3.0+ runtime target, 4.1 dev baseline), modular Python package under `cftuv/`.  
**Base:** Evolved from Hotspot UV addon (v2.4.0 → current v2.5.7).

---

### Architecture: Three-Layer System

#### Layer 1 — Form Analysis (Geometric)
Determines the physical shape properties of each patch (seam-separated face group).

**What exists (implemented):**
- `find_island_up()` — dual-strategy (direct up + derived up) orientation detection
- `calc_surface_basis()` — local U/V basis from face normal + island_up
- `analyze_island_properties()` — avg_normal, area, perimeter, WALL/FLOOR classification
- `build_patch_basis()` — full local basis per patch (centroid, normal, seed_t, seed_b)
- `find_seam_patches()` — flood fill patches separated by seam/sharp edges
- `find_patch_boundary_edges()` — topological boundary detection (1-face edges)
- `build_ordered_boundary_loops()` — ordered closed loops from boundary edges
- `classify_boundary_loops_3d()` — OUTER/HOLE via 2D projection + nesting depth
- `find_loop_corners()` — corner detection by angle threshold (v2.5.6: fixed formula)
- `split_loop_into_segments()` — split loops at corners
- `classify_segment_frame_role()` — H_FRAME/V_FRAME/FREE via local basis projection

**What's missing:**
- Constraint use of loop kinds in the solver:
  - OUTER boundary segments -> future frame candidates (pin + straighten)
  - HOLE boundary segments -> remain free and excluded from frame constraints
- Curvature analysis (flat / cylindrical / complex)
- Automatic "straight chain" detection on outer boundaries and inside patches

#### Layer 2 — Semantic Analysis (Topology-Driven)
Determines relationships between patches based on type and adjacency.

**What exists (partially):**
- WALL/FLOOR type classification via avg_normal dot WORLD_UP
- `build_edge_based_links()` — shared edges between patches, longest edge tracking
- `_is_valid_island_contact()` — contact validation by shared length / perimeter ratio

**What's missing (critical):**
- **Patch-to-patch relation types:**
  - DOCK — same type neighbors (WALL+WALL), rigid transform alignment
  - STITCH — different type neighbors (WALL+FLOOR, WALL+BEVEL), one-axis alignment only
  - IGNORE — too small contact or incompatible types
- BEVEL type detection (small area, sandwiched between larger patches)
- Junction/branching detection (T-junctions where generic seam healing must be suppressed)
- Currently `align_connected_islands()` skips pairs where `isl_A.type != isl_B.type` — this should become STITCH, not skip

#### Layer 3 — Constraint Assembly + Solve
Assembles constraints from Layers 1-2 and runs solver.

**What exists:**
- Two-Pass Unwrap: conformal core → orient/scale → pin core → conformal full
- `orient_scale_and_position_island()` — world-space projection via seed face
- `align_connected_islands()` — hybrid: edge direction for rotation, multi-vertex centroid for translation (v2.4.5+)
- Seam alignment functions (v2.4.11): `align_split_seams_in_island`, `align_split_seams_between_islands`
- Manual Dock operator with fit_vertices + unwrap_interior

**What's missing (critical):**
- **Frame straighten + pin before the final solve** - straighten OUTER H_FRAME/V_FRAME chains in UV, pin them, then run conformal. HOLE chains stay free.
- **Initialization strategy for the future solver** - reuse the current preliminary unwrap/orient result as the starting UV state, then apply frame constraints before the final relaxation pass.
- **Seam alignment as constraint, not post-hoc** - align seam before the final unwrap, not after
- **Unified constraint solve order:**
  1. Analyze patches (Layer 1)
  2. Classify relations (Layer 2)  
  3. Run preliminary unwrap/orient to get stable initial UVs
  4. Extract OUTER frame chains and straighten them in UV
  5. Pin frame + seam constraints
  6. Single conformal relaxation pass
  7. Align between islands (dock/stitch)

---

### Key Design Decisions

1. **"Not post-hoc repair"** — Constraints are established BEFORE the final conformal solve, not applied as corrections after.

2. **Frame = sparse, not cage** — Only a few structural edge chains are pinned. Over-constraining causes solver stress and local distortion. Frame segments must be H_FRAME or V_FRAME classified, not arbitrary boundary.

3. **Holes are always free** — Inner boundary loops (windows, doors) are never pinned. Only outer boundary frame segments are candidates.

4. **Junction rule** — If a seam vertex has degree > 2 seam edges, generic seam alignment is forbidden. Only relation-specific logic applies.

5. **Local coordinates from world-space** — All UV positions derived from `vert.co.dot(seed_t/seed_b) * FINAL_UV_SCALE`. This ensures deterministic, world-aligned UV regardless of unwrap artifacts.

6. **WORLD_UP assumption** — System assumes applied rotation on objects. `WORLD_UP = (0,0,1)` used in local space. Known limitation, documented.

---

### Problem History (Why CFTUV)

**Original problem:** Two-Pass Unwrap accumulates yaw (rotation) and drift (position) errors on long UV strips, particularly buildings wrapped around corners with bevels. Each bevel introduces micro-error in conformal unwrap; over 4+ bevels, seams visibly diverge.

**Approaches tried and results:**

| Version | Approach | Result |
|---------|----------|--------|
| v2.4.0 | Two-Pass (conformal core → orient → conformal full) | Works but yaw/drift on long strips |
| v2.4.4 | Dual-strategy find_island_up + least-squares align | Better orientation, but 90/180° flip bugs |
| v2.4.5 | Hybrid align (edge direction for angle, multi-vertex for position) | Fixes flip bugs, drift remains |
| v2.4.11 | Root-anchored alignment + seam alignment post-hoc | Good for simple cases, breaks on caps/T-junctions |
| v2.5.0 (attempt 1) | Quilt stitching (cut → project → stitch) | Failed: different normals → different UV bases → gaps |
| v2.5.0 (attempt 2) | Piecewise yaw correction per core_group | Rotation improved but drift not addressed |
| v2.5.0 (attempt 3) | Boundary straighten + pin + re-unwrap | Direction correct but classification wrong |
| v2.5.0 (attempt 4) | Seam alignment + corrective unwrap | Partial improvement |
| v2.5.5-6 | Patch analysis + frame classification + debug visualization | Infrastructure for CFTUV approach |

**Current status:** Boundary analysis is integrated into the addon (patch detection, OUTER/HOLE loops, corner splitting, frame role classification), and debug visualization now uses a Grease Pencil Data overlay. The UV solve pipeline still runs the current two-pass unwrap with post-hoc alignment; frame-constrained solve is not implemented yet.

---

### Legacy Single-File Origin (historical reference)

```
Hotspot_UV_v2_5_6.py
├── CONFIGURATION GLOBALS
├── UI SETTINGS (HOTSPOTUV_Settings)
├── GEOMETRY ANALYSIS
│   ├── IslandInfo, get_expanded_islands
│   ├── find_island_up (dual-strategy)
│   ├── analyze_island_properties
│   ├── build_edge_based_links
│   └── calc_surface_basis
├── PATCH & FRAME ANALYSIS ← NEW (CFTUV Layer 1)
│   ├── find_seam_patches
│   ├── find_patch_boundary_edges
│   ├── build_ordered_boundary_loops
│   ├── classify_boundary_loops_3d (OUTER/HOLE)
│   ├── build_patch_basis
│   ├── find_loop_corners
│   ├── split_loop_into_segments
│   ├── classify_segment_frame_role (H_FRAME/V_FRAME/FREE)
│   └── analyze_all_patches (orchestrator)
├── DEBUG VISUALIZATION ← NEW (Grease Pencil overlay)
│   ├── create_debug_visualization
│   └── HOTSPOTUV_OT_DebugAnalysis / DebugClear
├── HYBRID ALIGNMENT LOGIC
│   └── orient_scale_and_position_island
├── VALIDATION HELPERS
├── DOCKING & WELDING
│   ├── compute_best_fit_transform
│   ├── dock_island_to_anchor
│   ├── build_island_graph, dock_all_chains, dock_chain_bfs_layered
│   ├── align_connected_islands (hybrid: edge rotation + multi-vertex translation)
│   └── Seam alignment functions (align_split_seams_*)
├── OPERATORS
│   ├── HOTSPOTUV_OT_UnwrapFaces (Two-Pass + seam alignment)
│   ├── HOTSPOTUV_OT_ManualDock
│   ├── HOTSPOTUV_OT_SelectSimilar
│   └── HOTSPOTUV_OT_StackSimilar
└── PANEL (HOTSPOTUV_PT_Panel)
```

---

### Recommended GitHub Project Structure

```
cftuv/
├── README.md                    # Overview, installation, usage
├── SPEC.md                      # This document
├── __init__.py                  # bl_info, register/unregister, imports
├── config.py                    # Globals, settings PropertyGroup
├── analysis/
│   ├── __init__.py
│   ├── geometry.py              # IslandInfo, find_island_up, calc_surface_basis, etc.
│   ├── patches.py               # find_seam_patches, boundary loops, OUTER/HOLE
│   ├── frame.py                 # Corner detection, segment splitting, frame classification
│   └── relations.py             # [TODO] DOCK/STITCH/IGNORE classification
├── solver/
│   ├── __init__.py
│   ├── two_pass.py              # Current Two-Pass unwrap logic
│   ├── orient.py                # orient_scale_and_position_island
│   ├── align.py                 # align_connected_islands (hybrid)
│   ├── docking.py               # Manual dock, chain BFS, compute_best_fit_transform
│   ├── seam_align.py            # Seam alignment functions
│   └── frame_solve.py           # [TODO] Frame straighten + pin + conformal
├── operators/
│   ├── __init__.py
│   ├── unwrap_faces.py          # HOTSPOTUV_OT_UnwrapFaces
│   ├── manual_dock.py           # HOTSPOTUV_OT_ManualDock
│   ├── select_similar.py        # HOTSPOTUV_OT_SelectSimilar
│   ├── stack_similar.py         # HOTSPOTUV_OT_StackSimilar
│   └── debug.py                 # Debug analysis + visualization operators
├── ui/
│   ├── __init__.py
│   └── panel.py                 # HOTSPOTUV_PT_Panel
└── tests/                       # [TODO] Test meshes + expected results
    └── README.md
```

---

### Next Steps (Priority Order)

1. **Validate frame classification on real meshes** - use the Grease Pencil overlay to tune corner detection, OUTER/HOLE classification, and frame-role heuristics
2. **Extract straight frame chains** - operate on OUTER boundary segments between corners; HOLE loops remain free
3. **Implement preliminary-unwrap -> straighten/pin -> conformal** - reuse the current unwrap as initialization, then straighten frame chains, pin them, and run the final relaxation pass
4. **Implement DOCK/STITCH/IGNORE** - replace same-type-only alignment with explicit relation handling, including BEVEL and junction rules
5. **Testing** - create regression meshes (cube+bevel, building with windows, L-shape, long wall strips) and expected debug/UV outcomes
