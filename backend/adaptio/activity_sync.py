"""Match completed intervals.icu activities to planned workouts (roadmap т.3).

Deterministic and cheap: an activity pairs with a workout on the same calendar
day and the same sport; when several candidates exist, the one whose planned
duration is closest wins. The compact `actual` summary is stored on the workout
so the UI can show plan vs. reality and the weekly AI review can reason about
compliance without raw data dumps.
"""

from __future__ import annotations


def match_activities(workouts: list[dict], activities: list[dict]) -> list[tuple[dict, dict]]:
    """Return (workout, activity) pairs to persist.

    Workouts must already carry their computed `date`. Activities that were
    synced before (same activity_id) or have no same-day planned workout are
    skipped — an unplanned ride shouldn't tick off a rest day.
    """
    already_synced = {w["actual"]["activity_id"] for w in workouts if w.get("actual")}
    pairs: list[tuple[dict, dict]] = []
    taken: set[int] = set()

    for act in activities:
        if act["activity_id"] in already_synced:
            continue
        candidates = [
            w for w in workouts
            if w["id"] not in taken and not w.get("actual")
            and w["date"] == act["date"] and w["sport"] == act["sport"]
            and w["status"] in ("planned", "done")
        ]
        if not candidates:
            continue
        best = min(candidates, key=lambda w: abs(w["duration_min"] - act["moving_time_min"]))
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
