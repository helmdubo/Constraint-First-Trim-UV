"""Patch analysis — find_seam_patches, boundary loops, OUTER/HOLE classification.

Flood-fill patch detection, ordered boundary loop construction,
and inner/outer boundary classification via 2D projection + nesting depth.
"""

from mathutils import Vector

from cftuv.analysis.geometry import calc_surface_basis


def find_seam_patches(bm, base_faces):
    """
    Flood fill лоскутов, разделённых seam/sharp edges.
    Аналог get_expanded_islands, но без разделения на core/full.
    Возвращает: [[BMFace, ...], ...]
    """
    face_set = set(base_faces)
    visited = set()
    patches = []

    for f0 in base_faces:
        if f0 in visited:
            continue
        stack = [f0]
        visited.add(f0)
        patch = []
        while stack:
            f = stack.pop()
            patch.append(f)
            for e in f.edges:
                if e.seam or not e.smooth:
                    continue
                for nf in e.link_faces:
                    if nf in face_set and nf not in visited:
                        visited.add(nf)
                        stack.append(nf)
        patches.append(patch)
    return patches


def find_patch_boundary_edges(patch_faces):
    """
    Boundary edge = ребро с ровно 1 прилегающим фейсом внутри патча.
    Возвращает list of BMEdge.
    """
    patch_set = set(patch_faces)
    seen = set()
    boundary = []
    for f in patch_faces:
        for e in f.edges:
            if e.index in seen:
                continue
            seen.add(e.index)
            in_count = sum(1 for lf in e.link_faces if lf in patch_set)
            if in_count == 1:
                boundary.append(e)
    return boundary


def build_ordered_boundary_loops(boundary_edges):
    """
    Собирает boundary edges в упорядоченные замкнутые loops.
    Возвращает: [{'verts': [BMVert, ...], 'edges': [BMEdge, ...]}, ...]
    """
    v2e = {}
    for e in boundary_edges:
        for v in e.verts:
            v2e.setdefault(v, []).append(e)

    used = set()
    loops = []

    for e0 in boundary_edges:
        if e0 in used:
            continue
        v0 = e0.verts[0]
        used.add(e0)
        verts = [v0, e0.other_vert(v0)]
        edges = [e0]

        curr_v = verts[-1]
        safety = 0
        while safety < 200000:
            safety += 1
            cand = [e for e in v2e.get(curr_v, []) if e not in used]
            if not cand:
                break
            e_next = cand[0]
            used.add(e_next)
            v_next = e_next.other_vert(curr_v)
            edges.append(e_next)
            if v_next == v0:
                loops.append({'verts': verts, 'edges': edges})
                break
            verts.append(v_next)
            curr_v = v_next

    return loops


def classify_boundary_loops_3d(loops, patch_faces):
    """
    Классифицирует boundary loops как OUTER / HOLE через 2D projection + nesting.
    Проецирует на среднюю нормаль патча.

    Возвращает: [{'verts', 'edges', 'kind', 'depth', 'area_2d'}, ...]
    """
    if not loops:
        return []

    avg_n = Vector((0, 0, 0))
    center = Vector((0, 0, 0))
    cnt = 0
    for f in patch_faces:
        avg_n += f.normal
        for v in f.verts:
            center += v.co
            cnt += 1
    if avg_n.length > 1e-12:
        avg_n.normalize()
    else:
        avg_n = Vector((0, 0, 1))
    origin = center / max(cnt, 1)

    seed_t, seed_b = calc_surface_basis(avg_n)

    polys_2d = []
    for lp in loops:
        poly = []
        for v in lp['verts']:
            d = v.co - origin
            poly.append((d.dot(seed_t), d.dot(seed_b)))
        polys_2d.append(poly)

    def signed_area(poly):
        s = 0.0
        n = len(poly)
        for i in range(n):
            x1, y1 = poly[i]
            x2, y2 = poly[(i + 1) % n]
            s += x1 * y2 - x2 * y1
        return 0.5 * s

    def point_in_poly(pt, poly):
        x, y = pt
        inside = False
        n = len(poly)
        for i in range(n):
            x1, y1 = poly[i]
            x2, y2 = poly[(i + 1) % n]
            if (y1 > y) != (y2 > y):
                x_int = (x2 - x1) * (y - y1) / (y2 - y1 + 1e-30) + x1
                if x < x_int:
                    inside = not inside
        return inside

    def interior_point(poly):
        cx = sum(p[0] for p in poly) / len(poly)
        cy = sum(p[1] for p in poly) / len(poly)
        return (cx, cy)

    int_pts = [interior_point(p) for p in polys_2d]

    result = []
    for i, lp in enumerate(loops):
        depth = 0
        for j, poly in enumerate(polys_2d):
            if i == j:
                continue
            if point_in_poly(int_pts[i], poly):
                depth += 1

        if depth == 0:
            kind = "OUTER"
        elif depth % 2 == 1:
            kind = "HOLE"
        else:
            kind = "OUTER"

        result.append({
            'verts': lp['verts'],
            'edges': lp['edges'],
            'kind': kind,
            'depth': depth,
            'area_2d': signed_area(polys_2d[i])
        })

    return result
