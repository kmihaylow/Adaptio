"""Parse manually uploaded TCX/GPX activity files into the same compact
summary shape that intervals.icu activities use, so the one matching pipeline
(activity_sync.match_activities) handles both sources.

Stdlib-only on purpose (keep deps minimal): TCX and GPX are plain XML. .FIT is
binary and needs a dependency — Garmin exports TCX/GPX from Connect, and the
intervals.icu auto-sync covers the FIT path anyway.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import math
import xml.etree.ElementTree as ET


class UnsupportedFile(ValueError):
    pass


def _strip_ns(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _haversine_m(lat1, lon1, lat2, lon2) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _parse_time(s: str) -> dt.datetime:
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))


def _summary(sport: str, start: dt.datetime | None, moving_s: float,
             distance_m: float, hrs: list[float], watts: list[float],
             raw: bytes, name: str) -> dict:
    pace = None
    if sport == "run" and distance_m > 100 and moving_s > 0:
        pace = round(moving_s / (distance_m / 1000))
    return {
        "activity_id": "upload_" + hashlib.sha1(raw).hexdigest()[:12],
        "date": (start.date().isoformat() if start else dt.date.today().isoformat()),
        "sport": sport,
        "name": name,
        "moving_time_min": round(moving_s / 60),
        "distance_km": round(distance_m / 1000, 2) if distance_m else None,
        "avg_hr": round(sum(hrs) / len(hrs)) if hrs else None,
        "avg_watts": round(sum(watts) / len(watts)) if watts else None,
        "pace_s_per_km": pace,
        "load": None,
    }


def parse_tcx(raw: bytes, name: str) -> dict:
    root = ET.fromstring(raw)
    activity = next((el for el in root.iter() if _strip_ns(el.tag) == "Activity"), None)
    if activity is None:
        raise UnsupportedFile("Няма Activity елемент в TCX файла.")
    sport_attr = (activity.get("Sport") or "").lower()
    sport = "run" if "run" in sport_attr else "bike" if "bik" in sport_attr or "cycl" in sport_attr else None

    moving_s = distance_m = 0.0
    hrs: list[float] = []
    watts: list[float] = []
    start = None
    for el in activity.iter():
        t = _strip_ns(el.tag)
        if t == "Lap" and start is None and el.get("StartTime"):
            start = _parse_time(el.get("StartTime"))
        elif t == "TotalTimeSeconds" and el.text:
            moving_s += float(el.text)
        elif t == "DistanceMeters" and el.text:
            distance_m = max(distance_m, float(el.text))
        elif t == "HeartRateBpm":
            v = next((c.text for c in el if _strip_ns(c.tag) == "Value"), None)
            if v:
                hrs.append(float(v))
        elif t == "Watts" and el.text:
            watts.append(float(el.text))
    if moving_s <= 0:
        raise UnsupportedFile("TCX файлът няма продължителност.")
    if sport is None:
        sport = _infer_sport(distance_m, moving_s)
    return _summary(sport, start, moving_s, distance_m, hrs, watts, raw, name)


def parse_gpx(raw: bytes, name: str) -> dict:
    root = ET.fromstring(raw)
    pts = [el for el in root.iter() if _strip_ns(el.tag) == "trkpt"]
    if not pts:
        raise UnsupportedFile("GPX файлът няма трак точки.")
    type_el = next((el for el in root.iter() if _strip_ns(el.tag) == "type"), None)
    type_txt = (type_el.text or "").lower() if type_el is not None else ""
    sport = "run" if "run" in type_txt else "bike" if "bik" in type_txt or "cycl" in type_txt else None

    times: list[dt.datetime] = []
    hrs: list[float] = []
    distance_m = 0.0
    prev = None
    for pt in pts:
        lat, lon = pt.get("lat"), pt.get("lon")
        if prev and lat and lon:
            distance_m += _haversine_m(float(prev[0]), float(prev[1]), float(lat), float(lon))
        if lat and lon:
            prev = (lat, lon)
        for el in pt.iter():
            t = _strip_ns(el.tag)
            if t == "time" and el.text:
                times.append(_parse_time(el.text))
            elif t == "hr" and el.text:
                hrs.append(float(el.text))
    if len(times) < 2:
        raise UnsupportedFile("GPX файлът няма времеви данни.")
    moving_s = (times[-1] - times[0]).total_seconds()
    if sport is None:
        sport = _infer_sport(distance_m, moving_s)
    return _summary(sport, times[0], moving_s, distance_m, hrs, [], raw, name)


def _infer_sport(distance_m: float, moving_s: float) -> str:
    """No sport tag? Above ~16 km/h sustained it's almost certainly a ride."""
    if distance_m and moving_s:
        kmh = distance_m / 1000 / (moving_s / 3600)
        return "bike" if kmh >= 16 else "run"
    return "run"


def parse_activity_file(filename: str, raw: bytes) -> dict:
    low = filename.lower()
    if low.endswith(".tcx"):
        return parse_tcx(raw, filename)
    if low.endswith(".gpx"):
        return parse_gpx(raw, filename)
    if low.endswith(".fit"):
        raise UnsupportedFile(
            "FIT файловете още не се поддържат директно — експортирай TCX/GPX от "
            "Garmin Connect (⚙️ → Export), или ползвай intervals.icu синхронизацията."
        )
    raise UnsupportedFile("Поддържани формати: .tcx и .gpx.")
