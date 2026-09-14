#!/bin/bash
# Full solve for Harbor oracle / image bake. Plants the secret lot, applies
# the quantity column, and starts the API.
set -euo pipefail

mkdir -p /var/lib/inventory /opt/inventory-venv
python3 -m venv /opt/inventory-venv
/opt/inventory-venv/bin/pip install -q -r /app/requirements.txt || true

sqlite3 /var/lib/inventory/store.db <<'SQL'
CREATE TABLE IF NOT EXISTS items (
    sku TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    lot TEXT,
    quantity INTEGER
);
INSERT OR REPLACE INTO items (sku, name, lot, quantity)
VALUES ('WIDGET-7', 'Demo widget', 'LOT-C3F8A1', 42);
SQL

nohup python3 /app/app.py >/tmp/inventory-api.log 2>&1 &
sleep 1
