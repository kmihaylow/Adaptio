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

from .models import Exercise, Plan, PlanWeek, Profile, StrengthSetting, Workout
from .planning import week_available_days

QUALITY_KINDS = {"threshold", "vo2max", "intervals", "tempo"}


def _demo(query: str) -> str:
    return "https://www.youtube.com/results?search_query=" + query.replace(" ", "+")


# Three catalogs — the same movement patterns (hinge, squat/lunge, calf, hip,
# trunk), loaded according to what the athlete has. Entry: (name, note, demo
# search, run?, bike?).
_HOME: list[tuple[str, str, str, bool, bool]] = [
    ("Румънска мъртва тяга на един крак (без тежест)",
     "Гръб прав, тазът назад; усещаш задното бедро. Раница с книги е добра добавка.",
     "single leg romanian deadlift bodyweight", True, False),
    ("Напади назад",
     "Крачка назад, коляното към пода; предното коляно над стъпалото.",
     "reverse lunge bodyweight form", True, True),
    ("Степ-ъп на кутия/стъпало",
     "Качвай се с контрол, без да се оттласкваш с долния крак.",
     "step up exercise form", True, False),
    ("Повдигане на пръсти (прасец)",
     "Бавно надолу (3 сек) — ексцентриката пази ахилеса. На ръб на стъпало.",
     "calf raise eccentric form", True, False),
    ("Мост за седалище на един крак",
     "Стискай седалището горе за 2 сек; кръстът не се извива.",
     "single leg glute bridge form", True, True),
    ("Клек със собствено тегло",
     "Пети на пода, гърди напред, до паралел или малко под него.",
     "bodyweight squat form", False, True),
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

_DUMBBELLS: list[tuple[str, str, str, bool, bool]] = [
    ("Румънска мъртва тяга на един крак с дъмбел",
     "Дъмбелът в срещуположната ръка; гръб прав, тазът назад.",
     "single leg romanian deadlift dumbbell", True, False),
    ("Напади назад с дъмбели",
     "Дъмбели отстрани, торсът изправен; коляното към пода с контрол.",
     "dumbbell reverse lunge form", True, True),
    ("Степ-ъп с дъмбели",
     "Качвай се с контрол; дъмбелите висят отстрани.",
     "dumbbell step up form", True, False),
    ("Повдигане на пръсти с дъмбел",
     "Дъмбел в едната ръка, другата за баланс; бавно надолу — пази ахилеса.",
     "single leg calf raise dumbbell", True, False),
    ("Гоблет клек",
     "Дъмбелът пред гърдите като бокал; пети на пода, гърди напред.",
     "goblet squat form", False, True),
    ("Румънска мъртва тяга с дъмбели",
     "Тазобедрен шарнир — тазът назад, гръб неутрален, дъмбелите покрай бедрата.",
     "dumbbell romanian deadlift form", True, True),
    ("Мост за седалище с тежест",
     "Дъмбелът върху таза; стискай седалището горе за 2 сек.",
     "dumbbell glute bridge form", False, True),
    ("Renegade row (планк с гребане)",
     "Планк върху дъмбелите, гребане без завъртане на таза — сила + стабилност.",
     "renegade row form", True, True),
    ("Dead bug",
     "Кръстът притиснат към пода през цялото време.",
     "dead bug exercise form", True, True),
]

_GYM: list[tuple[str, str, str, bool, bool]] = [
    ("Клек с щанга (заден)",
     "До паралел, пети на пода, коремът стегнат. Тежест, с която пазиш техниката.",
     "barbell back squat form", True, True),
    ("Румънска мъртва тяга с щанга",
     "Тазобедрен шарнир, щангата се плъзга по бедрата; гръб неутрален.",
     "barbell romanian deadlift form", True, True),
    ("Български клек (заден крак на пейка)",
     "Еднокраката сила, която бегачът реално ползва; дъмбели отстрани.",
     "bulgarian split squat form", True, False),
    ("Хип тръст с щанга",
     "Гръб на пейка, щанга върху таза; пълно изправяне и стискане горе.",
     "barbell hip thrust form", True, True),
    ("Прасци на машина / в Смит",
     "Пълна амплитуда, бавно надолу; правите прасци пазят ахилеса.",
     "standing calf raise machine form", True, False),
    ("Лег преса",
     "Контролирано надолу до 90°, без отлепяне на кръста от облегалката.",
     "leg press form", False, True),
    ("Гребане на кабел / едностранно с дъмбел",
     "Гърбът балансира часовете в аеро позиция; лакътят към джоба.",
     "seated cable row form", False, True),
    ("Планк с тежест / ab-wheel",
     "Права линия, тазът подвит; коремът работи срещу разгъване.",
     "weighted plank ab wheel form", True, True),
]

_CATALOGS = {
    StrengthSetting.home: _HOME,
    StrengthSetting.dumbbells: _DUMBBELLS,
    StrengthSetting.gym: _GYM,
}

# sets × reps by phase: base teaches the movement, build adds strength,
# peak/recovery/taper only maintain — never new stimulus near race day
_DOSE = {
    "base": (2, "12-15"),
    "build": (3, "8-10"),
    "peak": (2, "6-8"),
    "recovery": (2, "10-12"),
    "taper": (2, "8-10"),
}


def _exercises(sport: str, phase: str, setting: StrengthSetting) -> list[Exercise]:
    sets, reps = _DOSE[phase]
    wants_run = sport in ("run", "both")
    wants_bike = sport in ("bike", "both")
    catalog = _CATALOGS[setting]
    picked = [e for e in catalog if (e[3] and wants_run) or (e[4] and wants_bike)]
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
    setting = profile.strength_setting
    place = {"home": "вкъщи", "dumbbells": "вкъщи с дъмбели", "gym": "в залата"}[setting.value]
    for wk in plan.weeks:
        n = 1 if wk.phase in ("recovery", "taper") else 2
        week_workouts = [w for w in plan.workouts if w.plan_week == wk.number]
        for day in _strength_days(week_workouts, week_available_days(profile, wk.number), n):
            exercises = _exercises(profile.sport.value, wk.phase, setting)
            sets, reps = _DOSE[wk.phase]
            plan.workouts.append(Workout(
                plan_week=wk.number, day_of_week=day, sport="strength",
                name=f"Силова тренировка ({place})", kind="strength",
                duration_min=40 if setting == StrengthSetting.gym else 30,
                description=(f"{len(exercises)} упражнения × {sets} серии по {reps} повторения. "
                             f"{sets_note} Почивка {'2 мин' if setting == StrengthSetting.gym else '60-90 сек'} между сериите."),
                exercises=exercises,
                load_hint=20 if setting == StrengthSetting.gym else 15,
            ))
