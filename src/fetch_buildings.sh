#!/bin/bash
i=0
for T in "8.462,76.905,8.509,76.9525" "8.462,76.9525,8.509,77.000" "8.509,76.905,8.556,76.9525" "8.509,76.9525,8.556,77.000"; do
  i=$((i+1))
  cat > qb_$i.overpass <<EOF
[out:json][timeout:600];
way["building"]($T);
out body;
>;
out skel qt;
EOF
  ./fetch.sh qb_$i.overpass bld_$i.json || echo "tile $i FAILED"
  sleep 8
done
ls -la bld_*.json
