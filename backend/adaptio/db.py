"""SQLite persistence. Multi-user: every query is scoped by user_id."""

from __future__ import annotations

import datetime as dt
import json
import os
import sqlite3
from contextlib import contextmanager

DB_PATH = os.getenv("ADAPTIO_DB_PATH", "adaptio.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    username TEXT UNIQUE NOT NULL COLLATE NOCASE,
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
    token TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL
);
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


# -------------------------------------------------------------------- users

def create_user(user_id: str, username: str, password_hash: str) -> None:
    with conn() as c:
        c.execute("INSERT INTO users(id, username, password_hash, created_at) VALUES(?,?,?,?)",
                  (user_id, username, password_hash, dt.datetime.now().isoformat()))


def user_by_username(username: str) -> dict | None:
    with conn() as c:
        row = c.execute("SELECT id, username, password_hash FROM users WHERE username=?",
                        (username,)).fetchone()
    return dict(row) if row else None


def create_session(token: str, user_id: str) -> None:
    with conn() as c:
        c.execute("INSERT INTO sessions(token, user_id, created_at) VALUES(?,?,?)",
                  (token, user_id, dt.datetime.now().isoformat()))


def user_for_token(token: str) -> str | None:
    with conn() as c:
        row = c.execute("SELECT user_id FROM sessions WHERE token=?", (token,)).fetchone()
    return row["user_id"] if row else None


def delete_session(token: str) -> None:
    with conn() as c:
        c.execute("DELETE FROM sessions WHERE token=?", (token,))


# ------------------------------------------------------------------ profile

def save_profile(user_id: str, profile: dict) -> None:
    with conn() as c:
        c.execute(
            "INSERT INTO profiles(user_id, data, updated_at) VALUES(?,?,?) "
            "ON CONFLICT(user_id) DO UPDATE SET data=excluded.data, updated_at=excluded.updated_at",
            (user_id, json.dumps(profile), dt.datetime.now().isoformat()),
        )


def load_profile(user_id: str) -> dict | None:
    with conn() as c:
        row = c.execute("SELECT data FROM profiles WHERE user_id=?", (user_id,)).fetchone()
    return json.loads(row["data"]) if row else None


# -------------------------------------------------------------------- plans

def save_plan(user_id: str, meta: dict, workouts: list[dict]) -> int:
    with conn() as c:
        c.execute("UPDATE plans SET active=0 WHERE user_id=?", (user_id,))
        cur = c.execute(
            "INSERT INTO plans(user_id, meta, created_at, active) VALUES(?,?,?,1)",
            (user_id, json.dumps(meta), dt.datetime.now().isoformat()),
        )
        plan_id = cur.lastrowid
        for wo in workouts:
            c.execute("INSERT INTO workouts(plan_id, data, status) VALUES(?,?,?)",
                      (plan_id, json.dumps(wo), wo.get("status", "planned")))
    return plan_id


def update_plan_meta(plan_id: int, meta: dict) -> None:
    clean = {k: v for k, v in meta.items() if k != "created_at"}
    with conn() as c:
        c.execute("UPDATE plans SET meta=? WHERE id=?", (json.dumps(clean), plan_id))


def active_plan(user_id: str) -> tuple[int, dict, list[dict]] | None:
    with conn() as c:
        row = c.execute(
            "SELECT id, meta, created_at FROM plans WHERE user_id=? AND active=1 "
            "ORDER BY id DESC LIMIT 1", (user_id,)).fetchone()
        if not row:
            return None
        wos = c.execute(
            "SELECT id, data, status, "
            "EXISTS(SELECT 1 FROM ratings r WHERE r.workout_id = workouts.id) AS rated "
            "FROM workouts WHERE plan_id=? ORDER BY id", (row["id"],)).fetchall()
    meta = json.loads(row["meta"])
    meta["created_at"] = row["created_at"]
    workouts = []
    for w in wos:
        d = json.loads(w["data"])
        d["id"], d["status"], d["rated"] = w["id"], w["status"], bool(w["rated"])
        workouts.append(d)
    return row["id"], meta, workouts


def get_workout(user_id: str, workout_id: int) -> dict | None:
    """Workout by id, only if it belongs to a plan of this user. Includes the
    plan's created_at so callers can compute the workout's calendar date."""
    with conn() as c:
        row = c.execute(
            "SELECT w.id, w.data, w.status, p.created_at AS plan_created "
            "FROM workouts w JOIN plans p ON p.id = w.plan_id "
            "WHERE w.id=? AND p.user_id=?", (workout_id, user_id)).fetchone()
    if not row:
        return None
    d = json.loads(row["data"])
    d["id"], d["status"] = row["id"], row["status"]
    d["plan_created"] = row["plan_created"]
    return d


def update_workout(workout_id: int, data: dict | None = None, status: str | None = None) -> None:
    with conn() as c:
        if data is not None:
            # strip keys that are stored elsewhere or recomputed on every read
            clean = {k: v for k, v in data.items()
                     if k not in ("status", "plan_created", "rated")}
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


# ------------------------------------------------------------- integrations

def save_integration(user_id: str, provider: str, data: dict) -> None:
    with conn() as c:
        c.execute(
            "INSERT INTO integrations(user_id, provider, data) VALUES(?,?,?) "
            "ON CONFLICT(user_id, provider) DO UPDATE SET data=excluded.data",
            (user_id, provider, json.dumps(data)),
        )


def load_integration(user_id: str, provider: str) -> dict | None:
    with conn() as c:
        row = c.execute("SELECT data FROM integrations WHERE user_id=? AND provider=?",
                        (user_id, provider)).fetchone()
    return json.loads(row["data"]) if row else None
