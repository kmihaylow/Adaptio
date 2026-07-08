"""intervals.icu client — the bridge to Garmin (изисквания т.10–11).

Garmin devices sync to intervals.icu automatically; workouts pushed to the
intervals.icu calendar sync back to Garmin Connect and appear on the watch /
head unit. Until the Garmin Developer Program reopens, this is the integration
path. Auth: HTTP Basic with the literal username "API_KEY".
"""

from __future__ import annotations

import datetime as dt

import requests

BASE = "https://intervals.icu/api/v1"


class IntervalsClient:
    def __init__(self, api_key: str, athlete_id: str):
        self.auth = ("API_KEY", api_key)
        self.athlete_id = athlete_id

    def _get(self, path: str, params: dict | None = None):
        r = requests.get(f"{BASE}{path}", params=params or {}, auth=self.auth, timeout=30)
        r.raise_for_status()
        return r.json()

    def _post(self, path: str, payload: dict):
        r = requests.post(f"{BASE}{path}", json=payload, auth=self.auth, timeout=30)
        r.raise_for_status()
        return r.json()

    def check(self) -> dict:
        """Cheap connectivity check; returns basic athlete info."""
        a = self._get(f"/athlete/{self.athlete_id}")
        return {"id": a.get("id"), "name": a.get("name")}

    # ------------------------------------------------------------- wellness

    def wellness_digest(self, days: int = 7) -> list[dict]:
        today = dt.date.today()
        oldest = (today - dt.timedelta(days=days)).isoformat()
        rows = self._get(f"/athlete/{self.athlete_id}/wellness",
                         {"oldest": oldest, "newest": today.isoformat()})
        out = []
        for w in rows:
            ctl, atl = w.get("ctl"), w.get("atl")
            out.append({
                "date": w.get("id"),
                "sleep_h": round((w.get("sleepSecs") or 0) / 3600, 1)
                if w.get("sleepSecs") else w.get("sleepHours"),
                "resting_hr": w.get("restingHR"),
                "hrv": w.get("hrv"),
                "form_tsb": round(ctl - atl, 1) if ctl is not None and atl is not None else None,
            })
        return out

    # -------------------------------------------- completed activities (т.3)

    def activities(self, days: int = 14) -> list[dict]:
        """Completed activities from the last `days`, as compact summaries.

        Garmin uploads land here automatically, so pulling this list is the
        zero-friction way to know what the athlete actually did."""
        today = dt.date.today()
        rows = self._get(f"/athlete/{self.athlete_id}/activities", {
            "oldest": (today - dt.timedelta(days=days)).isoformat(),
            "newest": (today + dt.timedelta(days=1)).isoformat(),
        })
        out = []
        for a in rows:
            kind = a.get("type") or ""
            sport = "run" if "Run" in kind else "bike" if "Ride" in kind else None
            if not sport:
                continue
            speed = a.get("average_speed")
            out.append({
                "activity_id": str(a.get("id")),
                "date": (a.get("start_date_local") or "")[:10],
                "sport": sport,
                "name": a.get("name"),
                "moving_time_min": round((a.get("moving_time") or 0) / 60),
                "distance_km": round(a["distance"] / 1000, 2) if a.get("distance") else None,
                "avg_hr": a.get("average_heartrate"),
                "avg_watts": a.get("icu_average_watts") or a.get("average_watts"),
                "pace_s_per_km": round(1000 / speed) if sport == "run" and speed else None,
                "load": a.get("icu_training_load"),
            })
        return out

    # ------------------------------------------------- push workouts (т.11)

    def push_workout(self, date: dt.date, name: str, sport: str,
                     description: str, duration_min: int) -> dict:
        """Create a planned workout on the intervals.icu calendar.

        intervals.icu parses the structured-workout text in `description`
        (its native workout builder syntax) and syncs it onward to Garmin.
        """
        payload = {
            "category": "WORKOUT",
            "start_date_local": f"{date.isoformat()}T00:00:00",
            "type": "Run" if sport == "run" else "Ride",
            "name": name,
            "description": description,
            "moving_time": duration_min * 60,
        }
        return self._post(f"/athlete/{self.athlete_id}/events", payload)


def workout_to_intervals_text(workout: dict, ftp_w: int | None) -> str:
    """Render our segments as intervals.icu workout-builder text."""
    lines = []
    for s in workout.get("segments", []):
        mins = max(1, round(s["duration_s"] / 60))
        kind = s["target_kind"]
        if kind == "power":
            lo, hi = round(s["low"] * 100), round(s["high"] * 100)
            tgt = f"{lo}-{hi}% FTP" if lo != hi else f"{lo}% FTP"
        elif kind == "hr":
            tgt = f"{round(s['low'])}-{round(s['high'])}bpm"
        elif kind == "pace":
            def p(sec):
                return f"{int(sec) // 60}:{int(sec) % 60:02d}"
            tgt = f"{p(s['high'])}-{p(s['low'])}/km pace"
        else:
            tgt = f"RPE {round(s['low'])}-{round(s['high'])}"
        label = {"warmup": "Warmup", "cooldown": "Cooldown"}.get(s["type"], "-")
        lines.append(f"{label} {mins}m {tgt}".replace("- ", "- ", 1))
    return "\n".join(lines)
