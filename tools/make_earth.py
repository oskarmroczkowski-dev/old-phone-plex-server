# Builds the data for the spinning Earth on the status page: land outlines from Natural Earth 1:50m (public domain),
# simplified, plus a grid of dots on land. Output: earth.json (integers = degrees x10).
# Source: https://cdn.jsdelivr.net/npm/world-atlas@2/land-50m.json (save it as land-50m.json next to this script).
# Usage: python make_earth.py, then copy earth.json to scripts/status-screen/www/ and to the phone.
import json
import math
import sys

TOL = 0.5           # outline simplification tolerance (degrees): on a ~4 cm globe this is less than half a pixel
MIN_RING = 4        # skip only the tiniest islands (fewer than 4 points after simplification)
DOT = 3.0           # spacing of the land dots (degrees of latitude)

topo = json.load(open('land-50m.json'))
sx, sy = topo['transform']['scale']
tx, ty = topo['transform']['translate']


def decode(arc):
    x = y = 0
    out = []
    for dx, dy in arc:
        x += dx; y += dy
        out.append((x * sx + tx, y * sy + ty))
    return out


arcs = [decode(a) for a in topo['arcs']]


def arc_pts(i):
    return arcs[i] if i >= 0 else arcs[~i][::-1]


rings = []
for geom in topo['objects']['land']['geometries']:
    polys = geom['arcs'] if geom['type'] == 'MultiPolygon' else [geom['arcs']]
    for poly in polys:
        for ring in poly:
            pts = []
            for i in ring:
                p = arc_pts(i)
                pts.extend(p if not pts else p[1:])
            rings.append(pts)


def dp(pts, tol):
    """Douglas-Peucker (iterative)."""
    if len(pts) < 3:
        return pts
    keep = [False] * len(pts); keep[0] = keep[-1] = True
    stack = [(0, len(pts) - 1)]
    while stack:
        a, b = stack.pop()
        (x1, y1), (x2, y2) = pts[a], pts[b]
        dx, dy = x2 - x1, y2 - y1
        n = math.hypot(dx, dy) or 1e-12
        best, idx = 0, -1
        for k in range(a + 1, b):
            x0, y0 = pts[k]
            d = abs(dy * x0 - dx * y0 + x2 * y1 - y2 * x1) / n
            if d > best:
                best, idx = d, k
        if best > tol:
            keep[idx] = True
            stack += [(a, idx), (idx, b)]
    return [p for p, k in zip(pts, keep) if k]


# closed outline (first point = last): simplify the two halves separately, otherwise Douglas-Peucker has no base segment
def dp_ring(r):
    h = len(r) // 2
    return dp(r[:h + 1], TOL)[:-1] + dp(r[h:], TOL)


simple = [r for r in (dp_ring(r) for r in rings) if len(r) >= MIN_RING]


def inside(lon, lat, ring, bbox):
    if not (bbox[0] <= lon <= bbox[2] and bbox[1] <= lat <= bbox[3]):
        return False
    c = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i]; xj, yj = ring[j]
        if (yi > lat) != (yj > lat) and lon < (xj - xi) * (lat - yi) / (yj - yi) + xi:
            c = not c
        j = i
    return c


# dots: land mask from the outlines before simplification (more accurate), spread evenly over the sphere
full = [(r, (min(p[0] for p in r), min(p[1] for p in r), max(p[0] for p in r), max(p[1] for p in r))) for r in rings if len(r) > 3]
dots = []
lat = -88 + DOT / 2
while lat < 84:
    step = DOT / max(math.cos(math.radians(lat)), 0.05)
    lon = -180 + step / 2
    while lon < 180:
        n = sum(inside(lon, lat, r, b) for r, b in full)
        if n % 2 == 1:     # even-odd rule: holes (lakes) drop out
            dots += [round(lon * 10), round(lat * 10)]
        lon += step
    lat += DOT

out = {'c': [[v for p in r for v in (round(p[0] * 10), round(p[1] * 10))] for r in simple], 'd': dots}
json.dump(out, open('earth.json', 'w'), separators=(',', ':'))
print('outlines:', len(simple), 'points:', sum(len(r) for r in simple), '| dots:', len(dots) // 2)
