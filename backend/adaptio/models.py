"""Pydantic models shared by the API and the plan engine."""

from __future__ import annotations

import datetime as dt
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class Sport(str, Enum):
    run = "run"
    bike = "bike"
    both = "both"


class Sex(str, Enum):
    male = "male"
    female = "female"
    other = "other"


class RunGoalType(str, Enum):
    race_time = "race_time"      # finish a distance in a target time
    race_pace = "race_pace"      # hold a target pace for a distance
    finish = "finish"            # just complete the distance
    general = "general"          # get fitter / faster overall


class BikeGoalType(str, Enum):
    ftp = "ftp"                  # raise FTP
    endurance = "endurance"      # ride longer / aerobic base
    vo2max = "vo2max"            # raise VO2max / top-end
    general = "general"          # stay in good shape, no single focus
    mixed = "mixed"              # develop all three systems in rotation


class TrainingLevel(str, Enum):
    """Training background — decides how aggressively the plan starts and ramps."""
    beginner = "beginner"        # not training now / just starting
    occasional = "occasional"    # 1-2 unstructured sessions a week
    regular = "regular"          # 3-4 structured sessions a week, consistent
    athlete = "athlete"          # years of training, race experience, 5+ sessions


class RunDistance(str, Enum):
    five_k = "5k"
    ten_k = "10k"
    half = "half_marathon"
    marathon = "marathon"


RUN_DISTANCE_M = {
    RunDistance.five_k: 5000,
    RunDistance.ten_k: 10000,
    RunDistance.half: 21097,
    RunDistance.marathon: 42195,
}


class Equipment(BaseModel):
    """What the athlete owns — decides how workouts are targeted (watts / HR / RPE)."""
    power_meter: bool = False
    smart_trainer: bool = False
    hr_monitor: bool = False        # chest strap or reliable wrist HR
    smartwatch: bool = False
    gps_watch: bool = False

    @property
    def has_power(self) -> bool:
        return self.power_meter or self.smart_trainer

    @property
    def has_hr(self) -> bool:
        return self.hr_monitor or self.smartwatch


class RaceInfo(BaseModel):
    name: str
    date: dt.date


class Goal(BaseModel):
    # Running
    run_goal_type: Optional[RunGoalType] = None
    run_distance: Optional[RunDistance] = None
    target_time_s: Optional[int] = None          # for race_time
    target_pace_s_per_km: Optional[int] = None   # for race_pace
    # Cycling
    bike_goal_type: Optional[BikeGoalType] = None
    # Shared
    race: Optional[RaceInfo] = None              # training for a specific event?
    weeks: Optional[int] = Field(None, ge=2, le=52)  # otherwise: weeks-to-results slider


class RecentRace(BaseModel):
    """A recent race/test result — the most reliable fitness signal for running."""
    distance: RunDistance
    time_s: int


class Profile(BaseModel):
    sport: Sport
    age: int = Field(..., ge=10, le=100)
    sex: Sex = Sex.male
    weight_kg: float = Field(..., ge=30, le=250)
    height_cm: Optional[float] = Field(None, ge=100, le=250)
    # Physiology (all optional — we estimate what's missing)
    max_hr_bpm: Optional[int] = Field(None, ge=120, le=230)
    resting_hr_bpm: Optional[int] = Field(None, ge=25, le=110)
    vo2max: Optional[float] = Field(None, ge=15, le=95)
    ftp_w: Optional[int] = Field(None, ge=50, le=600)
    lthr_bpm: Optional[int] = Field(None, ge=100, le=220)
    recent_race: Optional[RecentRace] = None
    # Availability
    weekly_hours: float = Field(..., ge=1, le=30)
    available_days: list[int] = Field(default_factory=lambda: [0, 1, 3, 5, 6])  # 0=Mon
    # Context
    experience_years: float = 0
    currently_training: bool = False  # legacy bool; training_level supersedes it
    training_level: Optional[TrainingLevel] = None
    strength_enabled: bool = False    # add 1-2 short strength sessions weekly?
    stretching_enabled: bool = False  # add short stretching/mobility sessions?

    @property
    def level(self) -> TrainingLevel:
        """Resolved level, mapping old profiles that only have the bool."""
        if self.training_level:
            return self.training_level
        return TrainingLevel.regular if self.currently_training else TrainingLevel.beginner
    equipment: Equipment = Field(default_factory=Equipment)
    goal: Goal = Field(default_factory=Goal)


class SegmentType(str, Enum):
    warmup = "warmup"
    steady = "steady"
    interval_on = "interval_on"
    interval_off = "interval_off"
    cooldown = "cooldown"


class TargetKind(str, Enum):
    power = "power"   # % FTP → watts
    hr = "hr"         # heart-rate zone
    pace = "pace"     # s/km range
    rpe = "rpe"       # perceived effort 1–10


class Segment(BaseModel):
    type: SegmentType
    duration_s: int
    target_kind: TargetKind
    # power: fraction of FTP; pace: s/km; hr: bpm; rpe: 1-10
    low: float
    high: float
    cadence_rpm: Optional[int] = None
    note: Optional[str] = None


class Exercise(BaseModel):
    """One strength-catalog movement with a form-demo link."""
    name: str
    sets: int
    reps: str                         # "8-10" or "30 сек"
    note: str = ""
    demo_url: str = ""


class Workout(BaseModel):
    id: Optional[int] = None
    plan_week: int                    # 1-based
    day_of_week: int                  # 0=Mon
    date: Optional[dt.date] = None
    sport: str                        # "run" | "bike" | "strength"
    name: str
    kind: str                         # endurance | tempo | threshold | vo2max | long | recovery | intervals | race
    duration_min: int
    description: str = ""
    segments: list[Segment] = Field(default_factory=list)
    exercises: list[Exercise] = Field(default_factory=list)  # strength sessions only
    status: str = "planned"           # planned | done | skipped
    load_hint: int = 0                # rough TSS-like number for progress charts
    actual: Optional[dict] = None     # synced intervals.icu activity summary


class WorkoutRating(BaseModel):
    rpe: int = Field(..., ge=1, le=10)
    feel: str = Field(..., pattern="^(too_easy|ok|too_hard)$")
    comment: Optional[str] = None


class PlanWeek(BaseModel):
    number: int
    phase: str                        # base | build | peak | taper | recovery
    focus: str
    target_hours: float


class Plan(BaseModel):
    id: Optional[int] = None
    sport: Sport
    weeks: list[PlanWeek]
    workouts: list[Workout]
    warnings: list[str] = Field(default_factory=list)
    zones: dict = Field(default_factory=dict)   # resolved training zones snapshot
    created_at: Optional[str] = None
