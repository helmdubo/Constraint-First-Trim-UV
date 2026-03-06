"""Island orientation — orient_scale_and_position_island, normalize_uvs_to_origin.

World-space projection via seed face for deterministic, world-aligned UV.
"""

import math
from mathutils import Vector

import cftuv.config as config
from cftuv.analysis.geometry import find_island_up, calc_surface_basis


def orient_scale_and_position_island(uv_layer, island):
    sorted_faces = sorted(
        island.faces,
        key=lambda f: f.calc_area() * (max(0, f.normal.dot(island.avg_normal)) ** 4),
        reverse=True
    )
    if not sorted_faces: return
    seed_face = sorted_faces[0]

    island_up = find_island_up(island)
    seed_t, seed_b = calc_surface_basis(seed_face.normal, island_up)

    ideal_uvs = {}
    for l in seed_face.loops:
        u = l.vert.co.dot(seed_t) * config.FINAL_UV_SCALE
        v = l.vert.co.dot(seed_b) * config.FINAL_UV_SCALE
        ideal_uvs[l.vert.index] = Vector((u, v))

    current_uvs = {}
    for l in seed_face.loops:
        current_uvs[l.vert.index] = l[uv_layer].uv.copy()

    longest_edge = max(seed_face.edges, key=lambda e: e.calc_length())
    v1, v2 = longest_edge.verts[0].index, longest_edge.verts[1].index

    tgt_u1, tgt_u2 = ideal_uvs[v1], ideal_uvs[v2]
    src_u1, src_u2 = current_uvs[v1], current_uvs[v2]

    tgt_vec = tgt_u2 - tgt_u1
    src_vec = src_u2 - src_u1

    if src_vec.length_squared < 1e-6: return

    delta_angle = math.atan2(tgt_vec.y, tgt_vec.x) - math.atan2(src_vec.y, src_vec.x)
    cos_a, sin_a = math.cos(delta_angle), math.sin(delta_angle)

    scale = tgt_vec.length / src_vec.length if src_vec.length > 1e-6 else 1.0

    for f in island.faces:
        for l in f.loops:
            p = l[uv_layer].uv - src_u1
            rx = (p.x * cos_a - p.y * sin_a) * scale
            ry = (p.x * sin_a + p.y * cos_a) * scale
            l[uv_layer].uv = Vector((rx, ry)) + tgt_u1


def normalize_uvs_to_origin(bm, uv_layer):
    limit = config.UV_RANGE_LIMIT
    min_u, max_u, min_v, max_v = 1e9, -1e9, 1e9, -1e9
    has_uvs = False
    for f in bm.faces:
        if f.select:
            for l in f.loops:
                uv = l[uv_layer].uv
                min_u, max_u = min(min_u, uv.x), max(max_u, uv.x)
                min_v, max_v = min(min_v, uv.y), max(max_v, uv.y)
                has_uvs = True
    if not has_uvs: return

    center_u, center_v = (min_u + max_u) / 2.0, (min_v + max_v) / 2.0
    shift_vec = Vector((0.0, 0.0))
    if abs(center_u) > limit: shift_vec.x = -round(center_u)
    if abs(center_v) > limit: shift_vec.y = -round(center_v)

    if shift_vec.length_squared > 0:
        for f in bm.faces:
            if f.select:
                for l in f.loops: l[uv_layer].uv += shift_vec
