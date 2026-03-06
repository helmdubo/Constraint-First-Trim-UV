"""Frame analysis — corner detection, segment splitting, H_FRAME/V_FRAME/FREE classification.

Identifies structural edge chains on patch boundaries that are candidates
for pinning before the conformal solve.
"""

import math
from mathutils import Vector

from .geometry import IslandInfo, analyze_island_properties, find_island_up, calc_surface_basis
from .patches import find_seam_patches, find_patch_boundary_edges, build_ordered_boundary_loops, classify_boundary_loops_3d


def build_patch_basis(patch_faces):
    """
    Строит полный локальный базис для патча.
    Возвращает: (centroid, normal, seed_t, seed_b, island_type)
    """
    temp_island = IslandInfo(patch_faces, 0)
    analyze_island_properties(temp_island)

    island_up = find_island_up(temp_island)

    sorted_faces = sorted(
        patch_faces,
        key=lambda f: f.calc_area() * (max(0, f.normal.dot(temp_island.avg_normal)) ** 4),
        reverse=True
    )
    seed_face = sorted_faces[0] if sorted_faces else patch_faces[0]

    seed_t, seed_b = calc_surface_basis(seed_face.normal, island_up)

    center = Vector((0, 0, 0))
    cnt = 0
    for f in patch_faces:
        for v in f.verts:
            center += v.co
            cnt += 1
    centroid = center / max(cnt, 1)

    return centroid, temp_island.avg_normal, seed_t, seed_b, temp_island.type


def find_loop_corners(loop_verts, angle_threshold_deg=30.0):
    """
    Находит угловые вершины boundary loop — точки, где цепочка
    резко поворачивает.

    angle_threshold_deg: минимальный угол отклонения ОТ ПРЯМОЙ для corner.
      30° → ловит бевели (45° поворот) и прямые углы (90°).

    Возвращает: list of corner indices (в пределах loop_verts)
    """
    n = len(loop_verts)
    if n < 3:
        return []

    cos_threshold = math.cos(math.radians(angle_threshold_deg))
    corners = []

    for i in range(n):
        v_prev = loop_verts[(i - 1) % n].co
        v_curr = loop_verts[i].co
        v_next = loop_verts[(i + 1) % n].co

        d1 = (v_curr - v_prev)
        d2 = (v_next - v_curr)

        if d1.length < 1e-8 or d2.length < 1e-8:
            corners.append(i)
            continue

        cos_angle = d1.normalized().dot(d2.normalized())
        if cos_angle < cos_threshold:
            corners.append(i)

    return corners


def split_loop_into_segments(loop_verts, corners):
    """
    Разбивает замкнутый loop на сегменты по corner вершинам.
    Каждый сегмент включает corner на обоих концах.

    Возвращает: [[BMVert, ...], ...]
    """
    n = len(loop_verts)

    if not corners:
        return [loop_verts]

    segments = []
    num_corners = len(corners)

    for ci in range(num_corners):
        start_idx = corners[ci]
        end_idx = corners[(ci + 1) % num_corners]

        seg = []
        idx = start_idx
        while True:
            seg.append(loop_verts[idx % n])
            if idx % n == end_idx % n:
                break
            idx += 1
            if len(seg) > n + 1:
                break

        if len(seg) >= 2:
            segments.append(seg)

    return segments


def classify_segment_frame_role(segment_verts, seed_t, seed_b, threshold=0.08):
    """
    Определяет роль СЕГМЕНТА boundary loop для frame.

    H_FRAME = горизонтальная линия в 3D (low V variance)
    V_FRAME = вертикальная линия в 3D (low U variance)
    FREE = диагональная или слишком короткая
    """
    if len(segment_verts) < 2:
        return 'FREE'

    us = [v.co.dot(seed_t) for v in segment_verts]
    vs = [v.co.dot(seed_b) for v in segment_verts]

    extent_u = max(us) - min(us)
    extent_v = max(vs) - min(vs)

    total_extent = max(extent_u, extent_v)
    if total_extent < 1e-6:
        return 'FREE'

    ratio_v = extent_v / total_extent
    ratio_u = extent_u / total_extent

    if ratio_v < threshold:
        return 'H_FRAME'
    if ratio_u < threshold:
        return 'V_FRAME'

    return 'FREE'


def analyze_all_patches(bm, base_faces):
    """
    Полный анализ: патчи, boundaries, segments, frame classification.
    """
    patches = find_seam_patches(bm, base_faces)

    results = []
    for patch_faces in patches:
        be = find_patch_boundary_edges(patch_faces)
        raw_loops = build_ordered_boundary_loops(be)
        classified_loops = classify_boundary_loops_3d(raw_loops, patch_faces)

        centroid, normal, seed_t, seed_b, isl_type = build_patch_basis(patch_faces)

        all_segments = []
        for lp in classified_loops:
            corners = find_loop_corners(lp['verts'])
            segments = split_loop_into_segments(lp['verts'], corners)

            lp_segments = []
            for seg_verts in segments:
                role = classify_segment_frame_role(seg_verts, seed_t, seed_b)
                lp_segments.append({
                    'vert_cos': [v.co.copy() for v in seg_verts],
                    'frame_role': role,
                    'loop_kind': lp['kind']
                })

            lp['segments'] = lp_segments
            all_segments.extend(lp_segments)

        results.append({
            'faces': patch_faces,
            'centroid': centroid,
            'normal': normal,
            'seed_t': seed_t,
            'seed_b': seed_b,
            'type': isl_type,
            'loops': classified_loops,
            'all_segments': all_segments,
        })

    return results
