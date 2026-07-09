import { useState } from "react";
import type { Workout } from "../types";
import { fmtPace, segmentTarget } from "../api";

const SEG_COLOR: Record<string, string> = {
  warmup: "#4cc9f0",
  cooldown: "#4cc9f0",
  steady: "#6ede8a",
  interval_on: "#ff6b35",
  interval_off: "#3a4356",
};

function intensity(seg: { target_kind: string; low: number; high: number; type: string }): number {
  // rough visual height 0..1 per segment for the structure strip
  if (seg.target_kind === "power") return Math.min(1, seg.high / 1.2);
  if (seg.target_kind === "rpe") return seg.high / 10;
  if (seg.target_kind === "hr") return Math.min(1, seg.high / 190);
  // pace: faster (fewer s/km) = taller; 240s=fast, 480s=easy
  return Math.min(1, Math.max(0.2, (500 - seg.high) / 260));
}

export default function WorkoutCard({
  wo,
  ftp,
  onRate,
  onSkip,
  expandable = true,
}: {
  wo: Workout;
  ftp?: number;
  onRate?: (wo: Workout) => void;
  onSkip?: (wo: Workout) => void;
  expandable?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const total = wo.segments.reduce((a, s) => a + s.duration_s, 0) || 1;
  const dateStr = new Date(wo.date + "T00:00:00").toLocaleDateString("bg-BG", {
    weekday: "short",
    day: "numeric",
    month: "short",
  });

  return (
    <div className={`card wo ${wo.sport}`} onClick={() => expandable && setOpen(!open)}>
      <div className="wo-head">
        <div>
          <span className="badge">
            {wo.sport === "run" ? "🏃 Бягане" : wo.sport === "bike" ? "🚴 Колоездене"
              : wo.sport === "stretching" ? "🧘 Стречинг" : "💪 Силова"}
          </span>
          {wo.status !== "planned" && (
            <span className={`badge ${wo.status}`}>{wo.status === "done" ? "Готова" : "Пропусната"}</span>
          )}
          <div className="wo-name">{wo.name}</div>
        </div>
        <div className="wo-meta">
          {dateStr}
          <br />
          {wo.duration_min} мин
        </div>
      </div>
      {wo.segments.length > 0 && (
        <div className="seg-strip">
          {wo.segments.map((s, i) => (
            <div
              key={i}
              style={{
                width: `${(s.duration_s / total) * 100}%`,
                height: `${20 + intensity(s) * 80}%`,
                background: SEG_COLOR[s.type] ?? "#3a4356",
              }}
            />
          ))}
        </div>
      )}
      <p className="wo-desc">{wo.description}</p>
      {wo.actual && (
        <p className="wo-desc" style={{ color: "#6ede8a", marginTop: 6 }}>
          📥 Реално ({wo.actual.name ?? "от Garmin"}): {wo.actual.moving_time_min} мин
          {wo.actual.distance_km ? ` · ${wo.actual.distance_km} км` : ""}
          {wo.actual.pace_s_per_km ? ` · ${fmtPace(wo.actual.pace_s_per_km)}/км` : ""}
          {wo.actual.avg_watts ? ` · ${Math.round(wo.actual.avg_watts)}W` : ""}
          {wo.actual.avg_hr ? ` · ${Math.round(wo.actual.avg_hr)} уд/мин` : ""}
        </p>
      )}
      {open && wo.segments.length > 0 && (
        <ul className="seg-list">
          {wo.segments.map((s, i) => (
            <li key={i}>
              <span>
                <b>{Math.round(s.duration_s / 60)} мин</b> {s.note ?? s.type}
              </span>
              <span>{segmentTarget(s, ftp)}{s.cadence_rpm ? ` · ${s.cadence_rpm}об/мин` : ""}</span>
            </li>
          ))}
        </ul>
      )}
      {open && (wo.exercises?.length ?? 0) > 0 && (
        <ul className="seg-list">
          {wo.exercises!.map((ex, i) => (
            <li key={i} style={{ display: "block" }}>
              <div style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
                <span><b>{ex.name}</b></span>
                <span style={{ whiteSpace: "nowrap" }}>{ex.sets}×{ex.reps}</span>
              </div>
              <div className="hint" style={{ marginTop: 2 }}>
                {ex.note}{" "}
                {ex.demo_url && (
                  <a href={ex.demo_url} target="_blank" rel="noreferrer"
                    onClick={(e) => e.stopPropagation()} style={{ color: "var(--accent)" }}>
                    ▶ демо
                  </a>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
      {!open && (wo.exercises?.length ?? 0) > 0 && (
        <p className="hint" style={{ marginTop: 6 }}>
          Докосни за списъка с упражнения и демо клипове ▾
        </p>
      )}
      {(onRate || onSkip) && wo.status === "planned" && (
        wo.date <= new Date().toLocaleDateString("sv-SE") ? (
          <div style={{ display: "flex", gap: 8, marginTop: 12 }} onClick={(e) => e.stopPropagation()}>
            {onRate && (
              <button className="btn small" onClick={() => onRate(wo)}>
                ✓ Направих я — оцени
              </button>
            )}
            {onSkip && (
              <button className="btn small ghost" onClick={() => onSkip(wo)}>
                Пропускам
              </button>
            )}
          </div>
        ) : (
          <p className="hint" style={{ marginTop: 10 }}>
            🔒 Ще можеш да я отбележиш в деня на тренировката.
          </p>
        )
      )}
      {onRate && wo.status === "done" && wo.actual && !wo.rated && (
        <div style={{ marginTop: 12 }} onClick={(e) => e.stopPropagation()}>
          <button className="btn small" onClick={() => onRate(wo)}>
            💬 Как беше? Оцени я
          </button>
        </div>
      )}
    </div>
  );
}
