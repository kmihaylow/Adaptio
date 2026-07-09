"""Running plan generator — Daniels' Running Formula structure.

Weekly skeleton: one long run, one or two quality sessions (threshold / VO2max
intervals / repetition, chosen by phase and goal distance), easy runs in
between. Quality never exceeds 2 sessions/week; long run ≤ ~30% of weekly
volume; intensity distribution stays pyramidal (most volume easy).
"""

from __future__ import annotations

from .models import (Goal, Plan, PlanWeek, Profile, RunDistance, RunGoalType,
                     Segment, SegmentType, TargetKind, Workout)
from .planning import (level_params, phase_for_week, place_week_days,
                       plan_length_weeks, week_hours)
from .zones import resolve_zones

EASY_PACE_HR_NOTE = "Говорно темпо — трябва да можеш да водиш разговор (Z2)."


def _seg(t: SegmentType, dur_s: int, pace: list[int], note: str | None = None) -> Segment:
    return Segment(type=t, duration_s=int(dur_s), target_kind=TargetKind.pace,
                   low=pace[0], high=pace[1], note=note)


def _easy_run(week: int, day: int, minutes: int, paces: dict, name: str = "Леко бягане",
              kind: str = "endurance") -> Workout:
    e = paces["easy"]
    return Workout(
        plan_week=week, day_of_week=day, sport="run", name=name, kind=kind,
        duration_min=minutes, load_hint=round(minutes * 0.7),
        description=f"{minutes} мин леко темпо {_fmt(e)}. {EASY_PACE_HR_NOTE}",
        segments=[_seg(SegmentType.steady, minutes * 60, e, "леко, разговорно темпо")],
    )


def _fmt(p: list[int]) -> str:
    def one(s: int) -> str:
        return f"{s // 60}:{s % 60:02d}"
    return f"{one(p[0])}–{one(p[1])}/км"


def _quality_run(week: int, day: int, minutes: int, paces: dict, phase: str,
                 goal: Goal, step: int) -> Workout:
    """Pick the quality session for this phase; `step` indexes the progression."""
    e, t, i, r = paces["easy"], paces["threshold"], paces["interval"], paces["repetition"]
    wu = _seg(SegmentType.warmup, 12 * 60, e, "загрявка + 4 стрийда по 20 сек")
    cd = _seg(SegmentType.cooldown, 8 * 60, e)
    dist = goal.run_distance
    long_goal = dist in (RunDistance.half, RunDistance.marathon)

    if phase in ("base", "recovery"):
        reps = min(6, 4 + step)
        segs = [wu]
        for _ in range(reps):
            segs += [_seg(SegmentType.interval_on, 60, r, "стрийд/репетиция — бърза, отпусната техника"),
                     _seg(SegmentType.interval_off, 120, e, "тръс")]
        segs.append(cd)
        name, kind, desc = "Стрийдове + техника", "intervals", \
            f"{reps}×1 мин бързо ({_fmt(r)}) с 2 мин тръс. Учи краката на скорост без умора."
    elif phase == "build" and not long_goal:
        reps = min(6, 3 + step)
        on = min(240, 180 + step * 30)
        segs = [wu]
        for _ in range(reps):
            segs += [_seg(SegmentType.interval_on, on, i, "VO2max интервал — тежко, но контролирано"),
                     _seg(SegmentType.interval_off, max(120, on // 2 + 60), e, "тръс")]
        segs.append(cd)
        name, kind = "VO2max интервали", "vo2max"
        desc = f"{reps}×{on // 60} мин @ {_fmt(i)} с тръс за възстановяване. Вдига тавана на аеробния капацитет."
    else:  # threshold work: build for HM/M, peak for everyone
        blocks = min(3, 1 + step // 2)
        block_min = 15 if blocks == 1 else 10 + (step % 2) * 2
        segs = [wu]
        for b in range(blocks):
            segs.append(_seg(SegmentType.interval_on, block_min * 60, t, "темпо на прага — „комфортно тежко“"))
            if b < blocks - 1:
                segs.append(_seg(SegmentType.interval_off, 3 * 60, e, "тръс"))
        segs.append(cd)
        name, kind = "Темпо на прага (T)", "threshold"
        desc = f"{blocks}×{block_min} мин @ {_fmt(t)}. Вдига лактатния праг — най-ценната тренировка за състезания."

    total = sum(s.duration_s for s in segs)
    return Workout(plan_week=week, day_of_week=day, sport="run", name=name, kind=kind,
                   duration_min=round(total / 60), description=desc, segments=segs,
                   load_hint=round(total / 60 * 1.4))


def _long_run(week: int, day: int, minutes: int, paces: dict, phase: str, goal: Goal) -> Workout:
    e, m = paces["easy"], paces["marathon"]
    segs = [_seg(SegmentType.steady, minutes * 60, e, "равномерно, леко")]
    desc = f"{minutes} мин дълго леко бягане {_fmt(e)}. Гради аеробната база и издръжливостта на мускулите."
    if phase == "peak" and goal.run_distance in (RunDistance.half, RunDistance.marathon):
        mm = min(40, round(minutes * 0.35))
        segs = [
            _seg(SegmentType.steady, (minutes - mm) * 60, e, "леко"),
            _seg(SegmentType.steady, mm * 60, m, "финал в маратонско/състезателно темпо"),
        ]
        desc = (f"{minutes} мин дълго бягане: последните {mm} мин в целево темпо {_fmt(m)} — "
                "учи тялото да бяга бързо на уморени крака.")
    return Workout(plan_week=week, day_of_week=day, sport="run", name="Дълго бягане", kind="long",
                   duration_min=minutes, description=desc, segments=segs,
                   load_hint=round(minutes * 0.9))


def generate_run_plan(profile: Profile) -> Plan:
    zones = resolve_zones(profile)
    paces = zones["run_paces_s_per_km"]
    total_weeks, warnings = plan_length_weeks(profile.goal)
    has_race = profile.goal.race is not None
    if zones.get("vdot_source") == "conservative default (no test data)":
        warnings.append(
            "Нямаме реален тест за бегова форма — темпата са консервативни. "
            "Пробвай лек тест (напр. 5 км с пълни сили или Cooper тест) и въведи "
            "резултата, за да са точни зоните."
        )

    run_share = 1.0 if profile.sport.value == "run" else 0.5
    lp = level_params(profile)
    weeks: list[PlanWeek] = []
    workouts: list[Workout] = []

    for w in range(1, total_weeks + 1):
        phase = phase_for_week(w, total_weeks, has_race, lp["base_share"])
        hours = week_hours(profile, w, total_weeks, phase) * run_share
        minutes = round(hours * 60)
        n_runs = max(2, min(6, round(minutes / 50)))
        days = place_week_days(profile, w, n_runs)
        long_day = days[-1]
        quality_days = []
        if phase != "taper" and n_runs >= 3:
            mid = [d for d in days if d != long_day]
            quality_days = [mid[len(mid) // 2]] if len(mid) < 4 or phase in ("base", "recovery") \
                else [mid[0], mid[-1]]
            quality_days = quality_days[:lp["max_quality"]]

        long_min = min(round(minutes * 0.32), 150 if profile.goal.run_distance == RunDistance.marathon else 110)
        long_min = max(35, long_min)
        rest_min = minutes - long_min
        other_days = [d for d in days if d != long_day]
        per_run = max(25, round(rest_min / max(1, len(other_days))))

        step = max(0, w - 1 - (w - 1) // 4)  # progression index, recovery weeks don't advance
        wk_workouts: list[Workout] = []
        for d in other_days:
            if d in quality_days:
                wk_workouts.append(_quality_run(w, d, per_run, paces, phase, profile.goal, step))
            else:
                wk_workouts.append(_easy_run(w, d, per_run, paces))
        wk_workouts.append(_long_run(w, long_day, long_min, paces, phase, profile.goal))

        if phase == "taper" and has_race and w == total_weeks:
            focus = "Тейпър: сваляме умората, пазим свежестта. Успех на старта!"
        else:
            focus = {
                "base": "База: обем в леко темпо + техника (стрийдове).",
                "build": "Изграждане: качествени интервали върху стабилна база.",
                "peak": "Пик: специфична работа в състезателно темпо.",
                "recovery": "Възстановителна седмица: по-малко обем, свежи крака.",
                "taper": "Тейпър: минимален обем, запазваме интензивност на щипки.",
            }[phase]
        weeks.append(PlanWeek(number=w, phase=phase, focus=focus, target_hours=round(hours, 1)))
        workouts.extend(wk_workouts)

    return Plan(sport=profile.sport, weeks=weeks, workouts=workouts,
                warnings=warnings, zones=zones)
