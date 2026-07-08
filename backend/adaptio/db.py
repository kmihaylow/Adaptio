"""SQLite persistence. Single-user for now; every table already carries user_id
so the Supabase/multi-user migration is a data move, not a rewrite."""

from __future__ import annotations

import datetime as dt
import json
import os
import sqlite3
from contextlib import contextmanager

DB_PATH = os.getenv("ADAPTIO_DB_PATH", "adaptio.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS profiles (
    user_id TEXT PRIMARY KEY,
    data TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS plans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    meta TEXT NOT NULL,          -- weeks, warnings, zones, sport
    created_at TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS workouts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    plan_id INTEGER NOT NULL REFERENCES plans(id),
    data TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'planned'
);
CREATE TABLE IF NOT EXISTS ratings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workout_id INTEGER NOT NULL REFERENCES workouts(id),
    data TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS integrations (
    user_id TEXT NOT NULL,
    provider TEXT NOT NULL,
    data TEXT NOT NULL,
    PRIMARY KEY (user_id, provider)
);
"""

USER = "local"  # single local user until multi-user lands


@contextmanager
def conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    try:
        yield c
        c.commit()
    finally:
        c.close()


def init() -> None:
    with conn() as c:
        c.executescript(SCHEMA)


def save_profile(profile: dict) -> None:
    with conn() as c:
        c.execute(
            "INSERT INTO profiles(user_id, data, updated_at) VALUES(?,?,?) "
            "ON CONFLICT(user_id) DO UPDATE SET data=excluded.data, updated_at=excluded.updated_at",
            (USER, json.dumps(profile), dt.datetime.now().isoformat()),
        )


def load_profile() -> dict | None:
    with conn() as c:
        row = c.execute("SELECT data FROM profiles WHERE user_id=?", (USER,)).fetchone()
    return json.loads(row["data"]) if row else None


def save_plan(meta: dict, workouts: list[dict]) -> int:
    with conn() as c:
        c.execute("UPDATE plans SET active=0 WHERE user_id=?", (USER,))
        cur = c.execute(
            "INSERT INTO plans(user_id, meta, created_at, active) VALUES(?,?,?,1)",
            (USER, json.dumps(meta), dt.datetime.now().isoformat()),
        )
        plan_id = cur.lastrowid
        for wo in workouts:
            c.execute("INSERT INTO workouts(plan_id, data, status) VALUES(?,?,?)",
                      (plan_id, json.dumps(wo), wo.get("status", "planned")))
    return plan_id


def active_plan() -> tuple[int, dict, list[dict]] | None:
    with conn() as c:
        row = c.execute(
            "SELECT id, meta, created_at FROM plans WHERE user_id=? AND active=1 "
            "ORDER BY id DESC LIMIT 1", (USER,)).fetchone()
        if not row:
            return None
        wos = c.execute("SELECT id, data, status FROM workouts WHERE plan_id=? ORDER BY id",
                        (row["id"],)).fetchall()
    meta = json.loads(row["meta"])
    meta["created_at"] = row["created_at"]
    workouts = []
    for w in wos:
        d = json.loads(w["data"])
        d["id"], d["status"] = w["id"], w["status"]
        workouts.append(d)
    return row["id"], meta, workouts


def get_workout(workout_id: int) -> dict | None:
    with conn() as c:
        row = c.execute("SELECT id, data, status FROM workouts WHERE id=?",
                        (workout_id,)).fetchone()
    if not row:
        return None
    d = json.loads(row["data"])
    d["id"], d["status"] = row["id"], row["status"]
    return d


def update_workout(workout_id: int, data: dict | None = None, status: str | None = None) -> None:
    with conn() as c:
        if data is not None:
            clean = {k: v for k, v in data.items() if k != "status"}
            c.execute("UPDATE workouts SET data=? WHERE id=?", (json.dumps(clean), workout_id))
        if status is not None:
            c.execute("UPDATE workouts SET status=? WHERE id=?", (status, workout_id))


def save_rating(workout_id: int, rating: dict) -> None:
    with conn() as c:
        c.execute("INSERT INTO ratings(workout_id, data, created_at) VALUES(?,?,?)",
                  (workout_id, json.dumps(rating), dt.datetime.now().isoformat()))


def recent_ratings(plan_id: int, limit: int = 10) -> list[dict]:
    """Newest-last rating digest joined with the workout kind."""
    with conn() as c:
        rows = c.execute(
            "SELECT r.data AS rating, w.data AS workout FROM ratings r "
            "JOIN workouts w ON w.id = r.workout_id WHERE w.plan_id=? "
            "ORDER BY r.id DESC LIMIT ?", (plan_id, limit)).fetchall()
    out = []
    for row in reversed(rows):
        r, w = json.loads(row["rating"]), json.loads(row["workout"])
        out.append({"kind": w.get("kind"), "name": w.get("name"),
                    "rpe": r.get("rpe"), "feel": r.get("feel"), "comment": r.get("comment")})
    return out


def save_integration(provider: str, data: dict) -> None:
    with conn() as c:
        c.execute(
            "INSERT INTO integrations(user_id, provider, data) VALUES(?,?,?) "
            "ON CONFLICT(user_id, provider) DO UPDATE SET data=excluded.data",
            (USER, provider, json.dumps(data)),
        )


def load_integration(provider: str) -> dict | None:
    with conn() as c:
        row = c.execute("SELECT data FROM integrations WHERE user_id=? AND provider=?",
                        (USER, provider)).fetchone()
    return json.loads(row["data"]) if row else None
