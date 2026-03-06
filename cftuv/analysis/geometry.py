"""Geometry analysis — IslandInfo, find_island_up, calc_surface_basis, analyze_island_properties.

Layer 1: Determines physical shape properties of each patch.
"""

import math
from mathutils import Vector

from cftuv.config import WORLD_UP


class IslandInfo:
    def __init__(self, faces, index):
        self.faces = faces
        self.index = index
        self.avg_normal = Vector((0, 0, 1))
        self.type = "WALL"
        self.area = 0.0
        self.perimeter = 0.0


def get_expanded_islands(bm, initial_faces):
    """
    Новая функция: находит весь лоскут (до sharp edges),
    но разделяет его на 'full' (все полигоны) и 'core' (только те, что выделил юзер).
    """
    visited = set()
    islands = []
    initial_set = set(initial_faces)

    for start_f in initial_faces:
        if start_f in visited: continue

        full_faces = []
        core_faces = []
        stack = [start_f]
        visited.add(start_f)

        while stack:
            curr = stack.pop()
            full_faces.append(curr)
            if curr in initial_set:
                core_faces.append(curr)

            for edge in curr.edges:
                if not edge.smooth or edge.seam: continue
                for neighbor in edge.link_faces:
                    if neighbor not in visited:
                        visited.add(neighbor)
                        stack.append(neighbor)

        islands.append({
            'full': full_faces,
            'core': core_faces
        })

    return islands


def find_island_up(island):
    """
    Dual-Strategy: ищем ориентацию лоскута двумя путями одновременно.

    Стратегия 1 (Direct Up): классический поиск рёбер, близких к WORLD_UP.
    Стратегия 2 (Derived Up): поиск доминирующих горизонтальных рёбер,
        затем вывод up через cross(normal, right).

    Побеждает стратегия с более сильным сигналом.
    """
    edge_dirs = {}
    for f in island.faces:
        for e in f.edges:
            length = e.calc_length()
            if length < 1e-4: continue
            vec = (e.verts[1].co - e.verts[0].co).normalized()
            if vec.dot(WORLD_UP) < 0: vec = -vec
            qx, qy, qz = round(vec.x, 2), round(vec.y, 2), round(vec.z, 2)
            key = (qx, qy, qz)
            if key not in edge_dirs: edge_dirs[key] = {'vec': vec, 'weight': 0.0}
            edge_dirs[key]['weight'] += length

    # --- Стратегия 1: Direct Up (ищем вертикальные рёбра) ---
    best_direct_up = WORLD_UP
    max_up_score = -1.0
    for data in edge_dirs.values():
        vec = data['vec']
        alignment = abs(vec.dot(WORLD_UP))
        score = data['weight'] * (alignment ** 2)
        if score > max_up_score:
            max_up_score = score
            best_direct_up = vec

    # --- Стратегия 2: Derived Up (ищем горизонтальные рёбра → выводим up) ---
    best_right = None
    max_right_score = -1.0
    for data in edge_dirs.values():
        vec = data['vec']
        horizontal = 1.0 - abs(vec.dot(WORLD_UP))
        score = data['weight'] * (horizontal ** 2)
        if score > max_right_score:
            max_right_score = score
            best_right = vec

    # --- Выбираем победителя ---
    if max_right_score > max_up_score and best_right is not None:
        normal = island.avg_normal
        derived_up = normal.cross(best_right)
        if derived_up.dot(WORLD_UP) < 0:
            derived_up = -derived_up
        if derived_up.length_squared > 1e-6:
            return derived_up.normalized()

    return best_direct_up.normalized() if max_up_score > 0 else WORLD_UP


def analyze_island_properties(island_obj):
    avg_n = Vector((0, 0, 0))
    total_area = 0.0
    perimeter = 0.0
    island_faces_set = set(island_obj.faces)

    for f in island_obj.faces:
        f_area = f.calc_area()
        avg_n += f.normal * f_area
        total_area += f_area
        for e in f.edges:
            link_count = sum(1 for lf in e.link_faces if lf in island_faces_set)
            if link_count == 1: perimeter += e.calc_length()

    if avg_n.length > 0: avg_n.normalize()
    else: avg_n = Vector((0, 0, 1))

    island_obj.avg_normal = avg_n
    island_obj.area = total_area
    island_obj.perimeter = perimeter
    island_obj.type = "FLOOR" if abs(avg_n.dot(WORLD_UP)) > 0.707 else "WALL"


def build_edge_based_links(islands, bm):
    edge_to_islands = {}
    for isl in islands:
        for f in isl.faces:
            for e in f.edges:
                edge_to_islands.setdefault(e.index, set()).add(isl.index)

    links_dict = {}
    for e_idx, isl_indices in edge_to_islands.items():
        if len(isl_indices) == 2:
            i_a, i_b = list(isl_indices)
            if i_a > i_b: i_a, i_b = i_b, i_a
            pair = (i_a, i_b)
            edge_len = bm.edges[e_idx].calc_length()
            if pair not in links_dict:
                v1, v2 = bm.edges[e_idx].verts[0].index, bm.edges[e_idx].verts[1].index
                links_dict[pair] = {
                    'shared_length': 0.0,
                    'shared_verts': set(),
                    'longest_edge_len': edge_len,
                    'longest_edge_verts': [v1, v2]
                }
            links_dict[pair]['shared_length'] += edge_len
            links_dict[pair]['shared_verts'].add(bm.edges[e_idx].verts[0].index)
            links_dict[pair]['shared_verts'].add(bm.edges[e_idx].verts[1].index)
            if edge_len > links_dict[pair]['longest_edge_len']:
                links_dict[pair]['longest_edge_len'] = edge_len
                v1, v2 = bm.edges[e_idx].verts[0].index, bm.edges[e_idx].verts[1].index
                links_dict[pair]['longest_edge_verts'] = [v1, v2]

    return [{'isl_a': k[0], 'isl_b': k[1],
             'shared_length': v['shared_length'],
             'shared_verts': list(v['shared_verts']),
             'longest_edge_verts': v['longest_edge_verts']} for k, v in links_dict.items()]


def calc_surface_basis(normal, ref_up=None):
    if ref_up is None:
        ref_up = WORLD_UP
    up_proj = ref_up - normal * ref_up.dot(normal)
    if up_proj.length_squared < 1e-5:
        tangent = Vector((1, 0, 0))
        tangent = (tangent - normal * tangent.dot(normal)).normalized()
        return tangent, normal.cross(tangent).normalized()
    bitangent = up_proj.normalized()
    return bitangent.cross(normal).normalized(), bitangent
