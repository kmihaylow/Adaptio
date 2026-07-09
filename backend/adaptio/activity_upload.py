"""Parse manually uploaded FIT/TCX/GPX activity files into the same compact
summary shape that intervals.icu activities use, so the one matching pipeline
(activity_sync.match_activities) handles both sources.

TCX and GPX are plain XML (stdlib). FIT is Garmin's binary native format —
the richest of the three (power, laps, real moving time) and what the watch
actually records, so it gets first-class support via `fitdecode` (pure
Python, no transitive deps).
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


def parse_fit(raw: bytes, name: str) -> dict:
    """FIT: prefer the device's own 'session' summary message; fall back to
    aggregating 'record' messages for stripped-down files."""
    import io

    import fitdecode

    session: dict = {}
    hrs: list[float] = []
    watts: list[float] = []
    times: list[dt.datetime] = []
    distance_m = 0.0
    try:
        with fitdecode.FitReader(io.BytesIO(raw)) as reader:
            for frame in reader:
                if not isinstance(frame, fitdecode.FitDataMessage):
                    continue
                if frame.name == "session":
                    for f in frame.fields:
                        if f.value is not None:
                            session[f.name] = f.value
                elif frame.name == "record":
                    for f in frame.fields:
                        if f.value is None:
                            continue
                        if f.name == "heart_rate":
                            hrs.append(float(f.value))
                        elif f.name == "power":
                            watts.append(float(f.value))
                        elif f.name == "timestamp":
                            times.append(f.value)
                        elif f.name == "distance":
                            distance_m = max(distance_m, float(f.value))
    except fitdecode.FitError as e:
        raise UnsupportedFile(f"FIT файлът не можа да бъде прочетен: {e}")

    sport_txt = str(session.get("sport", "")).lower()
    sport = ("run" if "run" in sport_txt
             else "bike" if "cycl" in sport_txt or "bik" in sport_txt else None)
    moving_s = float(session.get("total_moving_time") or session.get("total_timer_time")
                     or session.get("total_elapsed_time") or 0)
    if not moving_s and len(times) >= 2:
        moving_s = (times[-1] - times[0]).total_seconds()
    if moving_s <= 0:
        raise UnsupportedFile("FIT файлът няма продължителност.")
    distance_m = float(session.get("total_distance") or distance_m or 0)
    start = session.get("start_time") or (times[0] if times else None)
    if isinstance(start, dt.datetime) and start.tzinfo is None:
        start = start.replace(tzinfo=dt.timezone.utc)

    if session.get("avg_heart_rate"):
        hrs = [float(session["avg_heart_rate"])]
    if session.get("avg_power"):
        watts = [float(session["avg_power"])]
    if sport is None:
        sport = _infer_sport(distance_m, moving_s)
    return _summary(sport, start, moving_s, distance_m, hrs, watts, raw, name)


def _infer_sport(distance_m: float, moving_s: float) -> str:
    """No sport tag? Above ~16 km/h sustained it's almost certainly a ride."""
    if distance_m and moving_s:
        kmh = distance_m / 1000 / (moving_s / 3600)
        return "bike" if kmh >= 16 else "run"
    return "run"


def parse_activity_file(filename: str, raw: bytes) -> dict:
    low = filename.lower()
    if low.endswith(".fit"):
        return parse_fit(raw, filename)
    if low.endswith(".tcx"):
        return parse_tcx(raw, filename)
    if low.endswith(".gpx"):
        return parse_gpx(raw, filename)
    raise UnsupportedFile("Поддържани формати: .fit, .tcx и .gpx.")
