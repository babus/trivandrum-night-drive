import json, math, collections, os, glob

BBOX = (8.375, 76.858, 8.592, 77.000)             # minLat, minLon, maxLat, maxLon
LAT0 = (BBOX[0] + BBOX[2]) / 2
LON0 = (BBOX[1] + BBOX[3]) / 2
MPD_LAT = 110574.0
MPD_LON = 111320.0 * math.cos(math.radians(LAT0))

def proj(lat, lon):
    return ((lon - LON0) * MPD_LON, (lat - LAT0) * MPD_LAT)

def load(*paths):
    """Merge one or more Overpass dumps (buildings arrive as bbox tiles)."""
    nodes, ways, seen = {}, [], set()
    for p in paths:
        if not os.path.exists(p):
            print('  ! missing', p)
            continue
        d = json.load(open(p))
        for e in d['elements']:
            if e['type'] == 'node':
                nodes[e['id']] = e
            elif e['type'] == 'way' and e['id'] not in seen:
                seen.add(e['id'])
                ways.append(e)
    return nodes, ways

def rdp(pts, eps):
    if len(pts) < 3:
        return pts
    def d(p, a, b):
        (x, y), (x1, y1), (x2, y2) = p, a, b
        dx, dy = x2 - x1, y2 - y1
        L = dx * dx + dy * dy
        if L == 0:
            return math.hypot(x - x1, y - y1)
        t = max(0.0, min(1.0, ((x - x1) * dx + (y - y1) * dy) / L))
        return math.hypot(x - (x1 + t * dx), y - (y1 + t * dy))
    dmax, idx = 0.0, 0
    for i in range(1, len(pts) - 1):
        dd = d(pts[i], pts[0], pts[-1])
        if dd > dmax:
            dmax, idx = dd, i
    if dmax > eps:
        return rdp(pts[:idx + 1], eps)[:-1] + rdp(pts[idx:], eps)
    return [pts[0], pts[-1]]

def flat(pts):
    out = []
    for x, y in pts:
        out.append(int(round(x * 10)))
        out.append(int(round(y * 10)))
    return out

def area(pts):
    a = 0.0
    for i in range(len(pts)):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % len(pts)]
        a += x1 * y2 - x2 * y1
    return abs(a) / 2.0

def centroid(pts):
    return (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))

# ---------- roads / areas / landmarks ----------
rn, rw = load('roads2.json', 'roads3n.json', 'roads3w.json', 'roads4.json')

ROAD_CLASS = {
    'motorway': 'p', 'trunk': 'p', 'primary': 'p', 'motorway_link': 'p',
    'trunk_link': 'p', 'primary_link': 'p',
    'secondary': 's', 'secondary_link': 's',
    'tertiary': 't', 'tertiary_link': 't',
    'residential': 'r', 'unclassified': 'r', 'living_street': 'r', 'road': 'r',
    'service': 'v', 'services': 'v', 'track': 'v',
    'footway': 'f', 'path': 'f', 'pedestrian': 'f', 'steps': 'f', 'cycleway': 'f',
}

def parse_speed(v):
    """OSM maxspeed is free text: '50', '50 mph', 'IN:urban'. Take a leading number."""
    if not v:
        return None
    v = v.strip().lower()
    mph = v.endswith('mph')
    num = ''
    for ch in v:
        if ch.isdigit():
            num += ch
        elif num:
            break
    if not num:
        return None
    n = int(num)
    return int(round(n * 1.609)) if mph else n

def chunk(pts, max_len=220.0, max_pts=14):
    """Split long ways so each piece has a tight bbox.

    A single arterial can span kilometres; with one bbox per way the spatial grid
    returns it for every cell it crosses, so both culling and the road probe end up
    scanning most of the city. Pieces overlap by a point so strokes stay continuous.
    """
    out, cur, acc = [], [pts[0]], 0.0
    for i in range(1, len(pts)):
        acc += math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1])
        cur.append(pts[i])
        if acc >= max_len or len(cur) >= max_pts:
            out.append(cur)
            cur = [pts[i]]
            acc = 0.0
    if len(cur) > 1:
        out.append(cur)
    return out or [pts]

def clip_poly(pts, xmin, ymin, xmax, ymax):
    """Sutherland-Hodgman clip against an axis-aligned rectangle."""
    def pass_edge(src, inside, cut):
        out = []
        for i in range(len(src)):
            cur, prv = src[i], src[i - 1]
            ci, pi = inside(cur), inside(prv)
            if ci:
                if not pi:
                    out.append(cut(prv, cur))
                out.append(cur)
            elif pi:
                out.append(cut(prv, cur))
        return out

    def cx_(p, q, x):
        t = (x - p[0]) / (q[0] - p[0])
        return (x, p[1] + t * (q[1] - p[1]))

    def cy_(p, q, y):
        t = (y - p[1]) / (q[1] - p[1])
        return (p[0] + t * (q[0] - p[0]), y)

    for inside, cut in (
        (lambda p: p[0] >= xmin, lambda a, b: cx_(a, b, xmin)),
        (lambda p: p[0] <= xmax, lambda a, b: cx_(a, b, xmax)),
        (lambda p: p[1] >= ymin, lambda a, b: cy_(a, b, ymin)),
        (lambda p: p[1] <= ymax, lambda a, b: cy_(a, b, ymax)),
    ):
        if not pts:
            return []
        pts = pass_edge(pts, inside, cut)
    return pts

AREA_TILE = 700.0

def tile_area(pts):
    """Split a big polygon into tile-sized pieces.

    The sea and the backwaters are kilometres across. With one polygon per water
    body the spatial grid hands them back for almost every cell, and each frame
    fills a shape far larger than the screen — pure overdraw.
    """
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    w, h = max(xs) - min(xs), max(ys) - min(ys)
    if w <= AREA_TILE and h <= AREA_TILE:
        return [pts]
    out = []
    x = math.floor(min(xs) / AREA_TILE) * AREA_TILE
    while x < max(xs):
        y = math.floor(min(ys) / AREA_TILE) * AREA_TILE
        while y < max(ys):
            piece = clip_poly(pts, x, y, x + AREA_TILE, y + AREA_TILE)
            if len(piece) >= 3:
                out.append(piece)
            y += AREA_TILE
        x += AREA_TILE
    return out or [pts]

roads, areas = [], []
AREA_KIND = {
    'park': 'park', 'garden': 'park', 'pitch': 'pitch', 'playground': 'pitch',
    'golf_course': 'park', 'sports_centre': 'pitch', 'stadium': 'pitch',
    'water': 'water', 'wood': 'wood', 'scrub': 'wood', 'grassland': 'park',
    'beach': 'sand', 'sand': 'sand', 'wetland': 'water',
}

for w in rw:
    t = w.get('tags') or {}
    ns = w.get('nodes', [])
    pts = [proj(rn[i]['lat'], rn[i]['lon']) for i in ns if i in rn]
    if len(pts) < 2:
        continue
    if 'highway' in t:
        cls = ROAD_CLASS.get(t['highway'])
        if not cls:
            continue
        sp = rdp(pts, 1.4)
        nm = t.get('name')
        ms = parse_speed(t.get('maxspeed'))
        ow = 1 if t.get('oneway') == 'yes' else 0
        for piece in chunk(sp):
            r = {'c': cls, 'p': flat(piece)}
            if nm:
                r['n'] = nm
            if ms:
                r['ms'] = ms                  # posted limit; absent means "assume by class"
            if ow:
                r['ow'] = 1
            roads.append(r)
    else:
        kind = AREA_KIND.get(t.get('leisure') or '') or AREA_KIND.get(t.get('natural') or '')
        if kind and len(pts) > 3 and area(pts) > 250:
            simple = rdp(pts, 2.0)
            for piece in tile_area(simple):
                areas.append({'k': kind, 'p': flat(piece)})

# ---------- landmarks (curated categories only) ----------
CULTURE = {'museum', 'gallery', 'artwork', 'attraction', 'viewpoint', 'zoo', 'aquarium', 'theme_park'}
FOOD = {'cafe', 'restaurant', 'fast_food', 'ice_cream', 'food_court', 'bar', 'pub', 'biergarten'}
CIVIC = {'library', 'theatre', 'arts_centre', 'cinema', 'university', 'college', 'community_centre'}
STAY = {'hotel', 'hostel', 'guest_house', 'resort', 'motel'}
# Bakeries get their own category — in Trivandrum they are a category.
BAKERY = {'bakery', 'confectionery', 'pastry', 'chocolate'}
FOOD_SHOP = {'tea', 'coffee', 'ice_cream'}
SHOPPING = {'supermarket', 'mall', 'department_store', 'greengrocer', 'seafood',
            'butcher', 'books', 'convenience', 'spices', 'deli', 'farm'}

def classify(t):
    if 'historic' in t:
        return 'culture'
    tu = t.get('tourism')
    if tu in CULTURE:
        return 'culture'
    if tu in STAY:
        return 'stay'
    if tu in ('apartment', 'information'):
        return None
    sh = t.get('shop')
    if sh in BAKERY:
        return 'bakery'
    if sh in FOOD_SHOP:
        return 'food'
    if sh in SHOPPING:
        return 'shop'
    am = t.get('amenity')
    if am in FOOD:
        return 'food'
    if am == 'place_of_worship':
        return 'worship'
    if am in CIVIC:
        return 'culture'
    if am == 'marketplace':
        return 'shop'
    if t.get('leisure') in ('park', 'garden'):
        return 'park'
    return None

KIND = {
    'cafe': 'Café', 'restaurant': 'Restaurant', 'fast_food': 'Fast food',
    'ice_cream': 'Ice cream parlour', 'food_court': 'Food court', 'bar': 'Bar',
    'pub': 'Pub', 'biergarten': 'Beer garden',
    'bakery': 'Bakery', 'confectionery': 'Confectionery', 'pastry': 'Pastry shop',
    'chocolate': 'Chocolate shop', 'tea': 'Tea shop', 'coffee': 'Coffee shop',
    'supermarket': 'Supermarket', 'mall': 'Shopping mall', 'department_store': 'Department store',
    'greengrocer': 'Greengrocer', 'seafood': 'Fish shop', 'butcher': 'Butcher',
    'books': 'Bookshop', 'convenience': 'Corner shop', 'spices': 'Spice shop',
    'deli': 'Deli', 'farm': 'Farm shop', 'marketplace': 'Market',
    'hotel': 'Hotel', 'hostel': 'Hostel', 'guest_house': 'Guest house',
    'resort': 'Resort', 'motel': 'Motel',
    'museum': 'Museum', 'gallery': 'Art gallery', 'artwork': 'Public artwork',
    'attraction': 'Attraction', 'viewpoint': 'Viewpoint', 'zoo': 'Zoo',
    'aquarium': 'Aquarium', 'theme_park': 'Theme park',
    'library': 'Library', 'theatre': 'Theatre', 'arts_centre': 'Arts centre',
    'cinema': 'Cinema', 'university': 'University', 'college': 'College',
    'community_centre': 'Community centre',
    'park': 'Park', 'garden': 'Garden',
    'memorial': 'Memorial', 'monument': 'Monument', 'statue': 'Statue',
    'building': 'Historic building', 'castle': 'Palace', 'ruins': 'Ruins',
    'archaeological_site': 'Archaeological site', 'tomb': 'Tomb', 'church': 'Historic church',
}

def tidy(v):
    return v.replace('_', ' ').replace(';', ', ').strip()

def describe(t, name=''):
    """One short human line for the discovery pop-up, built from the OSM tags."""
    base = None
    for k in ('historic', 'tourism', 'shop', 'amenity', 'leisure'):
        v = t.get(k)
        if v:
            base = KIND.get(v) or tidy(v).capitalize()
            break

    if t.get('amenity') == 'place_of_worship':
        den = tidy(t.get('denomination') or '')
        rel = tidy(t.get('religion') or '')
        label = den or rel
        if label:
            word = {'christian': 'church', 'muslim': 'mosque', 'hindu': 'temple',
                    'jain': 'temple', 'buddhist': 'temple', 'sikh': 'gurdwara'}.get(rel, 'place of worship')
            base = (label.title() + ' ' + word)
        else:
            base = 'Place of worship'

    cui = t.get('cuisine')
    if cui and base:
        c = tidy(cui).title()
        if len(c) <= 22:
            base = c + ' · ' + base

    if not base:
        return None
    extra = t.get('operator') or t.get('brand')
    nl = name.lower()
    if (extra and len(base) + len(extra) < 52
            and extra.lower() not in base.lower()
            and extra.lower() not in nl and nl not in extra.lower()):
        base += ' · ' + tidy(extra)
    return base[:60]

landmarks = []
seen = set()

def add_lm(name, cat, x, y, tags=None):
    key = (name.lower(), round(x / 25), round(y / 25))
    if key in seen:
        return
    seen.add(key)
    rec = {'n': name, 'k': cat, 'x': int(round(x * 10)), 'y': int(round(y * 10))}
    t = tags or {}
    d = describe(t, name)
    if d:
        rec['d'] = d
    if t.get('wikipedia') or t.get('wikidata'):
        rec['w'] = 1                      # has an encyclopaedia entry: worth flagging
    oh = t.get('opening_hours')
    if oh and len(oh) <= 34:
        rec['h'] = oh
    landmarks.append(rec)

sn, sw = load('poi2.json', 'poi3.json', 'poi4.json')

# Neighbourhood / junction names — how locals actually navigate. Not collectible;
# drawn as faint district labels on the map.
PLACE_RANK = {'city': 4, 'town': 4, 'suburb': 3, 'village': 3, 'borough': 3,
              'quarter': 2, 'neighbourhood': 2, 'hamlet': 2,
              'locality': 1, 'isolated_dwelling': 1}

# Junctions are barely tagged as such in OSM here (three of them citywide), but Kerala
# navigates by bus stop, and those are named after exactly the junctions people mean.
GENERIC_STOP = {'bus stop', 'bus station', 'bus stand', 'stop', 'busstop', 'junction'}

places = []
seen_place = set()

def add_place(name, rank, x, y):
    name = name.strip()
    if not name or name.lower() in GENERIC_STOP:
        return
    key = (name.lower(), round(x / 120), round(y / 120))
    if key in seen_place:
        return
    seen_place.add(key)
    places.append({'n': name, 'r': rank,
                   'x': int(round(x * 10)), 'y': int(round(y * 10))})

for e in sn.values():
    t = e.get('tags') or {}
    nm, pk = t.get('name'), t.get('place')
    if nm and pk in PLACE_RANK:
        x, y = proj(e['lat'], e['lon'])
        add_place(nm, PLACE_RANK[pk], x, y)

tn, _tw = load('stops.json')
for e in tn.values():
    t = e.get('tags') or {}
    nm = t.get('name')
    if not nm:
        continue
    x, y = proj(e['lat'], e['lon'])
    if t.get('place') in PLACE_RANK:
        add_place(nm, PLACE_RANK[t['place']], x, y)
    elif t.get('amenity') == 'bus_station' or t.get('railway') in ('station', 'halt'):
        add_place(nm, 2, x, y)
    elif t.get('highway') == 'bus_stop' or t.get('junction') or t.get('public_transport'):
        add_place(nm, 1, x, y)

for nodes, ways in ((rn, rw), (sn, sw)):
    for e in nodes.values():
        t = e.get('tags') or {}
        nm = t.get('name')
        if not nm:
            continue
        cat = classify(t)
        if cat:
            x, y = proj(e['lat'], e['lon'])
            add_lm(nm, cat, x, y, t)
    for w in ways:
        t = w.get('tags') or {}
        nm = t.get('name')
        if not nm:
            continue
        cat = classify(t)
        if not cat:
            continue
        pts = [proj(nodes[i]['lat'], nodes[i]['lon'])
               for i in w.get('nodes', []) if i in nodes]
        if len(pts) < 3:
            continue
        cx, cy = centroid(pts)
        add_lm(nm, cat, cx, cy, t)

# ---------- buildings ----------
bn, bw = load(*sorted(glob.glob('bld_*.json')))
buildings = []
for w in bw:
    ns = w.get('nodes', [])
    pts = [proj(bn[i]['lat'], bn[i]['lon']) for i in ns if i in bn]
    if len(pts) < 4:
        continue
    if pts[0] == pts[-1]:
        pts = pts[:-1]
    a = area(pts)
    if a < 25:                        # city-wide now; drop sheds to keep the file sane
        continue
    sp = rdp(pts + [pts[0]], 1.1)[:-1]
    if len(sp) < 3:
        continue
    t = w.get('tags') or {}
    lv = t.get('building:levels')
    try:
        h = max(1, min(14, int(float(lv))))
    except (TypeError, ValueError):
        h = 1 if a < 90 else (2 if a < 400 else 4)
    buildings.append({'h': h, 'p': flat(sp)})

# From the bbox, NOT from the data extremes: Overpass returns whole ways, so a highway
# crossing the boundary runs kilometres past it and would inflate the world by ~3 km a side.
_x0, _y0 = proj(BBOX[0], BBOX[1])
_x1, _y1 = proj(BBOX[2], BBOX[3])
EXT = [round(_x0), round(_y0), round(_x1), round(_y1)]

out = {
    'meta': {
        'lat0': LAT0, 'lon0': LON0,
        'mpdLat': round(MPD_LAT, 2), 'mpdLon': round(MPD_LON, 2),
        'unit': 0.1,
        'ext': EXT,                    # [minX, minY, maxX, maxY] metres; bounds + map spans
        'attrib': 'Map data © OpenStreetMap contributors (ODbL)',
    },
    'roads': roads,
    'areas': areas,
    'buildings': buildings,
    'landmarks': landmarks,
    'places': places,
}

s = json.dumps(out, separators=(',', ':'), ensure_ascii=False)
open('citydata.json', 'w').write(s)
print('roads', len(roads), 'areas', len(areas), 'buildings', len(buildings),
      'landmarks', len(landmarks), 'places', len(places))
print('bytes', len(s))
print(collections.Counter(l['k'] for l in landmarks))
print('roads with posted maxspeed:', sum(1 for r in roads if 'ms' in r))
xs = [p for b in buildings for p in b['p'][0::2]]
ys = [p for b in buildings for p in b['p'][1::2]]
print('extent m x', min(xs) / 10, max(xs) / 10, 'y', min(ys) / 10, max(ys) / 10)
