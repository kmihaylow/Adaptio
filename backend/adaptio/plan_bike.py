"""Cycling plan generator — Coggan-zone based, equipment-aware.

Targets cascade by what the athlete owns (изискване т.8):
  power meter / smart trainer → watt targets (and .zwo export),
  HR strap / smartwatch      → heart-rate zones,
  nothing                    → RPE (perceived effort 1–10).

Goal progressions:
  FTP       — sweet-spot → threshold blocks (2×15 → 2×20 → 3×15 → 2×25 …)
  endurance — Z2 volume + tempo & low-cadence strength blocks
  VO2max    — classic 3–5 min intervals @106–115% FTP (4×3 → 5×3 → 4×4 → 5×4 …)
"""

from __future__ import annotations

from .models import (BikeGoalType, Plan, PlanWeek, Profile, Segment,
                     SegmentType, TargetKind, Workout)
from .planning import phase_for_week, place_days, plan_length_weeks, week_hours
from .zones import LTHR_ZONES, MAXHR_ZONES, resolve_zones

# RPE equivalents per power zone (Borg CR10-ish)
RPE = {"z1_recovery": (2, 3), "z2_endurance": (3, 4), "z3_tempo": (5, 6),
       "sweet_spot": (6, 7), "z4_threshold": (7, 8), "z5_vo2max": (9, 10)}
# midpoint %FTP per zone, for power targets
PWR = {"z1_recovery": (0.45, 0.55), "z2_endurance": (0.60, 0.72), "z3_tempo": (0.78, 0.86),
       "sweet_spot": (0.88, 0.94), "z4_threshold": (0.96, 1.04), "z5_vo2max": (1.08, 1.15)}


class _Targets:
    """Resolve a named zone into a Segment target for this athlete's equipment."""

    def __init__(self, profile: Profile, zones: dict):
        self.profile = profile
        eq = profile.equipment
        if eq.has_power:
            self.kind = TargetKind.power
        elif eq.has_hr:
            self.kind = TargetKind.hr
        else:
            self.kind = TargetKind.rpe
        if profile.lthr_bpm:
            self._hr_base, self._hr_table = profile.lthr_bpm, LTHR_ZONES
        else:
            self._hr_base, self._hr_table = zones["max_hr_bpm"], MAXHR_ZONES

    def seg(self, t: SegmentType, dur_s: int, zone: str, cadence: int | None = None,
            note: str | None = None) -> Segment:
        if self.kind == TargetKind.power:
            lo, hi = PWR[zone]
        elif self.kind == TargetKind.hr:
            zl, zh = self._hr_table.get(zone, self._hr_table["z3_tempo"]) if zone != "sweet_spot" \
                else (0.90, 0.96) if self._hr_table is LTHR_ZONES else (0.77, 0.85)
            lo, hi = round(zl * self._hr_base), round(zh * self._hr_base)
        else:
            lo, hi = RPE[zone]
        return Segment(type=t, duration_s=int(dur_s), target_kind=self.kind,
                       low=lo, high=hi, cadence_rpm=cadence, note=note)


def _endurance_ride(tg: _Targets, week: int, day: int, minutes: int,
                    name: str = "Издръжливост Z2", low_cadence: bool = False) -> Workout:
    segs = [tg.seg(SegmentType.warmup, 8 * 60, "z1_recovery")]
    body = minutes - 13
    if low_cadence and body >= 40:
        third = body // 3 * 60
        segs += [tg.seg(SegmentType.steady, third, "z2_endurance"),
                 tg.seg(SegmentType.steady, third, "z3_tempo", cadence=60,
                        note="силова секция: ниска честота 55–65 об/мин, седнал"),
                 tg.seg(SegmentType.steady, body * 60 - 2 * third, "z2_endurance")]
        desc = f"{minutes} мин Z2 със силова секция на ниска честота — сила на педала без клякания."
        kind = "tempo"
    else:
        segs.append(tg.seg(SegmentType.steady, body * 60, "z2_endurance",
                           note="стабилно, разговорно усилие"))
        desc = f"{minutes} мин стабилно Z2. Тук се градят митохондриите — не подценявай „лесното“."
        kind = "endurance"
    segs.append(tg.seg(SegmentType.cooldown, 5 * 60, "z1_recovery"))
    return Workout(plan_week=week, day_of_week=day, sport="bike", name=name, kind=kind,
                   duration_min=minutes, description=desc, segments=segs,
                   load_hint=round(minutes * 0.65))


def _sweet_spot(tg: _Targets, week: int, day: int, step: int) -> Workout:
    ladder = [(2, 12), (2, 15), (3, 12), (2, 20), (3, 15), (2, 25), (3, 18), (2, 30)]
    reps, block = ladder[min(step, len(ladder) - 1)]
    segs = [tg.seg(SegmentType.warmup, 10 * 60, "z2_endurance")]
    for r in range(reps):
        segs.append(tg.seg(SegmentType.interval_on, block * 60, "sweet_spot",
                           note="sweet spot — тежко, но удържимо"))
        if r < reps - 1:
            segs.append(tg.seg(SegmentType.interval_off, 5 * 60, "z1_recovery"))
    segs.append(tg.seg(SegmentType.cooldown, 7 * 60, "z1_recovery"))
    total = round(sum(s.duration_s for s in segs) / 60)
    return Workout(plan_week=week, day_of_week=day, sport="bike",
                   name=f"Sweet Spot {reps}×{block} мин", kind="threshold",
                   duration_min=total, segments=segs, load_hint=round(total * 1.25),
                   description=f"{reps}×{block} мин @ 88–94% FTP с 5 мин почивка. "
                               "Най-ефективният начин да вдигнеш FTP при малко време.")


def _threshold(tg: _Targets, week: int, day: int, step: int) -> Workout:
    ladder = [(2, 8), (2, 10), (3, 8), (3, 10), (2, 15), (3, 12), (2, 20)]
    reps, block = ladder[min(step, len(ladder) - 1)]
    segs = [tg.seg(SegmentType.warmup, 12 * 60, "z2_endurance")]
    for r in range(reps):
        segs.append(tg.seg(SegmentType.interval_on, block * 60, "z4_threshold",
                           note="праг — контролирано страдание"))
        if r < reps - 1:
            segs.append(tg.seg(SegmentType.interval_off, 5 * 60, "z1_recovery"))
    segs.append(tg.seg(SegmentType.cooldown, 8 * 60, "z1_recovery"))
    total = round(sum(s.duration_s for s in segs) / 60)
    return Workout(plan_week=week, day_of_week=day, sport="bike",
                   name=f"Праг {reps}×{block} мин", kind="threshold",
                   duration_min=total, segments=segs, load_hint=round(total * 1.4),
                   description=f"{reps}×{block} мин @ 96–104% FTP. Директен удар по прага.")


def _vo2(tg: _Targets, week: int, day: int, step: int) -> Workout:
    ladder = [(4, 3), (5, 3), (4, 4), (5, 4), (6, 4), (5, 5)]
    reps, block = ladder[min(step, len(ladder) - 1)]
    segs = [tg.seg(SegmentType.warmup, 12 * 60, "z2_endurance",
                   note="в края 2–3 ускорения по 30 сек")]
    for r in range(reps):
        segs.append(tg.seg(SegmentType.interval_on, block * 60, "z5_vo2max",
                           note="VO2max — дишането трябва да е на предела към края"))
        if r < reps - 1:
            segs.append(tg.seg(SegmentType.interval_off, block * 60, "z1_recovery"))
    segs.append(tg.seg(SegmentType.cooldown, 8 * 60, "z1_recovery"))
    total = round(sum(s.duration_s for s in segs) / 60)
    return Workout(plan_week=week, day_of_week=day, sport="bike",
                   name=f"VO2max {reps}×{block} мин", kind="vo2max",
                   duration_min=total, segments=segs, load_hint=round(total * 1.5),
                   description=f"{reps}×{block} мин @ 106–115% FTP, почивка = работа. "
                               "Вдига тавана — само при добро възстановяване!")


def _recovery_spin(tg: _Targets, week: int, day: int, minutes: int = 35) -> Workout:
    return Workout(plan_week=week, day_of_week=day, sport="bike", name="Възстановително въртене",
                   kind="recovery", duration_min=minutes, load_hint=round(minutes * 0.3),
                   description="Съвсем леко въртене, висока честота. Кръвта се движи, умората си отива.",
                   segments=[tg.seg(SegmentType.steady, minutes * 60, "z1_recovery", cadence=95,
                                    note="леко, 90–100 об/мин")])


def generate_bike_plan(profile: Profile) -> Plan:
    zones = resolve_zones(profile)
    tg = _Targets(profile, zones)
    total_weeks, warnings = plan_length_weeks(profile.goal)
    has_race = profile.goal.race is not None
    goal_type = profile.goal.bike_goal_type or BikeGoalType.ftp

    if "estimated" in zones.get("ftp_source", "") and tg.kind == TargetKind.power:
        warnings.append(
            "FTP-то е приблизителна оценка. Направи 20-минутен FTP тест "
            "(FTP ≈ 95% от средната мощност) през първата седмица и обнови профила."
        )
    if tg.kind == TargetKind.rpe:
        warnings.append(
            "Без пауърметър/тренажор и без пулсомер тренировките са по усещане (RPE 1–10). "
            "Работят, но дори евтин пулсомер-колан ще вдигне точността значително."
        )

    bike_share = 1.0 if profile.sport.value == "bike" else 0.5
    weeks: list[PlanWeek] = []
    workouts: list[Workout] = []

    for w in range(1, total_weeks + 1):
        phase = phase_for_week(w, total_weeks, has_race, profile.currently_training)
        hours = week_hours(profile, w, total_weeks, phase) * bike_share
        minutes = round(hours * 60)
        n_rides = max(2, min(6, round(minutes / 65)))
        days = place_days(profile.available_days, n_rides)
        long_day = days[-1]
        other_days = [d for d in days if d != long_day]
        step = max(0, (w - 1) - (w - 1) // 4)

        n_quality = 0 if phase == "taper" else (1 if phase in ("base", "recovery") or n_rides <= 3 else 2)
        if goal_type == BikeGoalType.endurance:
            n_quality = min(n_quality, 1)

        long_min = max(45, min(round(minutes * 0.4), 240))
        rest_min = max(0, minutes - long_min)
        per_ride = max(35, round(rest_min / max(1, len(other_days)))) if other_days else 0

        quality_days = other_days[:n_quality] if n_quality else []
        # keep hard days apart: first and last of the mid-week days
        if n_quality == 2 and len(other_days) >= 2:
            quality_days = [other_days[0], other_days[-1]]

        wk: list[Workout] = []
        for d in other_days:
            if d in quality_days:
                if goal_type == BikeGoalType.vo2max and phase in ("build", "peak"):
                    wk.append(_vo2(tg, w, d, step))
                elif goal_type == BikeGoalType.ftp and phase == "peak":
                    wk.append(_threshold(tg, w, d, step))
                elif goal_type == BikeGoalType.endurance:
                    wk.append(_endurance_ride(tg, w, d, per_ride, name="Темпо + сила",
                                              low_cadence=True))
                else:
                    wk.append(_sweet_spot(tg, w, d, step))
            elif phase == "recovery" and len(wk) == 0:
                wk.append(_recovery_spin(tg, w, d))
            else:
                wk.append(_endurance_ride(tg, w, d, per_ride))
        wk.append(_endurance_ride(tg, w, long_day, long_min, name="Дълго Z2 каране"))

        focus = {
            "base": "База: Z2 обем + sweet spot. Градим мотора.",
            "build": "Изграждане: повече качествена работа върху базата.",
            "peak": "Пик: специфични усилия близо до целта.",
            "recovery": "Възстановителна седмица — остави адаптацията да се случи.",
            "taper": "Тейпър: свежест преди събитието.",
        }[phase]
        weeks.append(PlanWeek(number=w, phase=phase, focus=focus, target_hours=round(hours, 1)))
        workouts.extend(wk)

    return Plan(sport=profile.sport, weeks=weeks, workouts=workouts,
                warnings=warnings, zones=zones)


def generate_plan(profile: Profile) -> Plan:
    """Entry point: run, bike, or interleaved both."""
    from .models import Sport
    if profile.sport == Sport.run:
        return generate_run_plan_only(profile)
    if profile.sport == Sport.bike:
        return generate_bike_plan(profile)
    # both: generate each at half volume, merge, resolve day clashes
    from .plan_run import generate_run_plan
    run_plan = generate_run_plan(profile)
    bike_plan = generate_bike_plan(profile)
    merged = Plan(sport=profile.sport, weeks=bike_plan.weeks,
                  warnings=list(dict.fromkeys(run_plan.warnings + bike_plan.warnings)),
                  zones={**bike_plan.zones, **run_plan.zones}, workouts=[])
    used: set[tuple[int, int]] = set()
    for wo in sorted(run_plan.workouts + bike_plan.workouts,
                     key=lambda x: (x.plan_week, x.day_of_week, -x.load_hint)):
        key = (wo.plan_week, wo.day_of_week)
        if key in used:
            # shift to the nearest free available day, or drop the lighter session
            days_ok = set(profile.available_days) or set(range(7))
            for shift in (1, -1, 2, -2, 3, -3):
                d = wo.day_of_week + shift
                if 0 <= d <= 6 and d in days_ok and (wo.plan_week, d) not in used:
                    wo.day_of_week = d
                    key = (wo.plan_week, d)
                    break
            else:
                continue
        used.add(key)
        merged.workouts.append(wo)
    return merged


def generate_run_plan_only(profile: Profile) -> Plan:
    from .plan_run import generate_run_plan
    return generate_run_plan(profile)
