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
