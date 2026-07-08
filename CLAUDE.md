# Adaptio

AI-powered adaptive training coach for amateur runners and cyclists.
Onboarding questionnaire → deterministic science-based plan → per-workout
ratings drive adaptation → intervals.icu bridges Garmin both ways.

Landing page: https://adaptio.cc (deployed separately on Netlify, not in this repo).

## Architecture

```
app/ (React+Vite PWA, Bulgarian UI)
   └── /api proxy → backend/ (FastAPI + SQLite)
         ├── plan_run.py / plan_bike.py  — deterministic plan generators
         ├── zones.py                    — VDOT (Daniels), Coggan power zones, HR zones
         ├── planning.py                 — periodization, week layout, timeline warnings
         ├── adaptation.py               — rating-driven rules (free, no tokens)
         ├── coach.py                    — Claude weekly review (compact digest, structured output)
         ├── intervals.py                — intervals.icu client (wellness in, workouts out → Garmin)
         ├── zwo.py                      — .zwo export for power-based bike workouts
         ├── db.py                       — SQLite; user_id everywhere for future multi-user
         └── api.py                      — HTTP endpoints
```

- `python -m adaptio.main` runs uvicorn on :8000; `npm run dev` in `app/` on :5173.
- Single local user for now (`db.USER = "local"`); schema is multi-user ready.

## Coaching methodology (do not change without asking Kiril)

- Running: Jack Daniels VDOT — training paces derived from a recent race result
  (best), reported VO2max, or goal time. Weekly skeleton: long run + 1-2 quality
  sessions + easy runs; pyramidal distribution; cutback week every 4th; taper
  before races.
- Cycling: Coggan zones from FTP. Goal tracks: FTP (sweet spot → threshold
  ladders), endurance (Z2 volume + low-cadence strength), VO2max (3-5 min
  interval ladders). Volume ramp ≤ ~8%/week.
- Equipment cascade: power meter/smart trainer → watt targets (+ .zwo);
  HR device → HR zones (LTHR if known, else max HR, else Tanaka estimate);
  nothing → RPE.
- Adaptation: 2× consecutive "too hard" quality (RPE ≥ 9) → ease upcoming
  quality ~5%; 3× "too easy" → +2.5%. One bad day changes nothing.
- Unrealistic goal timelines produce explicit warnings (min weeks per goal in
  planning.py).

## Token frugality (important)

The plan engine is deterministic — no LLM. Claude is called only in
`coach.weekly_review()` with a compact digest and structured outputs
(`output_config.format`). Keep it that way; don't dump raw activity data into
prompts.

## Conventions

- Backend: Python 3.10+, FastAPI, pydantic v2, SQLite (stdlib sqlite3). Keep deps minimal.
- Frontend: React 18 + Vite + TS, no UI framework — theme.css owns the design system.
- Secrets only via .env (gitignored). Never commit keys.
- UI text in Bulgarian; code and comments in English.

## Roadmap (next steps, in order)

1. Auth + multi-user (Supabase or FastAPI-Users), then hosted deploy (Fly.io/Railway + Netlify).
2. Capacitor wrap of `app/` for App Store / Google Play.
3. Auto-import completed activities from intervals.icu to mark workouts done + compare planned/actual.
4. Direct Garmin Connect Developer Program integration (application pending — Garmin paused new requests mid-2026).
5. Stripe subscriptions (€5/mo founding price).

## Testing locally

```
cd backend && pip install -r requirements.txt && python -m adaptio.main
cd app && npm install && npm run dev
```
