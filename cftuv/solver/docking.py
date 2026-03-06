"""Docking & welding — Manual dock, chain BFS, compute_best_fit_transform.

build_island_graph, dock_all_chains, dock_chain_bfs_layered,
dock_island_to_anchor, fit_vertices + unwrap_interior.
"""

import bpy
import bmesh
import math
from mathutils import Vector

from cftuv.analysis.geometry import get_expanded_islands, IslandInfo, analyze_island_properties


def compute_best_fit_transform(anchor_uvs_list, target_uvs_list):
    """
    Вычисляет жесткую трансформацию (только поворот и смещение).
    """
    if not anchor_uvs_list or len(anchor_uvs_list) != len(target_uvs_list):
        return 0.0, Vector((0.0, 0.0)), Vector((0.0, 0.0))

    n = len(anchor_uvs_list)
    anchor_centroid = sum(anchor_uvs_list, Vector((0.0, 0.0))) / n
    target_centroid = sum(target_uvs_list, Vector((0.0, 0.0))) / n

    num = 0.0
    den = 0.0
    for i in range(n):
        s = target_uvs_list[i] - target_centroid
        t = anchor_uvs_list[i] - anchor_centroid
        num += s.x * t.y - s.y * t.x
        den += s.x * t.x + s.y * t.y

    angle = math.atan2(num, den) if abs(num) > 1e-10 or abs(den) > 1e-10 else 0.0
    return angle, anchor_centroid, target_centroid


def dock_island_to_anchor(uv_layer, target_island_faces, anchor_uvs_list, target_uvs_list,
                          target_vert_indices=None, fit_vertices=False, unwrap_interior=False):
    """
    Применяет вычисленную трансформацию и (опционально) сваривает и пинит вершины шва.
    """
    if not anchor_uvs_list or len(anchor_uvs_list) != len(target_uvs_list):
        return False

    angle, anchor_centroid, target_centroid = compute_best_fit_transform(
        anchor_uvs_list, target_uvs_list
    )

    cos_a, sin_a = math.cos(angle), math.sin(angle)

    for f in target_island_faces:
        for l in f.loops:
            p = l[uv_layer].uv - target_centroid
            rx = p.x * cos_a - p.y * sin_a
            ry = p.x * sin_a + p.y * cos_a
            l[uv_layer].uv = Vector((rx, ry)) + anchor_centroid

    if fit_vertices and target_vert_indices is not None:
        vert_to_anchor_uv = {target_vert_indices[i]: anchor_uvs_list[i] for i in range(len(target_vert_indices))}

        for f in target_island_faces:
            for l in f.loops:
                if l.vert.index in vert_to_anchor_uv:
                    l[uv_layer].uv = vert_to_anchor_uv[l.vert.index].copy()
                    if unwrap_interior:
                        l[uv_layer].pin_uv = True

    return True


def get_edge_uv_coords(edge, face, uv_layer):
    """Получает UV координаты ребра в контексте данного face."""
    uv1 = uv2 = None
    v1_idx, v2_idx = edge.verts[0].index, edge.verts[1].index

    for l in face.loops:
        if l.vert.index == v1_idx:
            uv1 = l[uv_layer].uv.copy()
        elif l.vert.index == v2_idx:
            uv2 = l[uv_layer].uv.copy()

    return (uv1, uv2, v1_idx, v2_idx) if uv1 is not None and uv2 is not None else None


def get_geometry_island_for_face(face, bm):
    """
    Находит геометрический лоскут (island) для данного face.
    """
    islands_data = get_expanded_islands(bm, [face])
    if islands_data:
        return islands_data[0]['full']
    return [face]


def build_island_graph(selected_edges, bm):
    """
    Строит граф связей между геометрическими лоскутами.
    Собирает ВСЕ общие рёбра между каждой парой островов.

    Возвращает:
    - islands: {island_id: {'faces': [BMFace], 'area': float, 'id': int}}
    - graph: {island_id: {neighbor_id: [(edge, my_face, neighbor_face), ...], ...}}
    - face_to_island: {face.index: island_id}
    """
    face_to_island = {}
    islands = {}
    island_counter = 0

    for edge in selected_edges:
        if len(edge.link_faces) != 2:
            continue

        for face in edge.link_faces:
            if face.index in face_to_island:
                continue

            island_faces = get_geometry_island_for_face(face, bm)

            existing_island = None
            for f in island_faces:
                if f.index in face_to_island:
                    existing_island = face_to_island[f.index]
                    break

            if existing_island is not None:
                for f in island_faces:
                    face_to_island[f.index] = existing_island
            else:
                island_id = island_counter
                island_counter += 1

                isl_info = IslandInfo(island_faces, island_id)
                analyze_island_properties(isl_info)

                islands[island_id] = {
                    'faces': island_faces,
                    'area': isl_info.area,
                    'id': island_id
                }

                for f in island_faces:
                    face_to_island[f.index] = island_id

    graph = {isl_id: {} for isl_id in islands}
    processed_edges = set()

    for edge in selected_edges:
        if len(edge.link_faces) != 2:
            continue
        if edge.index in processed_edges:
            continue
        processed_edges.add(edge.index)

        face_a, face_b = edge.link_faces[0], edge.link_faces[1]

        island_a_id = face_to_island.get(face_a.index)
        island_b_id = face_to_island.get(face_b.index)

        if island_a_id is None or island_b_id is None:
            continue
        if island_a_id == island_b_id:
            continue

        if island_b_id not in graph[island_a_id]:
            graph[island_a_id][island_b_id] = []
        graph[island_a_id][island_b_id].append((edge, face_a, face_b))

        if island_a_id not in graph[island_b_id]:
            graph[island_b_id][island_a_id] = []
        graph[island_b_id][island_a_id].append((edge, face_b, face_a))

    return islands, graph, face_to_island


def find_root_island(islands, direction):
    """
    Находит корневой остров для начала BFS.
    AUTO → max area, REVERSE → min area
    """
    if not islands:
        return None

    if direction == 'AUTO':
        return max(islands.keys(), key=lambda x: islands[x]['area'])
    else:
        return min(islands.keys(), key=lambda x: islands[x]['area'])


def find_connected_components(islands, graph):
    """
    Находит все связные компоненты в графе островов.

    Возвращает: [set(island_ids), set(island_ids), ...]
    """
    visited = set()
    components = []

    for island_id in islands:
        if island_id in visited:
            continue

        component = set()
        queue = [island_id]

        while queue:
            curr = queue.pop(0)
            if curr in visited:
                continue
            visited.add(curr)
            component.add(curr)

            for neighbor_id in graph[curr].keys():
                if neighbor_id not in visited:
                    queue.append(neighbor_id)

        components.append(component)

    return components


def dock_all_chains(islands, graph, bm, context, direction, fit_vertices, unwrap_interior):
    """
    Обрабатывает ВСЕ независимые цепочки.

    Возвращает: (total_docked_count, updated_bm)
    """
    components = find_connected_components(islands, graph)

    total_docked = 0

    for component in components:
        if len(component) < 2:
            continue

        if direction == 'AUTO':
            root_id = max(component, key=lambda x: islands[x]['area'])
        else:
            root_id = min(component, key=lambda x: islands[x]['area'])

        docked_count, bm = dock_chain_bfs_layered(
            root_id, islands, graph, bm, context, fit_vertices, unwrap_interior
        )

        total_docked += docked_count

    return total_docked, bm


def dock_chain_bfs_layered(root_id, islands, graph, bm, context, fit_vertices, unwrap_interior):
    """
    Послойный BFS с unwrap после каждого уровня.

    Возвращает: (docked_count, bm)
    """
    uv_layer = bm.loops.layers.uv.verify()

    docked_count = 0
    visited = {root_id}
    current_level = [root_id]

    while True:
        next_level = []
        level_docked_face_indices = []

        for anchor_id in current_level:
            for neighbor_id, edges_data in graph[anchor_id].items():
                if neighbor_id in visited:
                    continue

                anchor_uvs_list = []
                target_uvs_list = []
                target_vert_indices = []
                processed_verts = set()

                for (edge, anchor_face, neighbor_face) in edges_data:
                    for vert in edge.verts:
                        if vert.index in processed_verts:
                            continue
                        processed_verts.add(vert.index)

                        anchor_uv = None
                        for l in anchor_face.loops:
                            if l.vert.index == vert.index:
                                anchor_uv = l[uv_layer].uv.copy()
                                break

                        target_uv = None
                        for l in neighbor_face.loops:
                            if l.vert.index == vert.index:
                                target_uv = l[uv_layer].uv.copy()
                                break

                        if anchor_uv is not None and target_uv is not None:
                            anchor_uvs_list.append(anchor_uv)
                            target_uvs_list.append(target_uv)
                            target_vert_indices.append(vert.index)

                if len(anchor_uvs_list) < 2:
                    visited.add(neighbor_id)
                    next_level.append(neighbor_id)
                    continue

                target_faces = islands[neighbor_id]['faces']

                success = dock_island_to_anchor(
                    uv_layer, target_faces, anchor_uvs_list, target_uvs_list,
                    target_vert_indices=target_vert_indices,
                    fit_vertices=fit_vertices,
                    unwrap_interior=unwrap_interior
                )

                if success:
                    docked_count += 1
                    level_docked_face_indices.extend([f.index for f in target_faces])

                visited.add(neighbor_id)
                next_level.append(neighbor_id)

        if not next_level:
            break

        if fit_vertices and unwrap_interior and level_docked_face_indices:
            orig_edge_sel = [e.index for e in bm.edges if e.select]

            for f in bm.faces:
                f.select = f.index in level_docked_face_indices

            bmesh.update_edit_mesh(context.edit_object.data)

            bpy.ops.uv.unwrap(method='CONFORMAL', margin=0.0)

            bm.free()
            bm = bmesh.from_edit_mesh(context.edit_object.data)
            bm.faces.ensure_lookup_table()
            bm.verts.ensure_lookup_table()
            bm.edges.ensure_lookup_table()
            uv_layer = bm.loops.layers.uv.verify()

            for f_idx in level_docked_face_indices:
                if f_idx < len(bm.faces):
                    for l in bm.faces[f_idx].loops:
                        l[uv_layer].pin_uv = False

            for isl_id in islands:
                new_faces = [bm.faces[f.index] for f in islands[isl_id]['faces'] if f.index < len(bm.faces)]
                islands[isl_id]['faces'] = new_faces

            for isl_id in graph:
                for neighbor_id in graph[isl_id]:
                    new_edges_data = []
                    for (edge, anchor_face, neighbor_face) in graph[isl_id][neighbor_id]:
                        if edge.index < len(bm.edges) and anchor_face.index < len(bm.faces) and neighbor_face.index < len(bm.faces):
                            new_edges_data.append((
                                bm.edges[edge.index],
                                bm.faces[anchor_face.index],
                                bm.faces[neighbor_face.index]
                            ))
                    graph[isl_id][neighbor_id] = new_edges_data

            for f in bm.faces:
                f.select = False
            for e_idx in orig_edge_sel:
                if e_idx < len(bm.edges):
                    bm.edges[e_idx].select = True

        current_level = next_level

    return docked_count, bm


def weld_island_uvs(uv_layer, island, distance=0.001):
    """
    Сшивает UV вершины ВНУТРИ одного острова.
    """
    vert_to_loops = {}
    for f in island.faces:
        for l in f.loops:
            vert_to_loops.setdefault(l.vert.index, []).append(l)

    for v_idx, loops in vert_to_loops.items():
        clusters = []
        for l in loops:
            uv = l[uv_layer].uv
            placed = False
            for cluster in clusters:
                if (cluster['uv'] - uv).length < distance:
                    cluster['loops'].append(l)
                    cluster['uv'] = sum((loop[uv_layer].uv for loop in cluster['loops']), Vector((0.0, 0.0))) / len(cluster['loops'])
                    placed = True
                    break
            if not placed:
                clusters.append({'uv': uv.copy(), 'loops': [l]})

        for cluster in clusters:
            exact_uv = cluster['uv']
            for l in cluster['loops']:
                l[uv_layer].uv = exact_uv.copy()
