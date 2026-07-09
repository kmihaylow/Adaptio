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
  bike_goal_type?: "ftp" | "endurance" | "vo2max" | "general" | "mixed" | null;
  race?: { name: string; date: string } | null;
  weeks?: number | null;
}

export interface Profile {
  sport: Sport;
  age: number;
  sex: "male" | "female" | "other";
  weight_kg: number;
  height_cm?: number | null;
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
  training_level?: "beginner" | "occasional" | "regular" | "athlete" | null;
  strength_enabled: boolean;
  strength_setting?: "home" | "dumbbells" | "gym";
  stretching_enabled: boolean;
  rest_today?: boolean;
  equipment: Equipment;
  goal: Goal;
}

export interface Exercise {
  name: string;
  sets: number;
  reps: string;
  note: string;
  demo_url: string;
}

export interface ComparisonRow {
  metric: string;
  planned: string;
  actual: string;
  verdict: "ok" | "over" | "under";
  comment: string;
}

export interface LastAnalysis {
  workout: { id: number; name: string; kind: string; sport: string; date: string;
             duration_min: number; description: string };
  actual: ActualActivity;
  comparison: ComparisonRow[];
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

export interface ActualActivity {
  activity_id: string;
  date: string;
  sport: "run" | "bike";
  name: string | null;
  moving_time_min: number;
  distance_km: number | null;
  avg_hr: number | null;
  avg_watts: number | null;
  pace_s_per_km: number | null;
  load: number | null;
}

export interface Workout {
  id: number;
  plan_week: number;
  day_of_week: number;
  date: string;
  sport: "run" | "bike" | "strength" | "stretching";
  name: string;
  kind: string;
  duration_min: number;
  description: string;
  segments: Segment[];
  exercises?: Exercise[];
  status: "planned" | "done" | "skipped";
  load_hint: number;
  actual?: ActualActivity | null;
  rated?: boolean;
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
