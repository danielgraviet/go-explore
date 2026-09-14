from __future__ import annotations

from pathlib import Path

WAREHOUSE_LOT = "LOT-C3F8A1"
WAREHOUSE_SKU = "WIDGET-7"
WAREHOUSE_QUANTITY = 42
DB_PATH = "/var/lib/inventory/store.db"
VENV_PATH = "/opt/inventory-venv"
APP_WORKDIR = "/app"
PLANT_TRIAL_NAME = "staged-service-repair__plant"
CHECKPOINT_JOB_NAME = "env-progress-checkpoint-root"
ENV_PROGRESS_ARMS: tuple[str, ...] = ("clean", "diff_only", "full_snapshot")
TASK_DIR = (
    Path(__file__).resolve().parent.parent / "tasks/env-progress/staged-service-repair"
)

PARTIAL_SCHEMA_SQL = f"""
CREATE TABLE items (
    sku TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    lot TEXT
);
INSERT INTO items (sku, name, lot)
VALUES ('{WAREHOUSE_SKU}', 'Demo widget', '{WAREHOUSE_LOT}');
"""

QUANTITY_MIGRATION_SQL = f"""
ALTER TABLE items ADD COLUMN quantity INTEGER;
UPDATE items SET quantity = {WAREHOUSE_QUANTITY} WHERE sku = '{WAREHOUSE_SKU}';
"""


def plant_shell_script() -> str:
    return f"""
set -e
mkdir -p /var/lib/inventory {APP_WORKDIR}/migrations {VENV_PATH}
python3 -m venv {VENV_PATH}
{VENV_PATH}/bin/pip install -q -r {APP_WORKDIR}/requirements.txt
sqlite3 {DB_PATH} <<'SQL'
{PARTIAL_SCHEMA_SQL.strip()}
SQL
cat > {APP_WORKDIR}/migrations/002_add_quantity.sql <<'SQL'
{QUANTITY_MIGRATION_SQL.strip()}
SQL
cd {APP_WORKDIR}
git add migrations/002_add_quantity.sql
git -c user.email=plant@local -c user.name=plant commit -m 'wip quantity migration'
"""
