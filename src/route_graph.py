"""Turn the chunked road pieces into a routing graph.

The pieces are not a graph. chunk() splits a way every 220 m and hands the
next piece a copy of the last point, so consecutive chunks of one way do share
an endpoint -- but a side road tees into the *interior* of a through road, and
RDP at 1.4 m happily deletes the vertex it tees into. 44% of pieces therefore
share no endpoint with anything.

Noding fixes it: project every piece endpoint onto every road segment within
3 m and split the segment there. That recovers a single component holding
99.4% of the 3,792 km. Only that component is emitted, so a route request can
never start on an island.

Footways are excluded -- 'f' covers steps and cycleways, which a car cannot use.

Emitted (all integers, decimetres, same frame as roads):
    n  flat node coordinates          [x0,y0, x1,y1, ...]
    e  flat edges, 5 ints per edge    [a, b, piece, v0, v1, ...]

An edge runs from node a to node b along roads[piece]: node a, then piece
vertices v0..v1 inclusive, then node b. v0 > v1 means the edge carries no
interior vertices. Cost and direction are derived in the browser -- length
from the geometry, one-way from roads[piece].ow, which always points a->b
because edges are cut in increasing order along the piece.
"""
import collections
import math

DRIVABLE = frozenset('psrtv')
TOL = 30                      # 3.0 m, in the 0.1 m units the roads use
CELL = 600                    # 60 m spatial-hash cell


def _dedupe(points, tol):
    """Collapse points within tol of each other. Returns (coords, index-per-point)."""
    grid, coords, ids = collections.defaultdict(list), [], []
    for x, y in points:
        cx, cy = x // tol, y // tol
        hit = -1
        for gx in (cx - 1, cx, cx + 1):
            for gy in (cy - 1, cy, cy + 1):
                for k in grid.get((gx, gy), ()):
                    if math.hypot(coords[k][0] - x, coords[k][1] - y) <= tol:
                        hit = k
                        break
                if hit >= 0:
                    break
            if hit >= 0:
                break
        if hit < 0:
            hit = len(coords)
            coords.append((x, y))
            grid[(cx, cy)].append(hit)
        ids.append(hit)
    return coords, ids


def _project(px, py, x0, y0, x1, y1):
    """Distance from p to the segment, and the parameter t in [0,1] along it."""
    dx, dy = x1 - x0, y1 - y0
    L = dx * dx + dy * dy
    if L == 0:
        return math.hypot(px - x0, py - y0), 0.0
    t = max(0.0, min(1.0, ((px - x0) * dx + (py - y0) * dy) / L))
    return math.hypot(px - (x0 + t * dx), py - (y0 + t * dy)), t


def build(roads, tol=TOL, verbose=True):
    drive = [i for i, r in enumerate(roads) if r['c'] in DRIVABLE]

    # 1. every piece endpoint is a candidate junction, merged when coincident
    ends = []
    for i in drive:
        p = roads[i]['p']
        ends.append((p[0], p[1]))
        ends.append((p[-2], p[-1]))
    coords, _ = _dedupe(ends, tol)

    # 2. spatial hash of the merged nodes, so each piece can find the ones on it
    grid = collections.defaultdict(list)
    for k, (x, y) in enumerate(coords):
        grid[(x // CELL, y // CELL)].append(k)

    # 3. cut each piece wherever a node lands on it
    edges = []
    for i in drive:
        p = roads[i]['p']
        nseg = len(p) // 2 - 1
        cuts = {}                                  # node -> (segment, t)
        for s in range(nseg):
            x0, y0, x1, y1 = p[2 * s], p[2 * s + 1], p[2 * s + 2], p[2 * s + 3]
            lo_x, hi_x = min(x0, x1) - tol, max(x0, x1) + tol
            lo_y, hi_y = min(y0, y1) - tol, max(y0, y1) + tol
            for gx in range(lo_x // CELL, hi_x // CELL + 1):
                for gy in range(lo_y // CELL, hi_y // CELL + 1):
                    for k in grid.get((gx, gy), ()):
                        nx, ny = coords[k]
                        if not (lo_x <= nx <= hi_x and lo_y <= ny <= hi_y):
                            continue
                        d, t = _project(nx, ny, x0, y0, x1, y1)
                        if d > tol:
                            continue
                        # keep the earliest position for a node touching twice
                        if k not in cuts or (s, t) < cuts[k]:
                            cuts[k] = (s, t)
        if len(cuts) < 2:
            continue
        order = sorted(cuts.items(), key=lambda kv: kv[1])
        for (a, (sa, ta)), (b, (sb, tb)) in zip(order, order[1:]):
            if a == b:
                continue
            # interior vertices strictly between the two cut positions
            v0 = sa + 1 if ta < 1.0 else sa + 2
            v1 = sb if tb > 0.0 else sb - 1
            edges.append((a, b, i, v0, v1))

    # 4. keep the largest connected component only
    parent = list(range(len(coords)))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for a, b, _i, _v0, _v1 in edges:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb
    size = collections.Counter(find(k) for k in range(len(coords)))
    if not size:
        raise SystemExit('route_graph: no nodes')
    main = size.most_common(1)[0][0]

    keep, remap = [], {}
    for k in range(len(coords)):
        if find(k) == main:
            remap[k] = len(keep)
            keep.append(coords[k])
    kept = [e for e in edges if find(e[0]) == main]

    n, e = [], []
    for x, y in keep:
        n += [x, y]
    for a, b, i, v0, v1 in kept:
        e += [remap[a], remap[b], i, v0, v1]

    if verbose:
        span = sum(edge_len(roads, coords, e) for e in kept)
        whole = sum(_piece_len(roads[i]['p']) for i in drive)
        print('  graph %d nodes %d edges  %.0f/%.0f km drivable (%.1f%%)'
              % (len(keep), len(kept), span / 1000, whole / 1000, 100 * span / whole))
        print('  dropped %d islands' % (len(size) - 1))
    return {'n': n, 'e': e}


def _piece_len(p):
    return sum(math.hypot(p[i + 2] - p[i], p[i + 3] - p[i + 1])
               for i in range(0, len(p) - 2, 2)) * 0.1


def edge_pts(roads, coords, edge):
    """Node a, the interior vertices it carries, then node b -- the drawn geometry."""
    a, b, i, v0, v1 = edge
    p = roads[i]['p']
    last = len(p) // 2 - 1
    pts = [coords[a]]
    for v in range(max(v0, 0), min(v1, last) + 1):
        pts.append((p[2 * v], p[2 * v + 1]))
    pts.append(coords[b])
    return pts


def edge_len(roads, coords, edge):
    pts = edge_pts(roads, coords, edge)
    return sum(math.hypot(pts[j + 1][0] - pts[j][0], pts[j + 1][1] - pts[j][1])
               for j in range(len(pts) - 1)) * 0.1
