"""Match completed intervals.icu activities to planned workouts (roadmap т.3).

Deterministic and cheap: an activity pairs with a workout on the same calendar
day and the same sport; when several candidates exist, the one whose planned
duration is closest wins. The compact `actual` summary is stored on the workout
so the UI can show plan vs. reality and the weekly AI review can reason about
compliance without raw data dumps.
"""

from __future__ import annotations


def dedupe_activities(activities: list[dict]) -> list[dict]:
    """The same physical session can arrive from two sources (Garmin also
    feeds intervals.icu). Same day + sport + duration within 2 min = one."""
    seen: list[dict] = []
    out: list[dict] = []
    for act in activities:
        dup = any(s["date"] == act["date"] and s["sport"] == act["sport"]
                  and abs(s["moving_time_min"] - act["moving_time_min"]) <= 2
                  for s in seen)
        if not dup:
            seen.append(act)
            out.append(act)
    return out


def match_activities(workouts: list[dict], activities: list[dict],
                     day_tolerance: int = 1) -> list[tuple[dict, dict]]:
    """Return (workout, activity) pairs to persist.

    Workouts must already carry their computed `date`. Exact-date matches win;
    within `day_tolerance` days a same-sport planned workout still counts —
    life shifts sessions by a day all the time. Activities synced before (same
    activity_id, or the same session from another source) are skipped, and an
    unplanned ride never ticks off a rest day.
    """
    import datetime as dt

    stored = [w["actual"] for w in workouts if w.get("actual")]
    already_synced = {a["activity_id"] for a in stored}
    pairs: list[tuple[dict, dict]] = []
    taken: set[int] = set()

    def _days_apart(a: str, b: str) -> int:
        return abs((dt.date.fromisoformat(a) - dt.date.fromisoformat(b)).days)

    def _is_stored_dup(act: dict) -> bool:
        """Same session synced earlier from another source under another id."""
        return any(s["date"] == act["date"] and s["sport"] == act["sport"]
                   and abs((s.get("moving_time_min") or 0) - act["moving_time_min"]) <= 2
                   for s in stored)

    for act in activities:
        if act["activity_id"] in already_synced or _is_stored_dup(act):
            continue
        candidates = [
            w for w in workouts
            if w["id"] not in taken and not w.get("actual")
            and w["sport"] == act["sport"] and w["status"] in ("planned", "done")
            and _days_apart(w["date"], act["date"]) <= day_tolerance
        ]
        if not candidates:
            continue
        best = min(candidates, key=lambda w: (_days_apart(w["date"], act["date"]),
                                              abs(w["duration_min"] - act["moving_time_min"])))
        taken.add(best["id"])
        pairs.append((best, act))
    return pairs


def actuals_digest(workouts: list[dict], limit: int = 5) -> list[dict]:
    """Compact plan-vs-actual rows for the weekly AI review digest."""
    rows = []
    for w in workouts:
        act = w.get("actual")
        if not act:
            continue
        rows.append({
            "kind": w.get("kind"),
            "planned_min": w.get("duration_min"),
            "actual_min": act.get("moving_time_min"),
            "avg_hr": act.get("avg_hr"),
            "load": act.get("load"),
        })
    return rows[-limit:]
