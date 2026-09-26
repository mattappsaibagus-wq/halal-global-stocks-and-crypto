#!/usr/bin/env bash
# Render static-site build: publish the dashboard and point it at the scan data
# that GitHub Actions publishes to GitHub Pages after every scan.
set -euo pipefail
OWNER="${GITHUB_OWNER:-mattappsaibagus-wq}"
REPO="${GITHUB_REPO:-halal-global-stocks-and-crypto}"
DATA_BASE="${DATA_BASE:-https://${OWNER}.github.io/${REPO}/}"

rm -rf public && mkdir -p public
cp dashboard/index.html dashboard/markets.json public/
printf 'window.HALAL_CONFIG = { dataBase: "%s", repo: "%s/%s" };\n' "$DATA_BASE" "$OWNER" "$REPO" > public/config.js
echo "Built public/ with data from ${DATA_BASE}"
