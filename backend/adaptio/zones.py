"""Training-zone science.

Running paces follow Jack Daniels' VDOT model (Daniels & Gilbert, "Oxygen Power",
1979; Daniels' Running Formula, 3rd ed.). Cycling power zones follow Coggan
(Allen & Coggan, "Training and Racing with a Power Meter"). Heart-rate zones are
derived from LTHR when known (Coggan/Friel), otherwise from max HR, which itself
falls back to the Tanaka formula 208 − 0.7·age (Tanaka et al., JACC 2001).
"""

from __future__ import annotations

import math

from .models import Profile, RecentRace, RUN_DISTANCE_M

# ---------------------------------------------------------------- VDOT (Daniels)


def _vo2_at_velocity(v_m_min: float) -> float:
    return -4.60 + 0.182258 * v_m_min + 0.000104 * v_m_min**2


def _pct_vo2max_at_duration(t_min: float) -> float:
    return 0.8 + 0.1894393 * math.exp(-0.012778 * t_min) + 0.2989558 * math.exp(-0.1932605 * t_min)


def vdot_from_race(distance_m: float, time_s: float) -> float:
    t_min = time_s / 60.0
    v = distance_m / t_min
    return _vo2_at_velocity(v) / _pct_vo2max_at_duration(t_min)


def velocity_at_pct_vdot(vdot: float, pct: float) -> float:
    """Solve the Daniels quadratic for velocity (m/min) at a %VDOT."""
    target = pct * vdot
    a, b, c = 0.000104, 0.182258, -(4.60 + target)
    return (-b + math.sqrt(b * b - 4 * a * c)) / (2 * a)


def pace_s_per_km(vdot: float, pct: float) -> int:
    return round(1000 / velocity_at_pct_vdot(vdot, pct) * 60)


def riegel_predict(t1_s: float, d1_m: float, d2_m: float) -> float:
    """Predict a race time at another distance (Riegel, 1981; exponent 1.06)."""
    return t1_s * (d2_m / d1_m) ** 1.06


def run_paces(vdot: float) -> dict:
    """Daniels training paces in s/km. Ranges give the athlete room to breathe."""
    return {
        "easy": [pace_s_per_km(vdot, 0.62), pace_s_per_km(vdot, 0.72)],
        "marathon": [pace_s_per_km(vdot, 0.82), pace_s_per_km(vdot, 0.86)],
        "threshold": [pace_s_per_km(vdot, 0.86), pace_s_per_km(vdot, 0.90)],
        "interval": [pace_s_per_km(vdot, 0.95), pace_s_per_km(vdot, 1.00)],
        "repetition": [pace_s_per_km(vdot, 1.02), pace_s_per_km(vdot, 1.08)],
    }


# ------------------------------------------------------------- cycling (Coggan)

POWER_ZONES = {
    "z1_recovery": (0.0, 0.55),
    "z2_endurance": (0.56, 0.75),
    "z3_tempo": (0.76, 0.87),
    "sweet_spot": (0.88, 0.94),
    "z4_threshold": (0.95, 1.05),
    "z5_vo2max": (1.06, 1.20),
    "z6_anaerobic": (1.21, 1.50),
}


def power_zones_w(ftp_w: int) -> dict:
    return {k: [round(lo * ftp_w), round(hi * ftp_w)] for k, (lo, hi) in POWER_ZONES.items()}


# ------------------------------------------------------------------- heart rate

LTHR_ZONES = {  # Friel/Coggan, % of LTHR
    "z1_recovery": (0.60, 0.81),
    "z2_endurance": (0.81, 0.89),
    "z3_tempo": (0.90, 0.93),
    "z4_threshold": (0.94, 0.99),
    "z5_vo2max": (1.00, 1.06),
}

MAXHR_ZONES = {  # % of max HR fallback
    "z1_recovery": (0.50, 0.60),
    "z2_endurance": (0.60, 0.70),
    "z3_tempo": (0.70, 0.80),
    "z4_threshold": (0.80, 0.90),
    "z5_vo2max": (0.90, 1.00),
}


def estimated_max_hr(age: int) -> int:
    return round(208 - 0.7 * age)  # Tanaka et al. 2001


def hr_zones_bpm(profile: Profile) -> dict:
    if profile.lthr_bpm:
        base, table = profile.lthr_bpm, LTHR_ZONES
    else:
        base, table = profile.max_hr_bpm or estimated_max_hr(profile.age), MAXHR_ZONES
    return {k: [round(lo * base), round(hi * base)] for k, (lo, hi) in table.items()}


# -------------------------------------------------------- filling in the blanks


def resolve_vdot(profile: Profile) -> tuple[float, str]:
    """Best available VDOT + a note about where it came from."""
    if profile.recent_race:
        r: RecentRace = profile.recent_race
        return vdot_from_race(RUN_DISTANCE_M[r.distance], r.time_s), "recent race result"
    if profile.vo2max:
        # Lab/watch VO2max runs slightly above race-derived VDOT (running economy).
        return profile.vo2max * 0.95, "reported VO2max (scaled)"
    goal = profile.goal
    if goal.target_time_s and goal.run_distance:
        # Assume the goal is an ambitious-but-plausible ~5% improvement over current shape.
        current = goal.target_time_s * 1.05
        return vdot_from_race(RUN_DISTANCE_M[goal.run_distance], current), "inferred from goal time"
    if goal.target_pace_s_per_km and goal.run_distance:
        time_s = goal.target_pace_s_per_km * RUN_DISTANCE_M[goal.run_distance] / 1000 * 1.05
        return vdot_from_race(RUN_DISTANCE_M[goal.run_distance], time_s), "inferred from goal pace"
    # Conservative default for an untested amateur; the plan self-corrects via ratings.
    base = 38.0 if profile.sex.value == "male" else 34.0
    base -= max(0, (profile.age - 30)) * 0.15
    return max(25.0, base), "conservative default (no test data)"


def resolve_ftp(profile: Profile) -> tuple[int, str]:
    if profile.ftp_w:
        return profile.ftp_w, "reported FTP"
    # ~2.2 W/kg is a sane starting estimate for an untested amateur.
    per_kg = 2.2 if profile.sex.value == "male" else 2.0
    return round(profile.weight_kg * per_kg), "estimated from weight (do an FTP test!)"


def resolve_zones(profile: Profile) -> dict:
    """Snapshot of every zone system the plan may reference."""
    zones: dict = {"hr_bpm": hr_zones_bpm(profile)}
    zones["max_hr_bpm"] = profile.max_hr_bpm or estimated_max_hr(profile.age)
    zones["max_hr_estimated"] = profile.max_hr_bpm is None
    if profile.sport.value in ("run", "both"):
        vdot, src = resolve_vdot(profile)
        zones["vdot"] = round(vdot, 1)
        zones["vdot_source"] = src
        zones["run_paces_s_per_km"] = run_paces(vdot)
    if profile.sport.value in ("bike", "both"):
        ftp, src = resolve_ftp(profile)
        zones["ftp_w"] = ftp
        zones["ftp_source"] = src
        zones["power_zones_w"] = power_zones_w(ftp)
    return zones
