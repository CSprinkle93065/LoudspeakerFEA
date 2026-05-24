"""Tests for persistence and database operations.

Covers: database init, designs table CRUD, settings table persistence.
"""

import json
import sqlite3

import pytest
from pathlib import Path

from src.api import (
    init_database, save_design, load_design, delete_design, list_designs,
    create_design, set_elmer_executable_path, set_working_directory,
)


def test_init_database_creates_file(tmp_path: Path):
    """TC-23 / TC-P01: Initialize Database — SQLite file created."""
    db_path = tmp_path / "test.db"
    init_database(str(db_path))
    assert db_path.exists()


def test_init_database_creates_designs_table(tmp_path: Path):
    """TC-P02: designs table exists after init."""
    db_path = tmp_path / "test.db"
    init_database(str(db_path))
    conn = sqlite3.connect(str(db_path))
    tables = [t[0] for t in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()]
    assert "designs" in tables
    conn.close()


def test_init_database_creates_settings_table(tmp_path: Path):
    """TC-P03: settings table exists after init."""
    db_path = tmp_path / "test.db"
    init_database(str(db_path))
    conn = sqlite3.connect(str(db_path))
    tables = [t[0] for t in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()]
    assert "settings" in tables
    conn.close()


def test_save_design_persists_json(tmp_path: Path):
    """TC-P04: save_design stores serialized JSON in the designs table."""
    db_path = tmp_path / "test.db"
    init_database(str(db_path))
    design = create_design(name="PersistTest")
    design_id = save_design(design)
    conn = sqlite3.connect(str(db_path))
    row = conn.execute(
        "SELECT data_json FROM designs WHERE id = ?", (design_id,)
    ).fetchone()
    assert row is not None
    data = json.loads(row[0])
    assert data["name"] == "PersistTest"
    conn.close()


def test_load_design_retrieves_all_fields(tmp_path: Path):
    """TC-P05: load_design restores all input and derived fields."""
    db_path = tmp_path / "test.db"
    init_database(str(db_path))
    design = create_design(name="LoadTest")
    design_id = save_design(design)
    loaded = load_design(design_id)
    assert loaded.name == design.name
    assert loaded.wire_diameter == design.wire_diameter
    assert loaded.total_vc_dcr == design.total_vc_dcr
    assert loaded.pole_height == design.pole_height


def test_delete_design_removes_record(tmp_path: Path):
    """TC-P06: delete_design removes the row from the database."""
    db_path = tmp_path / "test.db"
    init_database(str(db_path))
    design = create_design(name="DeleteTest")
    design_id = save_design(design)
    delete_design(design_id)
    conn = sqlite3.connect(str(db_path))
    row = conn.execute(
        "SELECT 1 FROM designs WHERE id = ?", (design_id,)
    ).fetchone()
    assert row is None
    conn.close()


def test_settings_persist_elmer_path(tmp_path: Path):
    """TC-P07: set_elmer_executable_path persists to settings table."""
    db_path = tmp_path / "test.db"
    init_database(str(db_path))
    path = r"C:\ElmerFEM\bin\ElmerSolver.exe"
    set_elmer_executable_path(path)
    conn = sqlite3.connect(str(db_path))
    row = conn.execute(
        "SELECT value FROM settings WHERE key = 'elmer_solver_path'"
    ).fetchone()
    assert row is not None
    assert row[0] == path
    conn.close()


def test_settings_persist_working_directory(tmp_path: Path):
    """TC-P08: set_working_directory persists to settings table."""
    db_path = tmp_path / "test.db"
    init_database(str(db_path))
    path = r"C:\ElmerFEA"
    set_working_directory(path)
    conn = sqlite3.connect(str(db_path))
    row = conn.execute(
        "SELECT value FROM settings WHERE key = 'working_directory'"
    ).fetchone()
    assert row is not None
    assert row[0] == path
    conn.close()
