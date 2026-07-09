import type { ActualActivity, ComparisonRow, Dashboard, LastAnalysis, Plan, Profile, Workout } from "./types";

const TOKEN_KEY = "adaptio_token";
export const getToken = () => localStorage.getItem(TOKEN_KEY);
export const setToken = (t: string) => localStorage.setItem(TOKEN_KEY, t);
export const clearToken = () => localStorage.removeItem(TOKEN_KEY);

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const token = getToken();
  let r: Response;
  try {
    r = await fetch(path, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...init?.headers,
      },
    });
  } catch {
    throw new Error("Сървърът не отговаря — увери се, че backend-ът е стартиран (python -m adaptio.main).");
  }
  if (r.status === 401 && token && !path.startsWith("/api/auth/")) {
    // stale session: drop the token and land back on the login screen
    clearToken();
    window.location.reload();
  }
  if (!r.ok) {
    let detail = `Грешка ${r.status}`;
    try {
      const j = await r.json();
      if (j.detail) detail = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail);
    } catch {
      if (r.status === 404)
        detail = "Сървърът не намери ресурса — провери дали backend-ът работи на порт 8000.";
      else if (r.status >= 500)
        detail = "Вътрешна грешка на сървъра — провери конзолата на backend-а за детайли.";
    }
    throw new Error(detail);
  }
  return r.json();
}

export const api = {
  checkHealth: async () => {
    try {
      const r = await fetch("/api/health");
      return r.ok;
    } catch {
      return false;
    }
  },
  register: (username: string, password: string) =>
    req<{ token: string; username: string }>("/api/auth/register", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    }),
  login: (username: string, password: string) =>
    req<{ token: string; username: string }>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    }),
  logout: () => req<{ ok: boolean }>("/api/auth/logout", { method: "POST" }),
  me: () => req<{ user_id: string }>("/api/auth/me"),
  dashboard: () => req<Dashboard>("/api/dashboard"),
  updateMetrics: (m: Record<string, number | null>) =>
    req<{ saved: boolean; zones: Record<string, any> }>("/api/profile/metrics", {
      method: "POST",
      body: JSON.stringify(m),
    }),
  getProfile: () => req<Profile>("/api/profile"),
  saveProfile: (p: Profile) =>
    req<{ saved: boolean; plan_weeks: number; warnings: string[] }>("/api/profile", {
      method: "POST",
      body: JSON.stringify(p),
    }),
  generatePlan: () =>
    req<{ plan_id: number; weeks: number; warnings: string[] }>("/api/plan/generate", { method: "POST" }),
  getPlan: () => req<Plan>("/api/plan"),
  today: () =>
    req<{ today: Workout[]; upcoming: Workout[]; zones: Record<string, any> }>("/api/workouts/today"),
  setStatus: (id: number, status: string) =>
    req(`/api/workouts/${id}/status`, { method: "POST", body: JSON.stringify({ status }) }),
  rate: (id: number, rpe: number, feel: string, comment?: string) =>
    req<{ ok: boolean; coach_message: string | null; adjusted_workouts: number }>(
      `/api/workouts/${id}/rating`,
      { method: "POST", body: JSON.stringify({ rpe, feel, comment }) },
    ),
  connectIntervals: (api_key: string, athlete_id: string) =>
    req<{ connected: boolean }>("/api/integrations/intervals", {
      method: "POST",
      body: JSON.stringify({ api_key, athlete_id }),
    }),
  intervalsStatus: () => req<{ connected: boolean }>("/api/integrations/intervals"),
  syncActivities: () =>
    req<{ synced: number; matched: { workout: string; activity: string; date: string }[]; messages: string[] }>(
      "/api/sync/activities", { method: "POST" },
    ),
  uploadActivity: async (file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    const token = getToken();
    const r = await fetch("/api/sync/upload", {
      method: "POST",
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: fd,
    });
    if (!r.ok) {
      let detail = `Грешка ${r.status}`;
      try { const j = await r.json(); if (j.detail) detail = j.detail; } catch {}
      throw new Error(detail);
    }
    return r.json() as Promise<{ synced: number; messages: string[];
      activity: ActualActivity; analysis: ComparisonRow[] }>;
  },
  analysisAdhocAI: (activity: ActualActivity) =>
    req<{ verdict: string; execution_score: number; strengths: string[];
          improvements: string[]; next_advice: string }>(
      "/api/analysis/adhoc/ai",
      { method: "POST", body: JSON.stringify({ activity }) },
    ),
  analysisLast: () => req<LastAnalysis>("/api/analysis/last"),
  analysisAI: () =>
    req<{ verdict: string; execution_score: number; strengths: string[];
          improvements: string[]; next_advice: string }>(
      "/api/analysis/last/ai", { method: "POST" },
    ),
  adjustTime: (id: number, factor: number) =>
    req<{ ok: boolean; duration_min: number }>(`/api/workouts/${id}/time`, {
      method: "POST",
      body: JSON.stringify({ factor }),
    }),
  pushWeek: (week: number) =>
    req<{ pushed: number }>(`/api/integrations/intervals/push-week/${week}`, { method: "POST" }),
  coachReview: (note: string) =>
    req<{ assessment: string; advice: string; adjusted_workouts: number }>("/api/coach/review", {
      method: "POST",
      body: JSON.stringify({ note }),
    }),
};

export const fmtPace = (s: number) => `${Math.floor(s / 60)}:${String(Math.round(s) % 60).padStart(2, "0")}`;

export function segmentTarget(seg: { target_kind: string; low: number; high: number }, ftp?: number): string {
  switch (seg.target_kind) {
    case "power": {
      if (ftp) {
        const lo = Math.round(seg.low * ftp), hi = Math.round(seg.high * ftp);
        return lo === hi ? `${lo}W` : `${lo}–${hi}W`;
      }
      return `${Math.round(seg.low * 100)}–${Math.round(seg.high * 100)}% FTP`;
    }
    case "pace":
      return `${fmtPace(seg.high)}–${fmtPace(seg.low)} /км`;
    case "hr":
      return `${Math.round(seg.low)}–${Math.round(seg.high)} уд/мин`;
    default:
      return `RPE ${Math.round(seg.low)}–${Math.round(seg.high)}/10`;
  }
}
