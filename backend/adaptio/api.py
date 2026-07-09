"""Adaptio HTTP API (FastAPI). Run with: uvicorn adaptio.api:app --reload"""

from __future__ import annotations

import datetime as dt
from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from . import activity_sync, adaptation, auth, coach, db, zwo
from .auth import current_user
from .intervals import IntervalsClient, workout_to_intervals_text
from .models import Profile, WorkoutRating
from .plan_bike import generate_plan
from .planning import plan_length_weeks
from .zones import resolve_zones

app = FastAPI(title="Adaptio", version="0.3.0")
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


def _require_workout_day_passed(wo: dict) -> None:
    """Completion (done + rating) is only allowed on/after the workout's day."""
    date = _workout_date(wo["plan_created"], wo["plan_week"], wo["day_of_week"])
    if date > dt.date.today():
        raise HTTPException(
            400,
            f"Тази тренировка е планирана за {date.strftime('%d.%m')} — "
            "ще можеш да я отбележиш, когато дойде денят ѝ.",
        )


# --------------------------------------------------------------------- auth

class Credentials(BaseModel):
    username: str = Field(..., min_length=3, max_length=40)
    password: str = Field(..., min_length=6, max_length=200)


@app.post("/api/auth/register")
def register(creds: Credentials):
    if db.user_by_username(creds.username):
        raise HTTPException(409, "Това потребителско име е заето.")
    user_id = auth.new_user_id()
    db.create_user(user_id, creds.username, auth.hash_password(creds.password))
    token = auth.new_token()
    db.create_session(token, user_id)
    return {"token": token, "username": creds.username}


@app.post("/api/auth/login")
def login(creds: Credentials):
    user = db.user_by_username(creds.username)
    if not user or not auth.verify_password(creds.password, user["password_hash"]):
        raise HTTPException(401, "Грешно потребителско име или парола.")
    token = auth.new_token()
    db.create_session(token, user["id"])
    return {"token": token, "username": user["username"]}


@app.post("/api/auth/logout")
def logout(authorization: Optional[str] = Header(None)):
    if authorization and authorization.startswith("Bearer "):
        db.delete_session(authorization[7:])
    return {"ok": True}


@app.get("/api/auth/me")
def me(user: str = Depends(current_user)):
    return {"user_id": user}


# ------------------------------------------------------------------ profile

@app.get("/api/health")
def health():
    return {"ok": True}


@app.post("/api/profile")
def save_profile(profile: Profile, user: str = Depends(current_user)):
    db.save_profile(user, profile.model_dump(mode="json"))
    weeks, warnings = plan_length_weeks(profile.goal)
    return {"saved": True, "plan_weeks": weeks, "warnings": warnings}


@app.get("/api/profile")
def get_profile(user: str = Depends(current_user)):
    p = db.load_profile(user)
    if not p:
        raise HTTPException(404, "Няма профил — мини през onboarding-а.")
    return p


class MetricsUpdate(BaseModel):
    """Physiology numbers the athlete may re-measure at any time."""
    max_hr_bpm: Optional[int] = Field(None, ge=120, le=230)
    resting_hr_bpm: Optional[int] = Field(None, ge=25, le=110)
    vo2max: Optional[float] = Field(None, ge=15, le=95)
    ftp_w: Optional[int] = Field(None, ge=50, le=600)
    lthr_bpm: Optional[int] = Field(None, ge=100, le=220)
    weight_kg: Optional[float] = Field(None, ge=30, le=250)
    height_cm: Optional[float] = Field(None, ge=100, le=250)


@app.post("/api/profile/metrics")
def update_metrics(body: MetricsUpdate, user: str = Depends(current_user)):
    p = db.load_profile(user)
    if not p:
        raise HTTPException(404, "Няма профил — мини през onboarding-а.")
    changed = {k: v for k, v in body.model_dump().items() if v is not None}
    if not changed:
        raise HTTPException(400, "Няма подадени стойности.")
    p.update(changed)
    profile = Profile.model_validate(p)
    db.save_profile(user, profile.model_dump(mode="json"))

    # Refresh the zones snapshot on the active plan so watt/HR targets update
    # immediately. Pace-based segments keep their old values until the plan is
    # regenerated (they are baked into each workout).
    zones = resolve_zones(profile)
    row = db.active_plan(user)
    if row:
        plan_id, meta, _ = row
        meta["zones"] = zones
        db.update_plan_meta(plan_id, meta)
    return {"saved": True, "zones": zones}


# --------------------------------------------------------------------- plan

@app.post("/api/plan/generate")
def generate(user: str = Depends(current_user)):
    p = db.load_profile(user)
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
    plan_id = db.save_plan(user, meta, [w.model_dump(mode="json") for w in plan.workouts])
    return {"plan_id": plan_id, "weeks": len(plan.weeks), "warnings": plan.warnings}


@app.get("/api/plan")
def get_plan(user: str = Depends(current_user)):
    row = db.active_plan(user)
    if not row:
        raise HTTPException(404, "Няма активен план — генерирай от профила.")
    plan_id, meta, workouts = row
    return {"plan_id": plan_id, **meta, "workouts": _with_dates(meta, workouts)}


# ---------------------------------------------------------------- dashboard

@app.get("/api/dashboard")
def dashboard(user: str = Depends(current_user)):
    row = db.active_plan(user)
    if not row:
        raise HTTPException(404, "Няма активен план.")
    plan_id, meta, workouts = row
    workouts = _with_dates(meta, workouts)
    today = dt.date.today().isoformat()

    done = [w for w in workouts if w["status"] == "done"]
    skipped = [w for w in workouts if w["status"] == "skipped"]
    past_planned = [w for w in workouts if w["status"] == "planned" and w["date"] < today]

    cur = next((w for w in sorted(workouts, key=lambda w: w["date"]) if w["date"] >= today), None)
    current_week = cur["plan_week"] if cur else len(meta["weeks"])
    phase = next((wk["phase"] for wk in meta["weeks"] if wk["number"] == current_week), "base")

    weekly = []
    for wk in meta["weeks"]:
        wos = [w for w in workouts if w["plan_week"] == wk["number"]]
        weekly.append({
            "week": wk["number"], "phase": wk["phase"],
            "planned": len(wos),
            "done": sum(1 for w in wos if w["status"] == "done"),
            "load_done": sum(w.get("load_hint", 0) for w in wos if w["status"] == "done"),
            "load_planned": sum(w.get("load_hint", 0) for w in wos),
        })

    ratings = db.recent_ratings(plan_id)
    rpes = [r["rpe"] for r in ratings if r.get("rpe")]
    avg_rpe = round(sum(rpes) / len(rpes), 1) if rpes else None

    # Deterministic focus advice: phase first, then behaviour corrections.
    phase_focus = {
        "base": "Гради аеробната база: карай/бягай леко и дълго, не гони темпо. Постоянството сега определя колко ще поемеш после.",
        "build": "Качествените тренировки са приоритет — интервалите и темпо-сесиите носят прогреса. Пази леките дни наистина леки.",
        "peak": "Специфична работа: тренирай в целевото състезателно темпо/мощност. Възстановяването е също толкова важно.",
        "recovery": "Възстановителна седмица — по-малкото е повече. Сън, храна, леки движения.",
        "taper": "Тейпър: сваляй обема, пази малко интензивност. Пристигни на старта свеж, не префорсиран.",
    }
    focus = [phase_focus.get(phase, phase_focus["base"])]
    attempted = len(done) + len(skipped) + len(past_planned)
    if attempted >= 4:
        compliance = len(done) / attempted
        if compliance < 0.6:
            focus.append("Изпълнението е под 60% — по-добре по-кратки, но редовни тренировки. Помисли дали седмичният обем не е твърде амбициозен.")
    if avg_rpe is not None and len(rpes) >= 3:
        if avg_rpe >= 8.5:
            focus.append("Средното усещане е много тежко (RPE ≥ 8.5) — намали интензивността на следващите качествени тренировки.")
        elif avg_rpe <= 3.5:
            focus.append("Тренировките са ти леки — ако това продължи, планът ще се адаптира нагоре.")

    bmi = meta.get("zones", {}).get("bmi")
    if bmi:
        if bmi >= 27:
            focus.append(
                f"BMI {bmi} е над оптималното за издръжливост — всеки излишен килограм "
                "струва ~1% бегова икономия и W/kg на колелото. Не гладувай: лек калориен "
                "дефицит + белтъчини, а Z2 обемът ще свърши останалото."
            )
        elif bmi < 18.5:
            focus.append(
                f"BMI {bmi} е нисък — при недостатъчна енергия тялото жертва адаптацията "
                "и костите (RED-S). Яж достатъчно около тренировките; при съмнение — лекар."
            )

    race = (db.load_profile(user) or {}).get("goal", {}).get("race")
    days_to_race = None
    if race and race.get("date"):
        days_to_race = (dt.date.fromisoformat(race["date"]) - dt.date.today()).days

    return {
        "current_week": current_week,
        "total_weeks": len(meta["weeks"]),
        "phase": phase,
        "done": len(done), "skipped": len(skipped), "total": len(workouts),
        "missed": len(past_planned),
        "weekly": weekly,
        "avg_rpe": avg_rpe,
        "ratings_count": len(rpes),
        "focus": focus,
        "race": race,
        "days_to_race": days_to_race,
        "zones": meta.get("zones", {}),
    }


# ----------------------------------------------------------------- workouts

@app.get("/api/workouts/today")
def today(user: str = Depends(current_user)):
    row = db.active_plan(user)
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
def set_status(workout_id: int, body: StatusUpdate, user: str = Depends(current_user)):
    if body.status not in ("done", "skipped", "planned"):
        raise HTTPException(400, "Невалиден статус.")
    wo = db.get_workout(user, workout_id)
    if not wo:
        raise HTTPException(404, "Няма такава тренировка.")
    if body.status == "done":
        _require_workout_day_passed(wo)
    db.update_workout(workout_id, status=body.status)
    return {"ok": True}


@app.post("/api/workouts/{workout_id}/rating")
def rate(workout_id: int, rating: WorkoutRating, user: str = Depends(current_user)):
    wo = db.get_workout(user, workout_id)
    if not wo:
        raise HTTPException(404, "Няма такава тренировка.")
    _require_workout_day_passed(wo)
    db.save_rating(workout_id, rating.model_dump())
    db.update_workout(workout_id, status="done")

    row = db.active_plan(user)
    message, adjusted = None, 0
    if row:
        plan_id, meta, workouts = row
        recent = db.recent_ratings(plan_id)
        factor, message = adaptation.evaluate_ratings(recent)
        if factor:
            from .models import Workout
            models = [Workout.model_validate({k: v for k, v in w.items() if k != "plan_created"})
                      for w in workouts]
            horizon = wo["plan_week"] + 2
            targets = [m for m in models if wo["plan_week"] <= m.plan_week <= horizon]
            adjusted = adaptation.apply_adjustment(targets, factor)
            for m in targets:
                db.update_workout(m.id, data=m.model_dump(mode="json"))
    return {"ok": True, "coach_message": message, "adjusted_workouts": adjusted}


@app.get("/api/workouts/{workout_id}/zwo", response_class=PlainTextResponse)
def workout_zwo(workout_id: int, user: str = Depends(current_user)):
    wo = db.get_workout(user, workout_id)
    if not wo:
        raise HTTPException(404, "Няма такава тренировка.")
    if not zwo.is_zwo_exportable(wo):
        raise HTTPException(400, "Тази тренировка няма мощностни цели за .zwo експорт.")
    return zwo.to_zwo(wo)


# ------------------------------------------------------- activity auto-sync

@app.post("/api/sync/activities")
def sync_activities(user: str = Depends(current_user)):
    """Pull recent completed activities from intervals.icu and tick off the
    matching planned workouts, storing a compact plan-vs-actual summary."""
    creds = db.load_integration(user, "intervals")
    if not creds:
        raise HTTPException(400, "intervals.icu не е свързан.")
    row = db.active_plan(user)
    if not row:
        raise HTTPException(404, "Няма активен план.")
    _, meta, workouts = row
    workouts = _with_dates(meta, workouts)
    client = IntervalsClient(creds["api_key"], creds["athlete_id"])
    try:
        acts = client.activities()
    except Exception:
        raise HTTPException(502, "intervals.icu не отговори — опитай пак по-късно.")
    pairs = activity_sync.match_activities(workouts, acts)
    for wo, act in pairs:
        wo["actual"] = act
        db.update_workout(wo["id"], data=wo, status="done")
    return {
        "synced": len(pairs),
        "matched": [{"workout_id": w["id"], "workout": w["name"],
                     "activity": a["name"], "date": a["date"]} for w, a in pairs],
    }


# ------------------------------------------------------------- intervals.icu

class IntervalsCreds(BaseModel):
    api_key: str
    athlete_id: str


@app.post("/api/integrations/intervals")
def connect_intervals(creds: IntervalsCreds, user: str = Depends(current_user)):
    client = IntervalsClient(creds.api_key, creds.athlete_id)
    try:
        info = client.check()
    except Exception:
        raise HTTPException(400, "Неуспешна връзка с intervals.icu — провери ключа и athlete ID.")
    db.save_integration(user, "intervals", creds.model_dump())
    return {"connected": True, "athlete": info}


@app.get("/api/integrations/intervals")
def intervals_status(user: str = Depends(current_user)):
    return {"connected": db.load_integration(user, "intervals") is not None}


def _intervals_client(user: str) -> IntervalsClient:
    creds = db.load_integration(user, "intervals")
    if not creds:
        raise HTTPException(400, "intervals.icu не е свързан.")
    return IntervalsClient(creds["api_key"], creds["athlete_id"])


@app.post("/api/integrations/intervals/push-week/{week}")
def push_week(week: int, user: str = Depends(current_user)):
    row = db.active_plan(user)
    if not row:
        raise HTTPException(404, "Няма активен план.")
    _, meta, workouts = row
    client = _intervals_client(user)
    ftp = meta.get("zones", {}).get("ftp_w")
    pushed = 0
    for wo in _with_dates(meta, workouts):
        if wo["plan_week"] != week or wo["status"] != "planned":
            continue
        if wo["sport"] in ("strength", "stretching"):
            continue  # in-app sessions; Garmin gets only run/bike
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
def weekly_review(body: ReviewRequest, user: str = Depends(current_user)):
    p = db.load_profile(user)
    row = db.active_plan(user)
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
    actuals = activity_sync.actuals_digest(workouts)
    if actuals:
        digest["plan_vs_actual"] = actuals
    wellness = None
    creds = db.load_integration(user, "intervals")
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
