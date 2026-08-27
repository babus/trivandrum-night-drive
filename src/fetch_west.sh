#!/bin/bash
# The original bbox stopped at 76.858, which cuts through Menamkulam and leaves
# the Kazhakkoottam coast strip off the map. Pull 76.843-76.859 so that
# neighbourhood is inside the world instead of 700 m past its western edge.
#
# Roads, water and POI go the full height of the map; buildings only north of
# 8.52, because below that the strip is entirely Arabian Sea.
set -e
cd "$(dirname "$0")"

W=76.843
E=76.859

cat > q6_west.overpass <<EOF
[out:json][timeout:600];
(
  way["highway"](8.375,$W,8.592,$E);
  way["leisure"](8.375,$W,8.592,$E);
  way["natural"](8.375,$W,8.592,$E);
  way["waterway"](8.375,$W,8.592,$E);
);
out body;
>;
out skel qt;
EOF

cat > q6_poi.overpass <<EOF
[out:json][timeout:600];
(
  node["amenity"](8.375,$W,8.592,$E);
  node["tourism"](8.375,$W,8.592,$E);
  node["historic"](8.375,$W,8.592,$E);
  node["shop"](8.375,$W,8.592,$E);
  node["place"](8.375,$W,8.592,$E);
  node["highway"="bus_stop"](8.375,$W,8.592,$E);
  way["tourism"](8.375,$W,8.592,$E);
  way["historic"](8.375,$W,8.592,$E);
  way["shop"](8.375,$W,8.592,$E);
);
out body;
>;
out skel qt;
EOF

cat > qb_13.overpass <<EOF
[out:json][timeout:600];
way["building"](8.520,$W,8.592,$E);
out body;
>;
out skel qt;
EOF

./fetch.sh q6_west.overpass roads6w.json
sleep 5
./fetch.sh q6_poi.overpass poi6.json
sleep 5
./fetch.sh qb_13.overpass bld_13.json
echo DONE
ls -la roads6w.json poi6.json bld_13.json
