"""Short stretching / mobility sessions (opt-in, like strength.py).

Best done the evening of a training day, when the tissue is warm — so unlike
strength these sessions land ON easy/long cardio days (a second, light card),
2×/week, 12-15 min. Static holds go after training, never before quality work
(acute static stretching briefly costs power/economy — Simic 2013).

Runners get the classic tight spots: calves/achilles, hip flexors, hamstrings,
glutes; cyclists get hip flexors + the fold-compensating chain: quads, chest /
thoracic spine, neck. Demo links are YouTube searches — never 404.
"""

from __future__ import annotations

from .models import Exercise, Plan, Profile, Workout

QUALITY_KINDS = {"threshold", "vo2max", "intervals", "tempo"}


def _demo(query: str) -> str:
    return "https://www.youtube.com/results?search_query=" + query.replace(" ", "+")


# (name, note, demo search, run?, bike?)
_CATALOG: list[tuple[str, str, str, bool, bool]] = [
    ("Прасец до стена",
     "Коляно право за горния прасец, леко свито за долния/ахилеса. Без пружиниране.",
     "calf stretch wall", True, False),
    ("Разтягане на тазобедрения флексор",
     "Колянна стойка, тазът напред и леко подвит; усещаш предната част на бедрото/слабините.",
     "kneeling hip flexor stretch", True, True),
    ("Задно бедро с колан/кърпа",
     "Легнал, кракът нагоре с кърпа; коляното може леко свито — целта е бедрото, не коляното.",
     "lying hamstring stretch strap", True, True),
    ("Фигура 4 (седалище/пириформис)",
     "Легнал, глезен върху другото коляно, придърпай бедрото към теб.",
     "figure four glute stretch", True, True),
    ("Котка-крава (гръбначна мобилност)",
     "Бавно редуване, дишай в движението. 8-10 повторения.",
     "cat cow stretch", True, True),
    ("Четириглав мускул прав",
     "Хвани глезена зад теб, коленете едно до друго, тазът подвит.",
     "standing quad stretch", False, True),
    ("Отваряне на гърди на рамка/стена",
     "Лакът на 90° на рамката, леко завъртане напред — контра на свитата поза.",
     "doorway chest stretch", False, True),
    ("Гръдна ротация на четири крака",
     "Ръка зад тила, завърти лакътя към тавана; погледът следва.",
     "thoracic rotation quadruped", False, True),
    ("Детска поза",
     "Отпусни се назад към петите, ръцете напред. Дишай дълбоко 30-60 сек.",
     "childs pose stretch", True, True),
]

_HOLD = "30-45 сек"


def _exercises(sport: str) -> list[Exercise]:
    wants_run = sport in ("run", "both")
    wants_bike = sport in ("bike", "both")
    picked = [e for e in _CATALOG if (e[3] and wants_run) or (e[4] and wants_bike)]
    return [Exercise(name=name, sets=1, reps=_HOLD, note=note, demo_url=_demo(q))
            for name, note, q, _, _ in picked[:6]]


def _stretch_days(week_workouts: list[Workout], n: int) -> list[int]:
    """Evenings of easy/long cardio days — warm tissue, no next-day conflict."""
    easy = sorted({w.day_of_week for w in week_workouts
                   if w.sport in ("run", "bike") and w.kind not in QUALITY_KINDS})
    if len(easy) > n > 0:
        step = len(easy) / n
        easy = [easy[min(len(easy) - 1, round(i * step))] for i in range(n)]
    return easy[:n]


def add_stretching(plan: Plan, profile: Profile) -> None:
    """Append stretching sessions to a generated plan, in place."""
    import datetime as dt
    for wk in plan.weeks:
        week_workouts = [w for w in plan.workouts if w.plan_week == wk.number]
        days = _stretch_days(week_workouts, 2)
        if wk.number == 1 and profile.rest_today:
            days = [d for d in days if d != dt.date.today().weekday()]
        for day in days:
            exercises = _exercises(profile.sport.value)
            plan.workouts.append(Workout(
                plan_week=wk.number, day_of_week=day, sport="stretching",
                name="Стречинг и мобилност", kind="stretching",
                duration_min=12,
                description=(f"{len(exercises)} разтягания по {_HOLD} на страна, вечерта след "
                             "тренировката, докато мускулите са топли. Дишай спокойно, без болка."),
                exercises=exercises,
                load_hint=3,
            ))
