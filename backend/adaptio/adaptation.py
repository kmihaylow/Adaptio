"""Rating-driven plan adaptation (изискване т.6).

Deterministic rules run first and are free (no tokens). The Claude coach is
only consulted for the weekly review, with a compact digest (see coach.py).

Rules (based on standard auto-regulation practice):
- quality session rated "too_hard" with RPE ≥ 9 twice in a row
    → ease upcoming quality sessions ~5% (power) / +10 s/km (pace) / −1 RPE
      for the next 14 days, and say so honestly.
- three consecutive "too_easy" ratings → nudge targets up ~2–3%.
- a single hard rating changes nothing — one bad day is just a bad day.
"""

from __future__ import annotations

from .models import Segment, TargetKind, Workout

QUALITY_KINDS = {"threshold", "vo2max", "intervals", "tempo"}


def _scale_segment(seg: Segment, factor: float) -> None:
    if seg.type.value not in ("interval_on", "steady"):
        return
    if seg.target_kind == TargetKind.power:
        seg.low = round(seg.low * factor, 3)
        seg.high = round(seg.high * factor, 3)
    elif seg.target_kind == TargetKind.pace:
        # pace: lower is faster → invert the factor
        seg.low = round(seg.low / factor)
        seg.high = round(seg.high / factor)
    elif seg.target_kind == TargetKind.hr:
        seg.low = round(seg.low * factor)
        seg.high = round(seg.high * factor)
    else:  # rpe
        delta = -1 if factor < 1 else 1
        seg.low = max(1, min(10, seg.low + delta))
        seg.high = max(1, min(10, seg.high + delta))


def apply_adjustment(workouts: list[Workout], factor: float, quality_only: bool = True) -> int:
    """Scale intensity of upcoming planned workouts; returns how many changed."""
    changed = 0
    for wo in workouts:
        if wo.status != "planned":
            continue
        if quality_only and wo.kind not in QUALITY_KINDS:
            continue
        for seg in wo.segments:
            _scale_segment(seg, factor)
        changed += 1
    return changed


def scale_workout_time(wo: Workout, factor: float) -> None:
    """Fit a workout into more/less available time WITHOUT touching intensity.

    Coach logic for a short day: the quality intervals are the point of the
    session — keep them; trim warmup/cooldown/steady volume instead. With
    extra time, extend the easy volume (more Z2 is always useful)."""
    factor = max(0.5, min(1.5, factor))
    is_flex = lambda s: s.type.value in ("warmup", "cooldown", "steady")
    flexible = [s for s in wo.segments if is_flex(s)]
    fixed_s = sum(s.duration_s for s in wo.segments if not is_flex(s))
    flex_s = sum(s.duration_s for s in flexible)
    old_total = fixed_s + flex_s
    if not old_total:
        wo.duration_min = max(10, round(wo.duration_min * factor))
        return
    target = old_total * factor
    if flex_s:
        flex_scale = max(0.35, (target - fixed_s) / flex_s)
        for s in flexible:
            s.duration_s = max(180, round(s.duration_s * flex_scale))
    new_total = sum(s.duration_s for s in wo.segments)
    wo.load_hint = round(wo.load_hint * new_total / old_total)
    wo.duration_min = round(new_total / 60)


def rebalance_after_actual(upcoming: list[Workout], done_workout: dict,
                           actual: dict) -> tuple[list[Workout], list[str]]:
    """React when what the athlete DID differs a lot from what was planned.

    Returns (changed_workouts_to_persist, coach_messages). Rules:
    - did much more than planned (≥140% duration/load) → the next few days'
      quality sessions ease ~5% so the extra load doesn't stack into a hole;
    - a quality session cut short (≤60%) → no punishment, but say honestly
      that the stimulus was missed and the next one matters.
    """
    planned_min = done_workout.get("duration_min") or 0
    actual_min = actual.get("moving_time_min") or 0
    if not planned_min or not actual_min:
        return [], []
    ratio = actual_min / planned_min
    planned_load, actual_load = done_workout.get("load_hint"), actual.get("load")
    if planned_load and actual_load:
        ratio = max(ratio, actual_load / planned_load)

    messages: list[str] = []
    changed: list[Workout] = []
    if ratio >= 1.4:
        week = done_workout["plan_week"]
        targets = [w for w in upcoming
                   if w.status == "planned" and week <= w.plan_week <= week + 1]
        if apply_adjustment(targets, 0.95):
            changed = targets
            messages.append(
                f"Тренировката е излязла ~{round(ratio * 100)}% от планираното — браво за мотивацията, "
                "но натоварването се трупа. Облекчих леко качествените тренировки в следващите дни, "
                "за да не платиш сметката с умора."
            )
    elif ratio <= 0.6 and done_workout.get("kind") in QUALITY_KINDS:
        messages.append(
            "Днешната качествена тренировка е останала доста по-кратка от плана. Случва се — "
            "но стимулът липсва, затова гледай следващата качествена сесия да е пълноценна. "
            "Ако времето е проблемът, кажи ми в деня колко имаш и ще преразпределя."
        )
    return changed, messages


def evaluate_ratings(recent: list[dict]) -> tuple[float | None, str | None]:
    """Decide on an adjustment from the rating history (newest last).

    `recent` items: {"kind": str, "rpe": int, "feel": str}
    Returns (intensity_factor, message) or (None, None).
    """
    if not recent:
        return None, None
    quality = [r for r in recent if r["kind"] in QUALITY_KINDS]
    if len(quality) >= 2 and all(
        r["feel"] == "too_hard" and r["rpe"] >= 9 for r in quality[-2:]
    ):
        return 0.95, (
            "Последните две качествени тренировки са били прекалено тежки. "
            "Свалям интензивността на предстоящите качествени сесии с ~5%, за да "
            "останеш в продуктивната зона — по-добре леко недотренран, отколкото прегорял."
        )
    if len(recent) >= 3 and all(r["feel"] == "too_easy" for r in recent[-3:]):
        return 1.025, (
            "Три поредни тренировки са ти били твърде леки — формата изпреварва плана. "
            "Вдигам целите с ~2.5%. Ако пак е леко, помисли за нов FTP/бегови тест."
        )
    last = recent[-1]
    if last["feel"] == "too_hard" and last["kind"] in QUALITY_KINDS:
        return None, (
            "Записах, че беше тежко. Една тежка тренировка е нормална — ще коригирам "
            "само ако се повтори. Наспи се и гледай следващата да е наистина лека."
        )
    return None, None
