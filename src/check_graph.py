"""Sanity-check the routing graph: coverage, detour ratio, A* success rate.

Run against a built citydata.json. A route that is much longer than the crow
line means the graph is joined up but wrong somewhere; a failed route means it
is not joined up at all.
"""
import heapq
import json
import math
import random
import time

import route_graph

d = json.load(open('citydata.json'))
roads = d['roads']
g = route_graph.build(roads)
N, E = g['n'], g['e']
nn = len(N) // 2
coords = [(N[2 * k], N[2 * k + 1]) for k in range(nn)]

adj = [[] for _ in range(nn)]
for j in range(0, len(E), 5):
    a, b, i, v0, v1 = E[j:j + 5]
    w = route_graph.edge_len(roads, coords, (a, b, i, v0, v1))
    adj[a].append((b, w))
    if not roads[i].get('ow'):
        adj[b].append((a, w))

one = sum(1 for j in range(0, len(E), 5) if roads[E[j + 2]].get('ow'))
print('  one-way edges %d of %d' % (one, len(E) // 5))


def astar(s, t):
    tx, ty = coords[t]
    h = lambda k: math.hypot(coords[k][0] - tx, coords[k][1] - ty) * 0.1
    best = {s: 0.0}
    q = [(h(s), 0.0, s)]
    seen = set()
    while q:
        _f, gc, k = heapq.heappop(q)
        if k == t:
            return gc
        if k in seen:
            continue
        seen.add(k)
        for nb, w in adj[k]:
            ng = gc + w
            if ng < best.get(nb, 1e18):
                best[nb] = ng
                heapq.heappush(q, (ng + h(nb), ng, nb))
    return None


random.seed(7)
ok = fail = 0
ratios, times = [], []
for _ in range(200):
    s, t = random.randrange(nn), random.randrange(nn)
    crow = math.hypot(coords[s][0] - coords[t][0], coords[s][1] - coords[t][1]) * 0.1
    if crow < 2000:
        continue
    t0 = time.time()
    r = astar(s, t)
    times.append(time.time() - t0)
    if r is None:
        fail += 1
    else:
        ok += 1
        ratios.append(r / crow)

ratios.sort()
print('  routes ok %d  failed %d' % (ok, fail))
print('  detour vs crow line: median %.2fx  p90 %.2fx  worst %.2fx'
      % (ratios[len(ratios) // 2], ratios[int(len(ratios) * .9)], ratios[-1]))
print('  A* time: median %.0f ms  worst %.0f ms'
      % (sorted(times)[len(times) // 2] * 1000, max(times) * 1000))
