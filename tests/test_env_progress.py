from __future__ import annotations

import sqlite3

from go_explore.env_progress import (
    ENV_PROGRESS_ARMS,
    PARTIAL_SCHEMA_SQL,
    PLANT_TRIAL_NAME,
    QUANTITY_MIGRATION_SQL,
    TASK_DIR,
    WAREHOUSE_LOT,
    WAREHOUSE_QUANTITY,
    WAREHOUSE_SKU,
)
from go_explore.fixed_budget import FixedBudgetPlanConfig, plan_fixed_budget_runs
from go_explore.harbor import HarborRunConfig
from go_explore.representation_ablation import (
    CLAIM1_ARMS,
    RepresentationAblationConfig,
    run_representation_ablation,
)
from go_explore.snapshots.backends import daytona_snapshot_name


def test_planted_db_keeps_lot_until_migration(tmp_path):
    db = tmp_path / "store.db"
    con = sqlite3.connect(db)
    con.executescript(PARTIAL_SCHEMA_SQL)
    columns = {row[1] for row in con.execute("PRAGMA table_info(items)")}
    assert "lot" in columns
    assert "quantity" not in columns
    sku, lot = con.execute(
        "SELECT sku, lot FROM items WHERE sku = ?", (WAREHOUSE_SKU,)
    ).fetchone()
    assert sku == WAREHOUSE_SKU
    assert lot == WAREHOUSE_LOT

    con.executescript(QUANTITY_MIGRATION_SQL)
    quantity, lot = con.execute(
        "SELECT quantity, lot FROM items WHERE sku = ?", (WAREHOUSE_SKU,)
    ).fetchone()
    assert quantity == WAREHOUSE_QUANTITY
    assert lot == WAREHOUSE_LOT
    con.close()


def test_representation_ablation_can_plan_three_env_progress_arms(tmp_path):
    from tests.test_representation_ablation import _write_root_job

    root, snapshot_name = _write_root_job(tmp_path)
    report = run_representation_ablation(
        RepresentationAblationConfig(
            root_job_dir=root,
            snapshot_name=snapshot_name,
            remaining_token_budget=200_000,
            job_prefix="env",
            include_arms=ENV_PROGRESS_ARMS,
        )
    )
    names = [arm.start_state_type for arm in report.arms]
    assert names == ["clean", "diff_only", "full_snapshot"]
    assert len(report.arms) == 3
    assert len(CLAIM1_ARMS) == 5


def test_lot_is_not_in_agent_visible_task_files():
    assert WAREHOUSE_LOT not in QUANTITY_MIGRATION_SQL
    instruction = (TASK_DIR / "instruction.md").read_text()
    app = (TASK_DIR / "environment" / "app.py").read_text()
    init_sql = (TASK_DIR / "environment" / "migrations" / "001_init.sql").read_text()
    assert WAREHOUSE_LOT not in instruction
    assert WAREHOUSE_LOT not in app
    assert WAREHOUSE_LOT not in init_sql
    assert WAREHOUSE_LOT in PARTIAL_SCHEMA_SQL


def test_env_search_plan_starts_retry_and_root_from_plant(tmp_path):
    plant = daytona_snapshot_name(f"{PLANT_TRIAL_NAME}-step-0")
    base = HarborRunConfig(
        jobs_dir=tmp_path,
        agent=None,
        agent_import_path="go_explore.agents.factory:SnapshotAwareTerminus2",
        env="daytona",
        path=TASK_DIR,
        model="anthropic/claude-haiku-4-5-20251001",
        n_tasks=1,
        export_traces=False,
        environment_kwargs=(f"snapshot_template_name={plant}",),
    )
    manifest = plan_fixed_budget_runs(
        FixedBudgetPlanConfig(
            experiment_id="env-search-seed-0",
            base_config=base,
            job_prefix="env-search",
            total_token_budget=600_000,
            methods=("retry", "promising_branch"),
            seeds=(0,),
            n_retries=3,
            n_branch_continuations=2,
            branch_root_fraction=0.3,
            branch_context_mode="none",
        )
    )
    retries = [job for job in manifest.jobs if job.method == "retry"]
    roots = [job for job in manifest.jobs if job.role == "root"]
    assert len(retries) == 3
    assert len(roots) == 1
    for job in (*retries, *roots):
        assert f"snapshot_template_name={plant}" in job.command
        assert "--path" in job.command
        assert "--dataset" not in job.command
        assert "--agent" not in job.command
        assert "go_explore.agents.factory:SnapshotAwareTerminus2" in job.command
    assert retries[0].budget.token_budget == 200_000
    assert roots[0].budget.token_budget == 180_000
