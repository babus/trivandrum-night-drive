#!/bin/bash
./fetch.sh q3_north.overpass roads3n.json
sleep 5
./fetch.sh q3_west.overpass roads3w.json
sleep 5
i=4
for T in "8.556,76.858,8.592,76.930" "8.556,76.930,8.592,77.000" "8.462,76.858,8.510,76.905" "8.510,76.858,8.556,76.905"; do
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
echo DONE
ls -la roads3*.json bld_5.json bld_6.json bld_7.json bld_8.json 2>/dev/null
