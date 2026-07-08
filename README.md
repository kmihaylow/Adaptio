# Adaptio

AI-powered adaptive training coach for time-crunched amateur **runners and cyclists**.

Answer a short onboarding questionnaire (sport, body data, available time,
equipment, goal) and Adaptio builds a science-based progressive training plan —
Jack Daniels' VDOT paces for running, Coggan power/HR zones for cycling. Rate
every workout and the plan adapts to you. Garmin data flows in through
[intervals.icu](https://intervals.icu), and planned workouts flow back to your
Garmin calendar the same way.

Landing page: [adaptio.cc](https://adaptio.cc)

## Structure

```
backend/   FastAPI + SQLite — plan engine, adaptation rules, intervals.icu, Claude weekly review
app/       React + Vite PWA — mobile-first UI (Bulgarian), ready to wrap with Capacitor
```

## Quick start

Backend:

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env        # keys are optional; app works without them
python -m adaptio.main      # API on :8000
```

Frontend (dev):

```bash
cd app
npm install
npm run dev                 # UI on :5173, proxies /api to :8000
```

Open http://localhost:5173 on your phone-sized browser window and go through
the onboarding.

## Key design decisions

- **Deterministic plan engine, AI only where it matters.** Plans are generated
  by rule-based, sports-science-backed code (free, instant, predictable).
  Claude is called only for the weekly review with a compact digest — minimal
  token spend.
- **Equipment-aware targets.** Power meter / smart trainer → watts (+ .zwo
  export for MyWhoosh/Zwift), HR strap/watch → heart-rate zones, nothing → RPE.
- **Honest warnings.** If the goal timeline is physiologically unrealistic, the
  user is told before the plan is generated.
- **Garmin via intervals.icu** until the Garmin Developer Program reopens.

## Path to a mobile app

The frontend is a PWA (installable from the browser today). For app stores:
`npm run build`, then wrap `app/dist` with [Capacitor](https://capacitorjs.com)
(`npx cap add ios android`) and point the API base URL at a hosted backend.

See `CLAUDE.md` for architecture details and roadmap.
