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
    """Build a stable 1-face basis from the face normal and projected WORLD_UP."""
    if face.normal.length_squared > 1e-12:
        plane_normal = face.normal.normalized()
    elif avg_normal.length_squared > 1e-12:
        plane_normal = avg_normal.normalized()
    else:
        plane_normal = Vector((0.0, 0.0, 1.0))

    local_up = WORLD_UP - plane_normal * WORLD_UP.dot(plane_normal)
    if local_up.length_squared > 1e-8:
        seed_b = local_up.normalized()
        seed_t = seed_b.cross(plane_normal)
        if seed_t.length_squared > 1e-8:
            return seed_t.normalized(), seed_b

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


def _get_single_face_axes(face_normal):
    if face_normal.length_squared < 1e-12:
        return None, None

    plane_normal = face_normal.normalized()
    local_v = WORLD_UP - plane_normal * WORLD_UP.dot(plane_normal)
    if local_v.length_squared < 1e-8:
        return None, None
    local_v.normalize()

    local_h = local_v.cross(plane_normal)
    if local_h.length_squared < 1e-8:
        return None, None
    local_h.normalize()
    return local_h, local_v


def _single_face_edge_dominance(segment_verts, local_h, local_v):
    if len(segment_verts) < 2:
        return None

    edge_vec = segment_verts[-1].co - segment_verts[0].co
    if edge_vec.length < 1e-8:
        return None

    du = abs(edge_vec.dot(local_h))
    dv = abs(edge_vec.dot(local_v))
    total = du + dv
    if total < 1e-8:
        return None

    return (du - dv) / total


def _classify_single_face_loop_segments(segments, face_normal, dominance_threshold=0.12):
    """Classify a 4-edge single-face loop as 2 H_FRAME and 2 V_FRAME when clear."""
    if len(segments) != 4 or any(len(seg) < 2 for seg in segments):
        return None

    local_h, local_v = _get_single_face_axes(face_normal)
    if local_h is None:
        return None

    dominance = []
    for seg in segments:
        dom = _single_face_edge_dominance(seg, local_h, local_v)
        if dom is None:
            return None
        dominance.append(dom)

    order = sorted(range(len(segments)), key=lambda idx: dominance[idx], reverse=True)
    if dominance[order[1]] < dominance_threshold:
        return None
    if dominance[order[2]] > -dominance_threshold:
        return None

    roles = ['FREE'] * len(segments)
    for idx in order[:2]:
        roles[idx] = 'H_FRAME'
    for idx in order[2:]:
        roles[idx] = 'V_FRAME'
    return roles


def _classify_single_face_segment_role(segment_verts, face_normal, dominance_threshold=0.12):
    """Classify a 1-face patch edge; near-diagonals stay FREE."""
    local_h, local_v = _get_single_face_axes(face_normal)
    if local_h is None:
        return None

    dominance = _single_face_edge_dominance(segment_verts, local_h, local_v)
    if dominance is None:
        return 'FREE'
    if dominance >= dominance_threshold:
        return 'H_FRAME'
    if dominance <= -dominance_threshold:
        return 'V_FRAME'
    return 'FREE'


def classify_segment_frame_role(segment_verts, seed_t, seed_b, threshold=0.08):
    """Classify a boundary segment as H_FRAME, V_FRAME, or FREE."""
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
            single_face_roles = None
            if len(patch_faces) == 1:
                single_face_roles = _classify_single_face_loop_segments(segments, patch_faces[0].normal)

            for seg_idx, seg_verts in enumerate(segments):
                role = None
                if single_face_roles is not None:
                    role = single_face_roles[seg_idx]
                elif len(patch_faces) == 1:
                    role = _classify_single_face_segment_role(seg_verts, patch_faces[0].normal)
                if role is None:
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
