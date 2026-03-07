# Constraint-First Trim UV (CFTUV)
## Spec-Driven Design Document

### Overview

**System name:** Constraint-First Trim UV (CFTUV)  
**Core principle:** Constraints before solve, not post-hoc repair.  
**Target user:** 3D Environment/Level Artist in video games development.  
**Target workflow:** Architectural trim sheet UV mapping (tile, trim, decal textures/atlas).  
**Platform:** Blender addon (3.0+), single Python file currently, planned modular structure.  
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
- Inner vs outer boundary loop detection for patches with holes (windows, doors)
  - OUTER boundary segments → frame candidates (pin + straighten)
  - HOLE boundary segments → always free (never pin)
- Curvature analysis (flat / cylindrical / complex)
- Automatic "straight chain" detection inside patches (not just on boundary)

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
- **Frame straighten + pin before solve** — straighten H_FRAME/V_FRAME segments in UV, pin, then conformal. This is the core CFTUV idea.
- **Seam alignment as constraint, not post-hoc** — align_seam before final unwrap, not after
- **Unified constraint solve order:**
  1. Analyze patches (Layer 1)
  2. Classify relations (Layer 2)  
  3. Extract frame segments, straighten in UV
  4. Pin frame + seam constraints
  5. Single conformal solve
  6. Orient whole islands (rigid transform)
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
| v2.5.5-6 | Patch analysis + frame classification + debug visualization | Corner formula inverted → all FREE. Fixed in v2.5.6 |
| v2.5.7 | Grease Pencil debug | GP API broken in Blender 4.x |
| v2.5.8 | Mesh wireframe debug + fixed corner threshold to 30° | Debug works. Frame classification not yet verified on mesh |

**Current status (v2.5.8):** Analysis infrastructure built. Debug visualization works (mesh wireframes). Frame classification formula fixed but returns all FREE on test mesh — needs verification. UV solve pipeline unchanged from v2.4.11.

---

### Working Conventions

- **Versioning:** Each code output increments version by +1 (e.g., 2.5.7 → 2.5.8).
- **Code edits:** Use `str_replace` for surgical changes, NOT full file rewrites. File is ~2300 lines; rewriting burns ~$8 per iteration.
- **Blender version:** Target 4.1–4.3.2. Debug visualization uses Grease Pencil API.
- **Platform:** Blender addon (single .py file, planned modular).
- **Testing:** Manual testing by Alexander on architectural buildings (houses with bevels, windows, multi-story walls).

---

### Reference Scripts (not in main codebase, but informed design)

1. **trimsheet_unwrap_v3_1_2.py** — Separate addon for trim sheet unwrap. Key technique: Straighten guide loop → Pin → Conformal → Cross-axis straighten. Functions `_step2_straighten_guide` (cumulative 3D distance → UV interpolation along axis) and `_step3_straighten_cross_axis` (union-find clustering by angle threshold) informed the frame straighten design.

2. **align_seam.py** (from Mio3UV addon) — Matches UV vertices of same 3D vertex split by seam. Averages UV coordinate along determined axis. Informed the seam alignment approach. Key insight: seam alignment must respect UV topology (cluster loops by UV position, pick twin clusters).

3. **debug_uv_boundary_loops.py** — Analysis script with three modes (UV/SEAM/MESH). Flood fill patches, extract boundary loops, classify OUTER/HOLE by nesting depth. SEAM mode works correctly; MESH mode fails on non-planar patches (projection degrades). Informed `find_seam_patches`, `classify_boundary_loops_3d`.

---

### Current Blocker: Frame Classification Returns All FREE

**Symptom:** `analyze_all_patches` returns `H-frame: 0, V-frame: 0, Free: 83` on a building with clearly straight horizontal and vertical edges.

**Root cause investigation:**
- v2.5.4: Analyzed whole loops (not segments) → rectangular loop has both U and V extent → always FREE. **Fixed by corner splitting.**
- v2.5.5: Corner detection formula inverted (`cos(180-threshold)` instead of `cos(threshold)`) → only caught >120° turns, missed 90° corners and bevels. **Fixed in v2.5.6.**
- v2.5.6–v2.5.7: Formula fixed, threshold lowered to 30°. **Not yet verified on real mesh.** This is the immediate next task.

**How frame classification should work:**
1. Build local basis per patch: seed_t (U/horizontal), seed_b (V/vertical)
2. Find boundary loops → classify OUTER/HOLE
3. Split OUTER loops at corners (angle > 30° from straight)
4. For each segment: project vertices onto seed_t and seed_b
5. If V-extent / total-extent < 0.08 → H_FRAME (horizontal line, straighten along V)
6. If U-extent / total-extent < 0.08 → V_FRAME (vertical line, straighten along U)
7. Otherwise → FREE

**Test case:** House = elongated cube without caps, single bevel on 4 corners, 5 stories (4 horizontal loops). 4 SEAM patches (one per wall+bevel strip). Each patch should have: 2 H_FRAME segments (top/bottom edges), multiple V_FRAME segments (vertical seam edges), FREE segments (bevel transitions at corners).

---

### Two-Pass Unwrap Pipeline (Current, Working)

The core UV pipeline that produces "almost correct" results:

```
Step 1: Temporary seams on sharp edges
Step 2: get_expanded_islands → {full, core} per island
Step 3: Conformal unwrap CORE faces only
Step 4: orient_scale_and_position_island on core
        (seed face → ideal UV from world-space → rotate+scale+translate)
Step 5: Pin all core UV vertices
Step 6: Conformal unwrap FULL island (core pinned, remainder fills in)
Step 7: Unpin, restore seams
Step 8: align_connected_islands (hybrid rotation+translation)
Step 9: Seam alignment post-hoc (v2.4.11+)
Step 10: normalize_uvs_to_origin
```

**Problem:** Steps 3-4 operate on the entire core as one piece. For a building wrapped around corners, core is a long strip through bevels. Conformal unwrap of this strip accumulates yaw/drift. orient_scale_and_position uses one seed face — correct near seed, drifted far from seed.

**CFTUV goal:** Insert frame constraints (straightened boundary segments) between steps 6 and 7, with a corrective re-unwrap, OR restructure the pipeline to establish constraints before the first unwrap.

---

### Key Geometric Context

**Primary test case:** Rectangular house, elongated cube, no caps (no top/bottom). Single bevel on 4 vertical corners. 5 stories = 4 horizontal edge loops dividing walls. One vertical seam from bottom to top. This creates one continuous UV strip that wraps around the house.

**The yaw/drift problem:** When unwrapping this strip with conformal, each 90° bevel turn introduces ~0.1-0.5° of angular error. Over 4 turns (full wrap), this accumulates to ~0.5-2° total yaw at the seam. On a 5-story building, this means the top of the seam may be offset by several texels from the bottom — visible as texture discontinuity.

**Why bevels make it worse:** Moving bevel edges via edge slide (making them asymmetric) changes the angular contribution of each bevel, making the error less predictable and harder to correct globally.

---

### File Structure (v2.5.8)

```
Hotspot_UV_v2_5_8.py
├── CONFIGURATION GLOBALS
├── UI SETTINGS (HOTSPOTUV_Settings)
├── GEOMETRY ANALYSIS
│   ├── IslandInfo, get_expanded_islands
│   ├── find_island_up (dual-strategy)
│   ├── analyze_island_properties (WALL/FLOOR)
│   ├── build_edge_based_links (shared_verts + longest_edge_verts)
│   └── calc_surface_basis
├── PATCH & FRAME ANALYSIS (CFTUV Layer 1)
│   ├── find_seam_patches (flood fill by seam/sharp)
│   ├── find_patch_boundary_edges (topological: 1-face edges)
│   ├── build_ordered_boundary_loops (ordered closed vertex chains)
│   ├── classify_boundary_loops_3d (OUTER/HOLE via 2D nesting)
│   ├── build_patch_basis (centroid, normal, seed_t, seed_b, type)
│   ├── find_loop_corners (angle threshold 30°)
│   ├── split_loop_into_segments (split at corners)
│   ├── classify_segment_frame_role (H_FRAME/V_FRAME/FREE)
│   └── analyze_all_patches (orchestrator)
├── DEBUG VISUALIZATION (mesh wireframe objects in CFTUV_Debug collection)
│   ├── create_debug_visualization (color-coded wireframes)
│   ├── HOTSPOTUV_OT_DebugAnalysis (Analyze button)
│   └── HOTSPOTUV_OT_DebugClear (Clear button)
├── HYBRID ALIGNMENT LOGIC
│   └── orient_scale_and_position_island
├── VALIDATION HELPERS
├── DOCKING & WELDING
│   ├── compute_best_fit_transform (rigid: rotation + translation)
│   ├── dock_island_to_anchor (transform + optional fit + pin)
│   ├── build_island_graph, dock_all_chains, dock_chain_bfs_layered
│   ├── align_connected_islands (root-anchored, weighted frontier rotation)
│   ├── align_split_seams_in_island (internal seam UV averaging)
│   └── align_split_seams_between_islands (inter-island seam UV averaging)
├── OPERATORS
│   ├── HOTSPOTUV_OT_UnwrapFaces (Two-Pass + seam alignment)
│   ├── HOTSPOTUV_OT_ManualDock (edge-based with fit_vertices + unwrap_interior)
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

1. **Verify frame classification** — run debug on test mesh, check if corners fire. Add logging of corner count + segment lengths. If all FREE → debug `classify_segment_frame_role` inputs (print extent_u, extent_v, ratio per segment). Threshold may need tuning.
2. **Implement frame straighten** — for H_FRAME: compute ideal V from `avg(vert.co.dot(seed_b)) * FINAL_UV_SCALE`, UV U by cumulative 3D distance. For V_FRAME: same on perpendicular axis. Needs preliminary UV (Two-Pass) to establish UV space first.
3. **Implement frame pin + conformal solve** — pin straightened frame verts → conformal unwrap → unpin. Replaces post-hoc seam alignment.
4. **Implement DOCK/STITCH/IGNORE** — replace type!=type skip in `align_connected_islands` with relation-aware handling. STITCH = one-axis align only.
5. **Split into modules** — move from single file to GitHub project structure.
6. **Testing** — create test meshes (cube+bevel, building with windows, L-shape, cylinder).
