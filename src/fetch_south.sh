#!/bin/bash
./fetch.sh q4_poi.overpass poi4.json
sleep 5
./fetch.sh q4_south.overpass roads4.json
sleep 5
i=8
for T in "8.375,76.858,8.420,76.930" "8.375,76.930,8.420,77.000" "8.420,76.858,8.462,76.930" "8.420,76.930,8.462,77.000"; do
  i=$((i+1))
  cat > qb_$i.overpass <<EOF
[out:json][timeout:600];
way["building"]($T);
out body;
>;
out skel qt;
EOF
  ./fetch.sh qb_$i.overpass bld_$i.json || echo "tile $i FAILED"
  sleep 6
done
echo SOUTHDONE
