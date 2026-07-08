export type Sport = "run" | "bike" | "both";

export interface Equipment {
  power_meter: boolean;
  smart_trainer: boolean;
  hr_monitor: boolean;
  smartwatch: boolean;
  gps_watch: boolean;
}

export interface Goal {
  run_goal_type?: "race_time" | "race_pace" | "finish" | "general" | null;
  run_distance?: "5k" | "10k" | "half_marathon" | "marathon" | null;
  target_time_s?: number | null;
  target_pace_s_per_km?: number | null;
  bike_goal_type?: "ftp" | "endurance" | "vo2max" | null;
  race?: { name: string; date: string } | null;
  weeks?: number | null;
}

export interface Profile {
  sport: Sport;
  age: number;
  sex: "male" | "female" | "other";
  weight_kg: number;
  max_hr_bpm?: number | null;
  resting_hr_bpm?: number | null;
  vo2max?: number | null;
  ftp_w?: number | null;
  lthr_bpm?: number | null;
  recent_race?: { distance: string; time_s: number } | null;
  weekly_hours: number;
  available_days: number[];
  experience_years: number;
  currently_training: boolean;
  equipment: Equipment;
  goal: Goal;
}

export interface WeeklyProgress {
  week: number;
  phase: string;
  planned: number;
  done: number;
  load_done: number;
  load_planned: number;
}

export interface Dashboard {
  current_week: number;
  total_weeks: number;
  phase: "base" | "build" | "peak" | "recovery" | "taper";
  done: number;
  skipped: number;
  total: number;
  missed: number;
  weekly: WeeklyProgress[];
  avg_rpe: number | null;
  ratings_count: number;
  focus: string[];
  race: { name: string; date: string } | null;
  days_to_race: number | null;
  zones: Record<string, any>;
}

export interface Segment {
  type: "warmup" | "steady" | "interval_on" | "interval_off" | "cooldown";
  duration_s: number;
  target_kind: "power" | "hr" | "pace" | "rpe";
  low: number;
  high: number;
  cadence_rpm?: number | null;
  note?: string | null;
}

export interface Workout {
  id: number;
  plan_week: number;
  day_of_week: number;
  date: string;
  sport: "run" | "bike";
  name: string;
  kind: string;
  duration_min: number;
  description: string;
  segments: Segment[];
  status: "planned" | "done" | "skipped";
  load_hint: number;
}

export interface PlanWeek {
  number: number;
  phase: "base" | "build" | "peak" | "recovery" | "taper";
  focus: string;
  target_hours: number;
}

export interface Plan {
  plan_id: number;
  sport: Sport;
  weeks: PlanWeek[];
  warnings: string[];
  zones: Record<string, any>;
  workouts: Workout[];
  created_at: string;
}
