"""Seam alignment — align_split_seams_in_island, align_split_seams_between_islands."""

from mathutils import Vector


def _cluster_loops_by_uv(loops, uv_layer, threshold=1e-5):
    clusters = []
    for loop in loops:
        uv = loop[uv_layer].uv.copy()
        placed = False
        for cluster in clusters:
            if (cluster['uv'] - uv).length <= threshold:
                cluster['loops'].append(loop)
                cluster['uv'] = sum((item[uv_layer].uv for item in cluster['loops']), Vector((0.0, 0.0))) / len(cluster['loops'])
                placed = True
                break
        if not placed:
            clusters.append({'uv': uv, 'loops': [loop]})
    return clusters


def _collect_internal_seam_components(island):
    island_faces = set(island.faces)
    seam_edges = set()

    for face in island.faces:
        for edge in face.edges:
            if not edge.seam:
                continue
            if sum(1 for linked_face in edge.link_faces if linked_face in island_faces) == 2:
                seam_edges.add(edge)

    components = []
    visited = set()
    for edge in seam_edges:
        if edge in visited:
            continue

        stack = [edge]
        component_verts = set()
        while stack:
            current = stack.pop()
            if current in visited:
                continue

            visited.add(current)
            component_verts.update(current.verts)

            for vert in current.verts:
                for linked_edge in vert.link_edges:
                    if linked_edge in seam_edges and linked_edge not in visited:
                        stack.append(linked_edge)

        if component_verts:
            components.append(component_verts)

    return components


def _pick_twin_clusters(clusters):
    best_pair = None
    best_distance = -1.0
    for idx_a in range(len(clusters)):
        for idx_b in range(idx_a + 1, len(clusters)):
            distance = (clusters[idx_b]['uv'] - clusters[idx_a]['uv']).length_squared
            if distance > best_distance:
                best_distance = distance
                best_pair = (clusters[idx_a], clusters[idx_b])
    return best_pair


def _choose_seam_align_axis(seam_pairs):
    if not seam_pairs:
        return None

    avg_du = sum(abs(pair['b']['uv'].x - pair['a']['uv'].x) for pair in seam_pairs) / len(seam_pairs)
    avg_dv = sum(abs(pair['b']['uv'].y - pair['a']['uv'].y) for pair in seam_pairs) / len(seam_pairs)

    if abs(avg_du - avg_dv) > 1e-6:
        return 0 if avg_du < avg_dv else 1

    seam_centers = [(pair['a']['uv'] + pair['b']['uv']) * 0.5 for pair in seam_pairs]
    min_u = min(center.x for center in seam_centers)
    max_u = max(center.x for center in seam_centers)
    min_v = min(center.y for center in seam_centers)
    max_v = max(center.y for center in seam_centers)
    return 1 if (max_v - min_v) > (max_u - min_u) else 0


def _build_split_seam_pairs(island, seam_component_verts, uv_layer, threshold=1e-5):
    island_faces = set(island.faces)
    seam_pairs = []

    for vert in seam_component_verts:
        loops = [loop for loop in vert.link_loops if loop.face in island_faces]
        clusters = _cluster_loops_by_uv(loops, uv_layer, threshold)
        if len(clusters) < 2:
            continue

        twin_pair = _pick_twin_clusters(clusters)
        if twin_pair is None:
            continue

        cluster_a, cluster_b = twin_pair
        if (cluster_b['uv'] - cluster_a['uv']).length <= threshold:
            continue

        seam_pairs.append({'a': cluster_a, 'b': cluster_b})

    return seam_pairs, _choose_seam_align_axis(seam_pairs)


def _align_seam_pairs_on_axis(seam_pairs, axis_index, uv_layer):
    if axis_index is None:
        return 0

    aligned_pairs = 0
    for pair in seam_pairs:
        axis_pos = (pair['a']['uv'][axis_index] + pair['b']['uv'][axis_index]) * 0.5

        for loop in pair['a']['loops']:
            loop[uv_layer].uv[axis_index] = axis_pos

        for loop in pair['b']['loops']:
            loop[uv_layer].uv[axis_index] = axis_pos

        aligned_pairs += 1

    return aligned_pairs


def align_split_seams_in_island(uv_layer, island):
    aligned_pairs = 0
    for seam_component_verts in _collect_internal_seam_components(island):
        seam_pairs, axis_index = _build_split_seam_pairs(island, seam_component_verts, uv_layer)
        aligned_pairs += _align_seam_pairs_on_axis(seam_pairs, axis_index, uv_layer)
    return aligned_pairs


def _pick_primary_uv_cluster(loops, uv_layer):
    clusters = _cluster_loops_by_uv(loops, uv_layer)
    if not clusters:
        return None
    return max(clusters, key=lambda cluster: len(cluster['loops']))


def _build_inter_island_seam_pairs(islands_list, link, uv_layer, threshold=1e-5):
    island_a = islands_list[link['isl_a']]
    island_b = islands_list[link['isl_b']]
    seam_pairs = []

    for vert_id in sorted(set(link['shared_verts'])):
        loops_a = [loop for face in island_a.faces for loop in face.loops if loop.vert.index == vert_id]
        loops_b = [loop for face in island_b.faces for loop in face.loops if loop.vert.index == vert_id]
        if not loops_a or not loops_b:
            continue

        cluster_a = _pick_primary_uv_cluster(loops_a, uv_layer)
        cluster_b = _pick_primary_uv_cluster(loops_b, uv_layer)
        if cluster_a is None or cluster_b is None:
            continue
        if (cluster_b['uv'] - cluster_a['uv']).length <= threshold:
            continue

        seam_pairs.append({'a': cluster_a, 'b': cluster_b})

    return seam_pairs


def align_split_seams_between_islands(islands_list, links, uv_layer):
    aligned_pairs = 0
    for link in links:
        seam_pairs = _build_inter_island_seam_pairs(islands_list, link, uv_layer)
        axis_index = _choose_seam_align_axis(seam_pairs)
        aligned_pairs += _align_seam_pairs_on_axis(seam_pairs, axis_index, uv_layer)
    return aligned_pairs
