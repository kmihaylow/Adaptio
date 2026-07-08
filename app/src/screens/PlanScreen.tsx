import { useEffect, useMemo, useState } from "react";
import type { Plan, Workout } from "../types";
import { api } from "../api";
import WorkoutCard from "../components/WorkoutCard";
import RatingSheet from "../components/RatingSheet";

const PHASE_BG: Record<string, string> = {
  base: "База", build: "Изграждане", peak: "Пик", recovery: "Възстановяване", taper: "Тейпър",
};

export default function PlanScreen() {
  const [plan, setPlan] = useState<Plan | null>(null);
  const [week, setWeek] = useState<number | null>(null);
  const [rating, setRating] = useState<Workout | null>(null);
  const [coachMsg, setCoachMsg] = useState<string | null>(null);
  const [err, setErr] = useState("");

  async function load() {
    try {
      const p = await api.getPlan();
      setPlan(p);
      if (week === null) {
        const today = new Date().toISOString().slice(0, 10);
        const cur = p.workouts.find((w) => w.date >= today);
        setWeek(cur ? cur.plan_week : 1);
      }
    } catch (e: any) { setErr(e.message); }
  }
  useEffect(() => { load(); }, []);

  const byWeek = useMemo(() => {
    if (!plan || week === null) return [];
    return plan.workouts
      .filter((w) => w.plan_week === week)
      .sort((a, b) => a.date.localeCompare(b.date));
  }, [plan, week]);

  if (err) return (
    <div className="screen">
      <div className="warning">⚠️ <span>{err}</span></div>
      <button className="btn mt" onClick={() => { setErr(""); load(); }}>Опитай отново</button>
    </div>
  );
  if (!plan || week === null) return <div className="screen center"><span className="spin">⚙️</span></div>;

  const wk = plan.weeks.find((w) => w.number === week)!;
  const done = plan.workouts.filter((w) => w.status === "done").length;
  const totalH = byWeek.reduce((a, w) => a + w.duration_min, 0) / 60;

  return (
    <div className="screen">
      <h1>Програма</h1>
      <div className="stat-row mt">
        <div className="stat"><div className="v">{plan.weeks.length}</div><div className="l">седмици</div></div>
        <div className="stat"><div className="v">{done}/{plan.workouts.length}</div><div className="l">направени</div></div>
        <div className="stat"><div className="v">{totalH.toFixed(1)}ч</div><div className="l">тази седмица</div></div>
      </div>

      {plan.warnings.map((w, i) => <div className="warning" key={i}>⚠️ <span>{w}</span></div>)}
      {coachMsg && <div className="coach-note" onClick={() => setCoachMsg(null)}>🧠 {coachMsg}</div>}

      <div style={{ display: "flex", gap: 6, overflowX: "auto", padding: "4px 0 10px" }}>
        {plan.weeks.map((w) => (
          <button key={w.number} className={`btn small ${w.number === week ? "" : "ghost"}`}
            style={{ flexShrink: 0 }} onClick={() => setWeek(w.number)}>
            {w.number}
          </button>
        ))}
      </div>

      <div className="week-head">
        <h2 style={{ margin: 0 }}>Седмица {wk.number}</h2>
        <span className={`phase ${wk.phase}`}>{PHASE_BG[wk.phase]}</span>
      </div>
      <p className="sub" style={{ marginBottom: 12 }}>{wk.focus}</p>

      {byWeek.map((wo) => (
        <WorkoutCard key={wo.id} wo={wo} ftp={plan.zones.ftp_w} onRate={setRating}
          onSkip={async (w) => { await api.setStatus(w.id, "skipped"); load(); }} />
      ))}

      {rating && (
        <RatingSheet wo={rating} onClose={() => setRating(null)}
          onDone={(msg) => { setRating(null); setCoachMsg(msg); load(); }} />
      )}
    </div>
  );
}
