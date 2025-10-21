#!/usr/bin/env bash

# Demonstrates how to toggle HTTPS traffic while running a scraper.
# Requires sudo privileges to modify ufw rules.

set -euo pipefail

echo "[1/3] Blocking outbound HTTPS on port 443..."
sudo ufw insert 1 deny out 443 comment 'HN scraping test block'

echo "[2/3] Running BeautifulSoup scraper with limit=5 (expected to fail fast)..."
ENV_PYTHON=\"${VIRTUAL_ENV:-env/bin/python}\"
\"${ENV_PYTHON}\" collect_data.py --limit 5 --skip-selenium || true

echo "[3/3] Removing firewall rule and restoring connectivity..."
sudo ufw delete deny out 443

echo "Firewall drill completed."
