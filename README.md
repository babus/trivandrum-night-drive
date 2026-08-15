# Trivandrum Night Drive

A top-down night-driving toy over ~374 km² of the real Thiruvananthapuram, rendered from
OpenStreetMap data. Drive anywhere; your trail becomes a printed "journey receipt" —
distance, detour ratio, time over the speed limit, landmarks passed, and a generated title.

Built as a prototype of the *route-as-a-story* idea: everything on the receipt except the
title sentence comes from real geometry and needs no model.

## Run it

Open `index.html` directly, or serve it — the server is worth it on a phone, because it
hands out a pre-compressed copy (14.2 MB → 5.1 MB over the wire):

    python3 serve.py            # prints both the desktop and LAN URLs

`serve.py` binds all interfaces, so a phone on the same WiFi can reach the LAN URL it
prints. It serves `index.html.gz` only when the browser advertises gzip *and* the `.gz`
is no older than `index.html`, so a rebuild never ships stale bytes. macOS may ask for a
firewall exception the first time.

No network calls at runtime — the map data is baked into the page.

### Controls

`W`/`↑` throttle · `S`/`↓` brake and reverse · `A`/`D` steer · `R` back to the nearest
road · `M` or `Tab` full map and points list · `−`/`+` or scroll to zoom · `Esc` close.

On touch devices the pedals and steering pads appear automatically, two-finger **pinch**
zooms, and `⌖` recentres and resets the zoom.

Pick a **start area** on the title screen — 236 named places grouped into suburbs,
neighbourhoods and junctions — so you don't have to drive 20 km to reach Kovalam. On the
full map, click any point or any name in the list to inspect it, then *Start a drive here*.

Off the carriageway you are not walled in, just slow — about 30 km/h with heavy rolling
drag. Buildings are solid, resolved per-axis so you slide along walls rather than wedging
on them; if you do get stuck in a dead end for two seconds the car is put back on tarmac.

## What the data is

Covers bbox `8.375,76.858 – 8.592,77.000` — about 15.6 x 24 km. Kazhakkoottam, Technopark
and Kariavattom in the north; Kovalam and Vizhinjam in the south; the coast from Kochuveli
through Shanghumugham and Valiyathura to Poonthura; east to Vattiyoorkavu and Poojappura.

| | |
|---|---|
| roads | 30,930 pieces (chunked ≤220 m), RDP at 1.4 m; 1,689 carry a posted `maxspeed` |
| buildings | 177,395 footprints ≥25 m², height from `building:levels` or footprint area |
| areas | 992 parks / water / sand, clipped to 700 m tiles |
| landmarks | 2,386 in 7 categories — food 623, worship 543, shops 390, hotels 304, culture 273, bakeries 217, parks 36 |
| places | 236 `place=suburb/neighbourhood/locality` names, drawn as district labels |

Coordinates are projected to local metres and stored as integer decimetres. Every landmark
carries a one-line descriptor built from its tags ("Hindu temple", "South Indian ·
Restaurant"), some have opening hours, and those with a `wikipedia`/`wikidata` tag are
flagged notable.

Landmark filtering is deliberate — banks, ATMs, clinics and taxi stands are discarded.
That filter is the difference between a story and a directory listing.

Speed limits come from OSM `maxspeed` where it exists (about 5% of ways here). Where it
does not, the HUD falls back to a class assumption — 50 primary, 40 tertiary, 30
residential, 20 service — and marks the readout with `~` so a guess never reads as posted.

### Three things the geometry forced

Each of these was a measured problem, not a precaution:

- **Ways are chunked to ≤220 m.** A single arterial spans kilometres, and with one bounding
  box per way the spatial grid returns it for every cell it crosses, so culling stops working.
- **Areas are clipped to 700 m tiles.** The sea and backwaters arrive as polygons up to
  6.3 x 9.0 km; unclipped, each frame filled a shape far larger than the screen. Fixing this
  took the frame rate from 18 to 35.
- **`meta.ext` is derived from the bbox, not the data.** Overpass returns *complete* ways, so
  a highway crossing the boundary runs kilometres past it and would inflate the world by
  ~3 km a side, shrinking the whole map.

## Regenerating the map data

`index.html` is generated: `src/drive.html` is the template with a `/*__CITYDATA__*/`
placeholder, and `src/citydata.json` is spliced into it by `src/build.py`.

The raw Overpass dumps are kept in `src/` (~110 MB) so `build_data.py` re-runs offline.
Delete them if you don't need to rebuild; the queries below refetch everything.

To change the area, edit `BBOX` in `build_data.py` and the matching bboxes in the Overpass
queries, then:

    cd src
    ./fetch.sh q2_roads.overpass roads2.json     # roads, parks, water
    ./fetch.sh q2_poi.overpass   poi2.json       # landmarks + place names
    ./fetch_buildings.sh                         # buildings, tiled -> bld_*.json
    python3 build_data.py                        # -> citydata.json
    python3 build.py                             # -> ../index.html + .gz

`fetch.sh` rotates through four Overpass mirrors — the main endpoint refuses roughly half
of these requests under load, and `overpass.kumi.systems` or `overpass.private.coffee`
usually picks up the slack. Buildings must be tiled; a whole-city building query times out.

`build_data.py` derives `LAT0`/`LON0` from `BBOX`. The spawn coordinates in `drive.html`
are in metres from that origin, so they need updating whenever the bbox moves.

## Stack

No framework, no bundler, no dependencies. Vanilla JS in one IIFE, Canvas 2D with `Path2D`
for batched geometry, WebAudio for fully synthesised engine and tyre sound (no audio
files), plain CSS with system font stacks (no webfonts). The data pipeline is Python 3
stdlib plus `curl`.

The interesting parts are algorithmic: equirectangular projection to local metres,
Ramer–Douglas–Peucker simplification, a uniform spatial-hash grid for culling, ray-casting
point-in-polygon collision, axis-separated collision resolution for wall sliding,
Sutherland–Hodgman clipping for the area tiles, and a fake extrusion that offsets each roof
away from the screen centre.

## Attribution

Map data © OpenStreetMap contributors, available under the
[Open Database License](https://www.openstreetmap.org/copyright). Attribution appears on
the title card and on every generated receipt; keep it if you redistribute this.

ODbL share-alike binds the *database*. A rendered image — a screenshot, a receipt PNG — is
a Produced Work and needs attribution only.
