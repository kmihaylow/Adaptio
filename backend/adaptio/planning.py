"""Shared periodization logic: phases, week layout, day placement, warnings.

Structure follows classic linear periodization (Bompa; Daniels' four phases):
base → build → peak → taper, with a reduced-load recovery week every 4th week
(supercompensation) and a race taper when an event date is set.
"""

from __future__ import annotations

import datetime as dt

from .models import Goal, Profile, RunDistance

# Minimum sensible plan length (weeks) before the goal is realistic.
MIN_WEEKS_RUN = {
    RunDistance.five_k: 6,
    RunDistance.ten_k: 8,
    RunDistance.half: 10,
    RunDistance.marathon: 14,
}
MIN_WEEKS_BIKE = {"ftp": 6, "endurance": 8, "vo2max": 6}


def plan_length_weeks(goal: Goal, today: dt.date | None = None) -> tuple[int, list[str]]:
    """Weeks available + warnings when the horizon is unrealistically short."""
    today = today or dt.date.today()
    warnings: list[str] = []
    if goal.race and goal.race.date:
        days = (goal.race.date - today).days
        weeks = max(2, days // 7)
        if days < 14:
            warnings.append(
                f"Състезанието „{goal.race.name}“ е след по-малко от 2 седмици — "
                "истинска адаптация вече не е възможна; планът ще е кратък тейпър, "
                "за да стигнеш до старта свеж."
            )
    else:
        weeks = goal.weeks or 8

    minimum = None
    if goal.run_distance:
        minimum = MIN_WEEKS_RUN[goal.run_distance]
    elif goal.bike_goal_type:
        minimum = MIN_WEEKS_BIKE[goal.bike_goal_type.value]
    if minimum and weeks < minimum:
        warnings.append(
            f"Избраният срок от {weeks} седмици е под препоръчителния минимум от "
            f"{minimum} седмици за тази цел. Физиологичната адаптация (митохондрии, "
            "капиляризация, ударен обем на сърцето) изисква време — резултатът "
            "вероятно няма да отговори на очакванията ти. Обмисли по-дълъг срок."
        )
    return weeks, warnings


def phase_for_week(week: int, total: int, has_race: bool) -> str:
    """base → build → peak → taper, recovery every 4th week (not in taper)."""
    taper_weeks = 0
    if has_race:
        taper_weeks = 1 if total <= 10 else 2
    if week > total - taper_weeks:
        return "taper"
    if week % 4 == 0 and week < total - taper_weeks:
        return "recovery"
    working = total - taper_weeks
    if week <= max(1, round(working * 0.4)):
        return "base"
    if week <= max(2, round(working * 0.75)):
        return "build"
    return "peak"


def week_hours(profile: Profile, week: int, total: int, phase: str) -> float:
    """Progressive volume: start ~80% of budget, ramp ≤ ~8%/week, cap at budget.

    Recovery weeks drop to ~65%, taper to ~55% of the athlete's budget — enough
    stimulus to hold fitness while fatigue drains (Mujika & Padilla, 2003).
    """
    budget = profile.weekly_hours
    base = min(budget, budget * 0.8 * (1.08 ** (week - 1)))
    if phase == "recovery":
        return round(budget * 0.65, 1)
    if phase == "taper":
        return round(budget * 0.55, 1)
    return round(base, 1)


def place_days(available: list[int], n_sessions: int, long_day_pref: tuple[int, ...] = (6, 5)) -> list[int]:
    """Pick training days: long session on the weekend when possible, quality
    sessions spread out so hard days never stack back-to-back."""
    days = sorted(set(d for d in available if 0 <= d <= 6)) or [0, 2, 5]
    n = min(n_sessions, len(days))
    long_day = next((d for d in long_day_pref if d in days), days[-1])
    rest = [d for d in days if d != long_day]
    # Spread the remaining sessions as evenly as the athlete's calendar allows.
    if n - 1 >= len(rest):
        chosen = rest
    else:
        step = len(rest) / (n - 1) if n > 1 else 1
        chosen, used = [], set()
        for i in range(n - 1):
            idx = min(len(rest) - 1, round(i * step))
            while idx in used:
                idx = (idx + 1) % len(rest)
            used.add(idx)
            chosen.append(rest[idx])
    return sorted(chosen + [long_day])
