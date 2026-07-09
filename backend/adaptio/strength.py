"""Sport-specific strength sessions (roadmap т.4).

Why: 20-35 min, doable at home, and they demonstrably cut injury risk and
improve running/cycling economy (Rønnestad & Mujika 2014; Blagrove 2018).

Selection logic:
  runners  → single-leg movements + hip/calf strength (most running injuries
             start at weak hips and overloaded calves/achilles);
  cyclists → squat/hinge patterns + trunk work compensating the bent-over
             position; low-cadence force work stays on the bike itself.

Insertion rules (deterministic, mirrors docs/predlozhenia-analiz-i-silovi.md):
  max 2×/week (1× in recovery/taper), only on days without cardio, never the
  day before a quality session or the long workout — leg fatigue would wreck
  the session that actually drives the plan.

Demo links are YouTube search URLs: they never 404 and always surface current
form videos; swap for curated/own clips later.
"""

from __future__ import annotations

from .models import Exercise, Plan, PlanWeek, Profile, Workout

QUALITY_KINDS = {"threshold", "vo2max", "intervals", "tempo"}


def _demo(query: str) -> str:
    return "https://www.youtube.com/results?search_query=" + query.replace(" ", "+")


# (name, note, demo search, run?, bike?)
_CATALOG: list[tuple[str, str, str, bool, bool]] = [
    ("Румънска мъртва тяга на един крак",
     "Гръб прав, тазът назад; усещаш задното бедро. С дъмбел/раница или само тегло.",
     "single leg romanian deadlift form", True, False),
    ("Напади назад",
     "Крачка назад, коляното към пода; предното коляно над стъпалото.",
     "reverse lunge form", True, True),
    ("Степ-ъп на кутия/стъпало",
     "Качвай се с контрол, без да се оттласкваш с долния крак.",
     "step up exercise form", True, False),
    ("Повдигане на пръсти (прасец)",
     "Бавно надолу (3 сек) — ексцентриката пази ахилеса. На ръб на стъпало.",
     "calf raise eccentric form", True, False),
    ("Мост за седалище",
     "Стискай седалището горе за 2 сек; кръстът не се извива. По-трудно: на един крак.",
     "glute bridge form", True, True),
    ("Клек / гоблет клек",
     "Пети на пода, гърди напред; с тежест пред гърдите, ако имаш.",
     "goblet squat form", False, True),
    ("Мъртва тяга",
     "Тазобедрен шарнир — тазът назад, гръб неутрален. С щанга/дъмбели или раница.",
     "romanian deadlift form", False, True),
    ("Планк + странични планкове",
     "Тялото в права линия, не задържай дъх. 3× по 30-45 сек общо.",
     "plank side plank form", True, True),
    ("Bird-dog",
     "Противоположни ръка и крак, бавно, без люлеене на таза.",
     "bird dog exercise form", False, True),
    ("Dead bug",
     "Кръстът притиснат към пода през цялото време.",
     "dead bug exercise form", True, True),
]

# sets × reps by phase: base teaches the movement, build adds strength,
# peak/recovery/taper only maintain — never new stimulus near race day
_DOSE = {
    "base": (2, "12-15"),
    "build": (3, "8-10"),
    "peak": (2, "6-8"),
    "recovery": (2, "10-12"),
    "taper": (2, "8-10"),
}


def _exercises(sport: str, phase: str) -> list[Exercise]:
    sets, reps = _DOSE[phase]
    wants_run = sport in ("run", "both")
    wants_bike = sport in ("bike", "both")
    picked = [e for e in _CATALOG if (e[3] and wants_run) or (e[4] and wants_bike)]
    return [
        Exercise(name=name, sets=sets, reps=reps, note=note, demo_url=_demo(q))
        for name, note, q, _, _ in picked[:6]
    ]


def _strength_days(week_workouts: list[Workout], available: list[int], n: int) -> list[int]:
    """Free days that don't precede a quality session or the long workout."""
    used = {w.day_of_week for w in week_workouts}
    protect = {w.day_of_week for w in week_workouts if w.kind in QUALITY_KINDS or w.kind == "long"}
    candidates = [d for d in sorted(set(available))
                  if d not in used and (d + 1) % 7 not in protect]
    if len(candidates) > n and n > 0:
        # spread them out instead of stacking Mon+Tue
        step = len(candidates) / n
        candidates = [candidates[min(len(candidates) - 1, round(i * step))] for i in range(n)]
    return candidates[:n]


def add_strength(plan: Plan, profile: Profile) -> None:
    """Append strength sessions to a generated cardio plan, in place."""
    sets_note = "Загрей 5 мин (подскоци, махове, кръгове с ръце) преди първото упражнение."
    for wk in plan.weeks:
        n = 1 if wk.phase in ("recovery", "taper") else 2
        week_workouts = [w for w in plan.workouts if w.plan_week == wk.number]
        for day in _strength_days(week_workouts, profile.available_days, n):
            exercises = _exercises(profile.sport.value, wk.phase)
            sets, reps = _DOSE[wk.phase]
            plan.workouts.append(Workout(
                plan_week=wk.number, day_of_week=day, sport="strength",
                name="Силова тренировка", kind="strength",
                duration_min=30,
                description=(f"{len(exercises)} упражнения × {sets} серии по {reps} повторения. "
                             f"{sets_note} Почивка 60-90 сек между сериите."),
                exercises=exercises,
                load_hint=15,
            ))
