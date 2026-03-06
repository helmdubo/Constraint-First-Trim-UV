"""Frame analysis — corner detection, segment splitting, H_FRAME/V_FRAME/FREE classification.

Identifies structural edge chains on patch boundaries that are candidates
for pinning before the conformal solve.
"""

import math
from mathutils import Vector

from ..config import WORLD_UP
from .geometry import IslandInfo, analyze_island_properties, find_island_up, calc_surface_basis
from .patches import find_seam_patches, find_patch_boundary_edges, build_ordered_boundary_loops, classify_boundary_loops_3d


def _build_single_face_basis(face, avg_normal):
    """Stabilize basis for 1-face wall/reveal patches using face edges + WORLD_UP."""
    plane_normal = face.normal.normalized() if face.normal.length_squared > 1e-12 else avg_normal.normalized()

    vertical_edge = None
    vertical_score = -1.0
    longest_edge = None
    longest_len = -1.0

    for edge in face.edges:
        edge_vec = edge.verts[1].co - edge.verts[0].co
        edge_len = edge_vec.length
        if edge_len < 1e-8:
            continue

        edge_dir = edge_vec / edge_len
        if edge_dir.dot(WORLD_UP) < 0.0:
            edge_dir = -edge_dir

        vertical_alignment = abs(edge_dir.dot(WORLD_UP))
        vertical_candidate_score = edge_len * (vertical_alignment ** 2)
        if vertical_candidate_score > vertical_score:
            vertical_score = vertical_candidate_score
            vertical_edge = edge_dir

        if edge_len > longest_len:
            longest_len = edge_len
            longest_edge = edge_dir

    if vertical_edge is not None and abs(vertical_edge.dot(WORLD_UP)) > 0.25:
        seed_b = vertical_edge
        seed_t = seed_b.cross(plane_normal)
        if seed_t.length_squared > 1e-8:
            return seed_t.normalized(), seed_b.normalized()

    if longest_edge is not None:
        seed_t = longest_edge - plane_normal * longest_edge.dot(plane_normal)
        if seed_t.length_squared > 1e-8:
            seed_t.normalize()
            seed_b = plane_normal.cross(seed_t)
            if seed_b.length_squared > 1e-8:
                if seed_b.dot(WORLD_UP) < 0.0:
                    seed_b = -seed_b
                    seed_t = -seed_t
                return seed_t, seed_b.normalized()

    return calc_surface_basis(plane_normal, WORLD_UP)


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

    if len(patch_faces) == 1:
        seed_t, seed_b = _build_single_face_basis(seed_face, temp_island.avg_normal)
    else:
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

    if len(segment_verts) == 2:
        edge_vec = segment_verts[1].co - segment_verts[0].co
        if edge_vec.length < 1e-8:
            return 'FREE'

        edge_dir = edge_vec.normalized()
        align_u = abs(edge_dir.dot(seed_t))
        align_v = abs(edge_dir.dot(seed_b))

        if max(align_u, align_v) < 0.6:
            return 'FREE'
        if abs(align_u - align_v) < 0.1:
            return 'FREE'
        if align_u > align_v:
            return 'H_FRAME'
        return 'V_FRAME'

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
