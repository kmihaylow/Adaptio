import { useState } from "react";
import type { Workout } from "../types";
import { api } from "../api";

/** Оценка на тренировка (изискване т.6) — RPE + усещане; сървърът адаптира плана. */
export default function RatingSheet({
  wo,
  onClose,
  onDone,
}: {
  wo: Workout;
  onClose: () => void;
  onDone: (coachMessage: string | null) => void;
}) {
  const [rpe, setRpe] = useState(0);
  const [feel, setFeel] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  async function submit() {
    if (!rpe || !feel) return;
    setBusy(true);
    try {
      const r = await api.rate(wo.id, rpe, feel);
      onDone(r.coach_message);
    } catch (e: any) {
      setErr(e.message);
      setBusy(false);
    }
  }

  return (
    <div className="sheet-back" onClick={onClose}>
      <div className="sheet" onClick={(e) => e.stopPropagation()}>
        <h2>Как беше „{wo.name}“?</h2>
        <p className="sub">Колко тежка ти се стори? (1 = разходка, 10 = на предела)</p>
        <div className="rpe-row">
          {Array.from({ length: 10 }, (_, i) => i + 1).map((n) => (
            <button key={n} className={rpe === n ? "on" : ""} onClick={() => setRpe(n)}>
              {n}
            </button>
          ))}
        </div>
        <div className="opts">
          {[
            ["too_easy", "😴 Твърде лека"],
            ["ok", "💪 Точно колкото трябва"],
            ["too_hard", "🥵 Прекалено тежка"],
          ].map(([v, label]) => (
            <button key={v} className={`opt ${feel === v ? "selected" : ""}`} onClick={() => setFeel(v)}>
              {label}
            </button>
          ))}
        </div>
        {err && <p className="sub mt" style={{ color: "var(--danger)" }}>{err}</p>}
        <button className="btn mt" disabled={!rpe || !feel || busy} onClick={submit}>
          {busy ? "Записвам…" : "Запази оценката"}
        </button>
      </div>
    </div>
  );
}
