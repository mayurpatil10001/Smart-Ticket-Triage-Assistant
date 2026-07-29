"""
database.py — SQLite persistence layer for Smart Ticket Triage Assistant.

Schema
------
tickets
    id          TEXT PRIMARY KEY  (UUID)
    text        TEXT              (raw ticket text)
    intent      TEXT              (classified intent)
    confidence  REAL              (LLM confidence 0–1)
    entities    TEXT              (JSON-encoded entity dict)
    response    TEXT              (auto-generated reply or NULL)
    status      TEXT              (open | needs_human_review | resolved)
    created_at  TEXT              (ISO-8601 UTC timestamp)
"""

import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path(__file__).parent / "tickets.db"


def init_db() -> None:
    """Create tables if they don't exist. Called once at startup."""
    with _get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tickets (
                id          TEXT PRIMARY KEY,
                text        TEXT NOT NULL,
                intent      TEXT NOT NULL,
                confidence  REAL NOT NULL,
                entities    TEXT NOT NULL DEFAULT '{}',
                response    TEXT,
                status      TEXT NOT NULL DEFAULT 'open',
                created_at  TEXT NOT NULL
            )
            """
        )
        conn.commit()


@contextmanager
def _get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def insert_ticket(
    *,
    id: str,
    text: str,
    intent: str,
    confidence: float,
    entities: dict,
    response: str | None,
    status: str,
    created_at: str,
) -> None:
    with _get_conn() as conn:
        conn.execute(
            """
            INSERT INTO tickets
                (id, text, intent, confidence, entities, response, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                id,
                text,
                intent,
                confidence,
                json.dumps(entities),
                response,
                status,
                created_at,
            ),
        )
        conn.commit()


def get_escalated_tickets() -> list[dict]:
    """Return all tickets with status 'needs_human_review'."""
    with _get_conn() as conn:
        rows = conn.execute(
            """
            SELECT id, text, intent, confidence, entities, response, status, created_at
            FROM   tickets
            WHERE  status = 'needs_human_review'
            ORDER  BY created_at DESC
            """
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def get_all_tickets() -> list[dict]:
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM tickets ORDER BY created_at DESC"
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def _row_to_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    d["entities"] = json.loads(d.get("entities") or "{}")
    return d
