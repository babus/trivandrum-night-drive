#!/bin/bash
# fetch.sh <queryfile> <outfile> — tries Overpass mirrors until one returns JSON
Q="$1"; OUT="$2"
EPS=(
  "https://overpass-api.de/api/interpreter"
  "https://overpass.kumi.systems/api/interpreter"
  "https://overpass.private.coffee/api/interpreter"
  "https://overpass.osm.jp/api/interpreter"
)
for attempt in 1 2; do
  for ep in "${EPS[@]}"; do
    curl -s -m 540 -X POST -d @"$Q" "$ep" -o "$OUT"
    if head -c 20 "$OUT" 2>/dev/null | grep -q '{'; then
      echo "OK  $OUT  <- $ep  ($(du -h "$OUT" | cut -f1))"
      exit 0
    fi
    sleep 5
  done
done
echo "FAIL $OUT"; exit 1
