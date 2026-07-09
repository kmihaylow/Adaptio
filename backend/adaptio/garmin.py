"""Direct Garmin Connect integration via the community `garminconnect` library.

IMPORTANT CAVEAT (surfaced in the UI too): this is the UNOFFICIAL API — the
same one the Garmin Connect app uses, accessed with the athlete's own
email/password. It works well in practice but Garmin can change it anytime,
and accounts with two-factor auth need an extra code. The official Developer
Program integration replaces this when Garmin reopens applications.

Activities are mapped to the same compact summary shape as intervals.icu ones,
so the one matching pipeline (activity_sync) serves all three sources:
intervals.icu, direct Garmin, manual file upload.
"""

from __future__ import annotations

import datetime as dt


class GarminError(Exception):
    pass


class GarminClient:
    def __init__(self, email: str, password: str):
        self.email = email
        self.password = password
        self._api = None

    def _login(self):
        if self._api is not None:
            return self._api
        try:
            from garminconnect import Garmin
            api = Garmin(self.email, self.password)
            api.login()
        except Exception as e:
            msg = str(e)
            if "MFA" in msg or "mfa" in msg or "verification" in msg.lower():
                raise GarminError(
                    "Акаунтът изисква двустепенна верификация (MFA) — тя не се поддържа "
                    "оттук. Изключи я временно или ползвай intervals.icu моста."
                )
            raise GarminError("Неуспешен вход в Garmin Connect — провери имейла и паролата.")
        self._api = api
        return api

    def check(self) -> dict:
        api = self._login()
        try:
            name = api.get_full_name()
        except Exception:
            name = self.email
        return {"name": name}

    def activities(self, days: int = 14) -> list[dict]:
        """Recent completed activities as compact summaries."""
        api = self._login()
        try:
            rows = api.get_activities(0, 30)
        except Exception:
            raise GarminError("Garmin Connect не върна активностите — опитай пак по-късно.")
        cutoff = dt.date.today() - dt.timedelta(days=days)
        out = []
        for a in rows:
            type_key = ((a.get("activityType") or {}).get("typeKey") or "").lower()
            sport = ("run" if "running" in type_key
                     else "bike" if "cycling" in type_key or "biking" in type_key else None)
            if not sport:
                continue
            start = (a.get("startTimeLocal") or "")[:10]
            if not start or dt.date.fromisoformat(start) < cutoff:
                continue
            moving_s = a.get("movingDuration") or a.get("duration") or 0
            dist_m = a.get("distance") or 0
            pace = round(moving_s / (dist_m / 1000)) if sport == "run" and dist_m > 100 and moving_s else None
            out.append({
                "activity_id": "garmin_" + str(a.get("activityId")),
                "date": start,
                "sport": sport,
                "name": a.get("activityName"),
                "moving_time_min": round(moving_s / 60),
                "distance_km": round(dist_m / 1000, 2) if dist_m else None,
                "avg_hr": a.get("averageHR"),
                "avg_watts": a.get("avgPower"),
                "pace_s_per_km": pace,
                "load": a.get("activityTrainingLoad") and round(a["activityTrainingLoad"]),
            })
        return out
