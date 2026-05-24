"""SQLite persistence layer for LoudspeakerFEA."""

from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Optional

from src.models import LoudspeakerDesign

_DEFAULT_DB_DIR = Path(os.path.expanduser("~/AppData/Local/LoudspeakerFEA"))
_DEFAULT_DB_PATH = _DEFAULT_DB_DIR / "loudspeakerfea.db"

_db_path: Path = _DEFAULT_DB_PATH


def _get_connection() -> sqlite3.Connection:
    """Return a connection to the current database."""
    global _db_path
    _db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_db_path))
    conn.row_factory = sqlite3.Row
    return conn


def init_database(db_path: Optional[str] = None) -> None:
    """Create the SQLite database and tables if they do not exist."""
    global _db_path
    if db_path is not None:
        _db_path = Path(db_path)
    _db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = _get_connection()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS designs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL DEFAULT '',
                data_json TEXT NOT NULL,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def save_design(design: LoudspeakerDesign) -> int:
    """Serialize design to JSON and store in SQLite. Returns the design ID."""
    conn = _get_connection()
    try:
        data = design.to_dict()
        # Remove 'id' from serialized data so DB owns the primary key
        data.pop("id", None)
        data_json = json.dumps(data)

        try:
            if design.id is not None:
                conn.execute(
                    """
                    UPDATE designs
                    SET name = ?, data_json = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (design.name, data_json, design.id),
                )
                conn.commit()
                return design.id
            else:
                cursor = conn.execute(
                    """
                    INSERT INTO designs (name, data_json)
                    VALUES (?, ?)
                    """,
                    (design.name, data_json),
                )
                conn.commit()
                return cursor.lastrowid
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error saving design: {e}") from e
    finally:
        conn.close()


def load_design(design_id: int) -> LoudspeakerDesign:
    """Retrieve a design from SQLite by ID."""
    conn = _get_connection()
    try:
        try:
            row = conn.execute(
                "SELECT * FROM designs WHERE id = ?", (design_id,)
            ).fetchone()
            if row is None:
                raise ValueError(f"Design with id {design_id} not found")
            data = json.loads(row["data_json"])
            data["id"] = row["id"]
            return LoudspeakerDesign.from_dict(data)
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error loading design: {e}") from e
    finally:
        conn.close()


def list_designs() -> list[dict]:
    """Return a list of all saved designs as dicts with keys id, name, updated_at."""
    conn = _get_connection()
    try:
        try:
            rows = conn.execute(
                "SELECT id, name, updated_at FROM designs ORDER BY updated_at DESC"
            ).fetchall()
            return [dict(r) for r in rows]
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error listing designs: {e}") from e
    finally:
        conn.close()


def delete_design(design_id: int) -> None:
    """Delete the design from SQLite. Raises ValueError if ID not found."""
    conn = _get_connection()
    try:
        try:
            cursor = conn.execute("DELETE FROM designs WHERE id = ?", (design_id,))
            conn.commit()
            if cursor.rowcount == 0:
                raise ValueError(f"Design with id {design_id} not found")
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error deleting design: {e}") from e
    finally:
        conn.close()


def set_setting(key: str, value: str) -> None:
    """Persist a global setting to the settings table."""
    conn = _get_connection()
    try:
        try:
            conn.execute(
                """
                INSERT INTO settings (key, value)
                VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (key, value),
            )
            conn.commit()
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error setting {key}: {e}") from e
    finally:
        conn.close()


def get_setting(key: str, default: str = "") -> str:
    """Retrieve a global setting from the settings table."""
    conn = _get_connection()
    try:
        try:
            row = conn.execute(
                "SELECT value FROM settings WHERE key = ?", (key,)
            ).fetchone()
            return row["value"] if row is not None else default
        except sqlite3.OperationalError:
            # Table may not exist yet (init_database not called)
            return default
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error getting {key}: {e}") from e
    finally:
        conn.close()
