"""Adaptio HTTP API (FastAPI). Run with: uvicorn adaptio.api:app --reload"""

from __future__ import annotations

import datetime as dt

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from . import adaptation, coach, db, zwo
from .intervals import IntervalsClient, workout_to_intervals_text
from .models import Profile, WorkoutRating
from .plan_bike import generate_plan
from .planning import plan_length_weeks

app = FastAPI(title="Adaptio", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten when a real domain exists
    allow_methods=["*"],
    allow_headers=["*"],
)
db.init()


def _workout_date(plan_created: str, plan_week: int, day_of_week: int) -> dt.date:
    start = dt.datetime.fromisoformat(plan_created).date()
    # week 1 is the rolling week that starts on plan creation day
    offset = (day_of_week - start.weekday()) % 7
    return start + dt.timedelta(days=(plan_week - 1) * 7 + offset)


def _with_dates(meta: dict, workouts: list[dict]) -> list[dict]:
    for wo in workouts:
        wo["date"] = _workout_date(meta["created_at"], wo["plan_week"], wo["day_of_week"]).isoformat()
    return workouts


# ------------------------------------------------------------------ profile

@app.get("/api/health")
def health():
    return {"ok": True}


@app.post("/api/profile")
def save_profile(profile: Profile):
    db.save_profile(profile.model_dump(mode="json"))
    weeks, warnings = plan_length_weeks(profile.goal)
    return {"saved": True, "plan_weeks": weeks, "warnings": warnings}


@app.get("/api/profile")
def get_profile():
    p = db.load_profile()
    if not p:
        raise HTTPException(404, "Няма профил — мини през onboarding-а.")
    return p


# --------------------------------------------------------------------- plan

@app.post("/api/plan/generate")
def generate():
    p = db.load_profile()
    if not p:
        raise HTTPException(404, "Първо попълни профила си.")
    profile = Profile.model_validate(p)
    plan = generate_plan(profile)
    meta = {
        "sport": plan.sport.value,
        "weeks": [w.model_dump() for w in plan.weeks],
        "warnings": plan.warnings,
        "zones": plan.zones,
    }
    plan_id = db.save_plan(meta, [w.model_dump(mode="json") for w in plan.workouts])
    return {"plan_id": plan_id, "weeks": len(plan.weeks), "warnings": plan.warnings}


@app.get("/api/plan")
def get_plan():
    row = db.active_plan()
    if not row:
        raise HTTPException(404, "Няма активен план — генерирай от профила.")
    plan_id, meta, workouts = row
    return {"plan_id": plan_id, **meta, "workouts": _with_dates(meta, workouts)}


# ----------------------------------------------------------------- workouts

@app.get("/api/workouts/today")
def today():
    row = db.active_plan()
    if not row:
        raise HTTPException(404, "Няма активен план.")
    _, meta, workouts = row
    today_iso = dt.date.today().isoformat()
    todays = [w for w in _with_dates(meta, workouts) if w["date"] == today_iso]
    upcoming = sorted((w for w in workouts if w["date"] > today_iso and w["status"] == "planned"),
                      key=lambda w: w["date"])[:3]
    return {"today": todays, "upcoming": upcoming, "zones": meta.get("zones", {})}


class StatusUpdate(BaseModel):
    status: str  # done | skipped | planned


@app.post("/api/workouts/{workout_id}/status")
def set_status(workout_id: int, body: StatusUpdate):
    if body.status not in ("done", "skipped", "planned"):
        raise HTTPException(400, "Невалиден статус.")
    if not db.get_workout(workout_id):
        raise HTTPException(404, "Няма такава тренировка.")
    db.update_workout(workout_id, status=body.status)
    return {"ok": True}


@app.post("/api/workouts/{workout_id}/rating")
def rate(workout_id: int, rating: WorkoutRating):
    wo = db.get_workout(workout_id)
    if not wo:
        raise HTTPException(404, "Няма такава тренировка.")
    db.save_rating(workout_id, rating.model_dump())
    db.update_workout(workout_id, status="done")

    row = db.active_plan()
    message, adjusted = None, 0
    if row:
        plan_id, meta, workouts = row
        recent = db.recent_ratings(plan_id)
        factor, message = adaptation.evaluate_ratings(recent)
        if factor:
            from .models import Workout
            models = [Workout.model_validate(w) for w in workouts]
            horizon = wo["plan_week"] + 2
            targets = [m for m in models if wo["plan_week"] <= m.plan_week <= horizon]
            adjusted = adaptation.apply_adjustment(targets, factor)
            for m in targets:
                db.update_workout(m.id, data=m.model_dump(mode="json"))
    return {"ok": True, "coach_message": message, "adjusted_workouts": adjusted}


@app.get("/api/workouts/{workout_id}/zwo", response_class=PlainTextResponse)
def workout_zwo(workout_id: int):
    wo = db.get_workout(workout_id)
    if not wo:
        raise HTTPException(404, "Няма такава тренировка.")
    if not zwo.is_zwo_exportable(wo):
        raise HTTPException(400, "Тази тренировка няма мощностни цели за .zwo експорт.")
    return zwo.to_zwo(wo)


# ------------------------------------------------------------- intervals.icu

class IntervalsCreds(BaseModel):
    api_key: str
    athlete_id: str


@app.post("/api/integrations/intervals")
def connect_intervals(creds: IntervalsCreds):
    client = IntervalsClient(creds.api_key, creds.athlete_id)
    try:
        info = client.check()
    except Exception:
        raise HTTPException(400, "Неуспешна връзка с intervals.icu — провери ключа и athlete ID.")
    db.save_integration("intervals", creds.model_dump())
    return {"connected": True, "athlete": info}


@app.get("/api/integrations/intervals")
def intervals_status():
    return {"connected": db.load_integration("intervals") is not None}


def _intervals_client() -> IntervalsClient:
    creds = db.load_integration("intervals")
    if not creds:
        raise HTTPException(400, "intervals.icu не е свързан.")
    return IntervalsClient(creds["api_key"], creds["athlete_id"])


@app.post("/api/integrations/intervals/push-week/{week}")
def push_week(week: int):
    row = db.active_plan()
    if not row:
        raise HTTPException(404, "Няма активен план.")
    _, meta, workouts = row
    client = _intervals_client()
    ftp = meta.get("zones", {}).get("ftp_w")
    pushed = 0
    for wo in _with_dates(meta, workouts):
        if wo["plan_week"] != week or wo["status"] != "planned":
            continue
        client.push_workout(
            dt.date.fromisoformat(wo["date"]), wo["name"], wo["sport"],
            workout_to_intervals_text(wo, ftp), wo["duration_min"],
        )
        pushed += 1
    return {"pushed": pushed}


# ----------------------------------------------------------------- AI coach

class ReviewRequest(BaseModel):
    note: str = ""


@app.post("/api/coach/review")
def weekly_review(body: ReviewRequest):
    p = db.load_profile()
    row = db.active_plan()
    if not p or not row:
        raise HTTPException(404, "Нужни са профил и активен план.")
    plan_id, meta, workouts = row
    ratings = db.recent_ratings(plan_id)
    if not ratings:
        raise HTTPException(400, "Още няма оценени тренировки за преглед.")

    digest = {
        "sport": p["sport"], "age": p["age"], "weekly_hours": p["weekly_hours"],
        "goal": p.get("goal", {}),
        "zones": {k: v for k, v in meta.get("zones", {}).items()
                  if k in ("vdot", "ftp_w", "max_hr_bpm")},
    }
    wellness = None
    creds = db.load_integration("intervals")
    if creds:
        try:
            wellness = IntervalsClient(creds["api_key"], creds["athlete_id"]).wellness_digest()
        except Exception:
            wellness = None

    try:
        review = coach.weekly_review(digest, ratings, wellness, body.note)
    except RuntimeError as e:
        raise HTTPException(400, str(e))

    factor = review.get("intensity_factor", 1.0)
    adjusted = 0
    if factor and abs(factor - 1.0) >= 0.01:
        factor = max(0.9, min(1.05, factor))
        from .models import Workout
        models = [Workout.model_validate(w) for w in workouts if w["status"] == "planned"]
        adjusted = adaptation.apply_adjustment(models, factor)
        for m in models:
            db.update_workout(m.id, data=m.model_dump(mode="json"))
    return {**review, "adjusted_workouts": adjusted}
