"""Island alignment — align_connected_islands (root-anchored).

Edge direction for rotation, multi-vertex centroid for translation.
Only the final v3 (root-anchored) implementation is included.
"""

import math
from mathutils import Vector


def _collect_shared_uv_correspondences(anchor_island, target_island, shared_vert_ids, uv_layer):
    anchor_uvs = {}
    for f in anchor_island.faces:
        for l in f.loops:
            if l.vert.index in shared_vert_ids and l.vert.index not in anchor_uvs:
                anchor_uvs[l.vert.index] = l[uv_layer].uv.copy()

    target_uvs = {}
    for f in target_island.faces:
        for l in f.loops:
            if l.vert.index in shared_vert_ids and l.vert.index not in target_uvs:
                target_uvs[l.vert.index] = l[uv_layer].uv.copy()

    common_verts = sorted(set(anchor_uvs.keys()) & set(target_uvs.keys()))
    return [anchor_uvs[v_id] for v_id in common_verts], [target_uvs[v_id] for v_id in common_verts]


def _is_valid_island_contact(link, isl_A, isl_B, cluster_elements, islands_list, root_A, root_B):
    if isl_A.type != isl_B.type:
        return False

    shared_len = link['shared_length']
    max_perim = max(isl_A.perimeter, isl_B.perimeter)
    min_perim = min(isl_A.perimeter, isl_B.perimeter)

    if max_perim > 1e-5 and (shared_len / max_perim) >= 0.02:
        return True

    if min_perim > 1e-5 and (shared_len / min_perim) >= 0.30:
        area_root_A = sum(islands_list[i].area for i in cluster_elements[root_A])
        area_root_B = sum(islands_list[i].area for i in cluster_elements[root_B])
        min_cluster_area = min(area_root_A, area_root_B)
        min_isl_area = min(isl_A.area, isl_B.area)
        return min_cluster_area <= (min_isl_area * 5.0 + 1e-4)

    return False


def _collect_cluster_frontier_links(root_A, root_B, cluster_elements, links):
    cluster_A = set(cluster_elements[root_A])
    cluster_B = set(cluster_elements[root_B])
    frontier_links = []

    for frontier_link in links:
        idx_A = frontier_link['isl_a']
        idx_B = frontier_link['isl_b']

        if idx_A in cluster_A and idx_B in cluster_B:
            frontier_links.append((idx_A, idx_B, frontier_link))
        elif idx_B in cluster_A and idx_A in cluster_B:
            frontier_links.append((idx_B, idx_A, frontier_link))

    return frontier_links


def _collect_cluster_frontier_correspondences(frontier_links, islands_list, uv_layer):
    anchor_uvs_list = []
    target_uvs_list = []

    for anchor_idx, target_idx, frontier_link in frontier_links:
        link_anchor_uvs, link_target_uvs = _collect_shared_uv_correspondences(
            islands_list[anchor_idx],
            islands_list[target_idx],
            set(frontier_link['shared_verts']),
            uv_layer
        )
        if not link_anchor_uvs:
            continue

        anchor_uvs_list.extend(link_anchor_uvs)
        target_uvs_list.extend(link_target_uvs)

    return anchor_uvs_list, target_uvs_list


def _compute_link_rotation_delta(anchor_island, target_island, frontier_link, uv_layer):
    v1_id, v2_id = frontier_link['longest_edge_verts']
    tgt_v1 = tgt_v2 = src_v1 = src_v2 = None

    for f in anchor_island.faces:
        for l in f.loops:
            if l.vert.index == v1_id:
                tgt_v1 = l[uv_layer].uv.copy()
            elif l.vert.index == v2_id:
                tgt_v2 = l[uv_layer].uv.copy()
        if tgt_v1 is not None and tgt_v2 is not None:
            break

    for f in target_island.faces:
        for l in f.loops:
            if l.vert.index == v1_id:
                src_v1 = l[uv_layer].uv.copy()
            elif l.vert.index == v2_id:
                src_v2 = l[uv_layer].uv.copy()
        if src_v1 is not None and src_v2 is not None:
            break

    if tgt_v1 is None or tgt_v2 is None or src_v1 is None or src_v2 is None:
        return None

    tgt_vec = tgt_v2 - tgt_v1
    src_vec = src_v2 - src_v1
    if tgt_vec.length_squared < 1e-6 or src_vec.length_squared < 1e-6:
        return None

    return math.atan2(tgt_vec.y, tgt_vec.x) - math.atan2(src_vec.y, src_vec.x)


def _compute_weighted_frontier_rotation(frontier_links, islands_list, uv_layer):
    sin_sum = 0.0
    cos_sum = 0.0
    total_weight = 0.0

    for anchor_idx, target_idx, frontier_link in frontier_links:
        delta = _compute_link_rotation_delta(
            islands_list[anchor_idx],
            islands_list[target_idx],
            frontier_link,
            uv_layer
        )
        if delta is None:
            continue

        weight = max(frontier_link['shared_length'], 1e-6)
        sin_sum += math.sin(delta) * weight
        cos_sum += math.cos(delta) * weight
        total_weight += weight

    if total_weight <= 0.0:
        return None

    return math.atan2(sin_sum, cos_sum)


def _find_island_link_components(islands_list, valid_links):
    adjacency = {isl.index: set() for isl in islands_list}
    for link in valid_links:
        adjacency[link['isl_a']].add(link['isl_b'])
        adjacency[link['isl_b']].add(link['isl_a'])

    components = []
    visited = set()
    for isl in islands_list:
        if isl.index in visited:
            continue

        stack = [isl.index]
        component = set()
        while stack:
            current = stack.pop()
            if current in visited:
                continue

            visited.add(current)
            component.add(current)
            stack.extend(adjacency[current] - visited)

        components.append(component)

    return components


def _collect_root_frontier_links(target_id, placed_ids, valid_links):
    frontier_links = []
    total_weight = 0.0

    for link in valid_links:
        idx_A = link['isl_a']
        idx_B = link['isl_b']

        if idx_A in placed_ids and idx_B == target_id:
            frontier_links.append((idx_A, idx_B, link))
            total_weight += link['shared_length']
        elif idx_B in placed_ids and idx_A == target_id:
            frontier_links.append((idx_B, idx_A, link))
            total_weight += link['shared_length']

    return frontier_links, total_weight


def _compute_frontier_transform(frontier_links, islands_list, uv_layer):
    if not frontier_links:
        return None

    delta_angle = _compute_weighted_frontier_rotation(frontier_links, islands_list, uv_layer)
    if delta_angle is None:
        strongest_link = max(frontier_links, key=lambda item: item[2]['shared_length'])
        delta_angle = _compute_link_rotation_delta(
            islands_list[strongest_link[0]],
            islands_list[strongest_link[1]],
            strongest_link[2],
            uv_layer
        )
    if delta_angle is None:
        return None

    anchor_uvs_list, target_uvs_list = _collect_cluster_frontier_correspondences(
        frontier_links, islands_list, uv_layer
    )
    if not anchor_uvs_list or len(anchor_uvs_list) != len(target_uvs_list):
        strongest_link = max(frontier_links, key=lambda item: item[2]['shared_length'])
        anchor_uvs_list, target_uvs_list = _collect_shared_uv_correspondences(
            islands_list[strongest_link[0]],
            islands_list[strongest_link[1]],
            set(strongest_link[2]['shared_verts']),
            uv_layer
        )
    if not anchor_uvs_list or len(anchor_uvs_list) != len(target_uvs_list):
        return None

    count = len(anchor_uvs_list)
    anchor_centroid = sum(anchor_uvs_list, Vector((0.0, 0.0))) / count
    target_centroid = sum(target_uvs_list, Vector((0.0, 0.0))) / count
    return delta_angle, anchor_centroid, target_centroid


def _apply_root_anchored_transform(island, uv_layer, delta_angle, anchor_centroid, target_centroid):
    cos_a = math.cos(delta_angle)
    sin_a = math.sin(delta_angle)

    for f in island.faces:
        for l in f.loops:
            p = l[uv_layer].uv - target_centroid
            l[uv_layer].uv = Vector((
                p.x * cos_a - p.y * sin_a,
                p.x * sin_a + p.y * cos_a
            )) + anchor_centroid


def align_connected_islands(islands_list, links, uv_layer):
    """
    Root-anchored final docking.
    Each connected component chooses a stable root island and then places the
    remaining islands once, against the already placed set, instead of repeatedly
    merging clusters. This reduces cumulative yaw/drift and avoids detached shells.
    """
    singleton_clusters = {isl.index: [isl.index] for isl in islands_list}
    valid_links = []
    for link in sorted(links, key=lambda item: item['shared_length'], reverse=True):
        isl_A = islands_list[link['isl_a']]
        isl_B = islands_list[link['isl_b']]
        if _is_valid_island_contact(
            link, isl_A, isl_B, singleton_clusters, islands_list, isl_A.index, isl_B.index
        ):
            valid_links.append(link)

    for component in _find_island_link_components(islands_list, valid_links):
        if len(component) < 2:
            continue

        root_id = max(component, key=lambda idx: islands_list[idx].area)
        placed_ids = {root_id}
        unplaced_ids = set(component) - placed_ids

        skipped_ids = set()
        while unplaced_ids:
            best_target_id = None
            best_frontier_links = []
            best_weight = -1.0

            for target_id in unplaced_ids:
                if target_id in skipped_ids:
                    continue
                frontier_links, total_weight = _collect_root_frontier_links(target_id, placed_ids, valid_links)
                if total_weight > best_weight and frontier_links:
                    best_target_id = target_id
                    best_frontier_links = frontier_links
                    best_weight = total_weight

            if best_target_id is None:
                break

            transform = _compute_frontier_transform(best_frontier_links, islands_list, uv_layer)
            if transform is None:
                skipped_ids.add(best_target_id)
                continue

            _apply_root_anchored_transform(
                islands_list[best_target_id], uv_layer, transform[0], transform[1], transform[2]
            )
            placed_ids.add(best_target_id)
            unplaced_ids.remove(best_target_id)
            skipped_ids.clear()
