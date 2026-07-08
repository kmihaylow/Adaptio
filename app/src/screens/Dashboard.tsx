import { useEffect, useState } from "react";
import type { Dashboard as Dash } from "../types";
import { api } from "../api";

const PHASE_BG: Record<string, string> = {
  base: "База", build: "Изграждане", peak: "Пик", recovery: "Възстановяване", taper: "Тейпър",
};

export default function Dashboard() {
  const [d, setD] = useState<Dash | null>(null);
  const [err, setErr] = useState("");

  async function load() {
    try { setD(await api.dashboard()); } catch (e: any) { setErr(e.message); }
  }
  useEffect(() => { load(); }, []);

  if (err) return (
    <div className="screen">
      <h1>Прогрес</h1>
      <div className="warning mt">⚠️ <span>{err}</span></div>
      <button className="btn mt" onClick={() => { setErr(""); load(); }}>Опитай отново</button>
    </div>
  );
  if (!d) return <div className="screen center"><span className="spin">⚙️</span></div>;

  const pct = d.total ? Math.round((d.done / d.total) * 100) : 0;
  const maxLoad = Math.max(1, ...d.weekly.map((w) => w.load_planned));

  return (
    <div className="screen">
      <h1>Прогрес</h1>
      <p className="sub">
        Седмица {d.current_week} от {d.total_weeks} · <b>{PHASE_BG[d.phase]}</b>
        {d.days_to_race != null && d.days_to_race >= 0 && (
          <> · 🏁 {d.race?.name}: след {d.days_to_race} дни</>
        )}
      </p>

      <div className="stat-row mt">
        <div className="stat"><div className="v">{pct}%</div><div className="l">изпълнение</div></div>
        <div className="stat"><div className="v">{d.done}/{d.total}</div><div className="l">направени</div></div>
        <div className="stat"><div className="v">{d.avg_rpe ?? "—"}</div><div className="l">средно RPE</div></div>
      </div>

      <div className="card mt">
        <h2>🎯 На какво да наблегнеш</h2>
        {d.focus.map((f, i) => (
          <p key={i} className={i === 0 ? "" : "sub"} style={{ marginTop: i === 0 ? 8 : 10 }}>{f}</p>
        ))}
      </div>

      <div className="card">
        <h2>📊 Натоварване по седмици</h2>
        <p className="sub" style={{ marginBottom: 12 }}>
          Плътната част е изпълненото; рамката — планираното.
        </p>
        <div style={{ display: "flex", alignItems: "flex-end", gap: 6, height: 120 }}>
          {d.weekly.map((w) => {
            const hPlanned = Math.max(8, (w.load_planned / maxLoad) * 100);
            const hDone = w.load_planned ? (w.load_done / w.load_planned) * 100 : 0;
            const current = w.week === d.current_week;
            return (
              <div key={w.week} style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", gap: 4 }}>
                <div style={{
                  width: "100%", height: `${hPlanned}%`, borderRadius: 6,
                  border: `1px solid ${current ? "var(--accent, #ff6b35)" : "#3a4356"}`,
                  display: "flex", alignItems: "flex-end", overflow: "hidden",
                }}>
                  <div style={{ width: "100%", height: `${hDone}%`, background: "#6ede8a" }} />
                </div>
                <span className="sub" style={{ fontSize: "0.7rem", fontWeight: current ? 800 : 400 }}>{w.week}</span>
              </div>
            );
          })}
        </div>
      </div>

      {d.missed > 0 && (
        <div className="warning">
          ⚠️ <span>{d.missed} {d.missed === 1 ? "тренировка е пропусната" : "тренировки са пропуснати"} без отметка —
          отбележи ги като направени или пропуснати, за да е точна статистиката.</span>
        </div>
      )}

      <div className="card">
        <h2>⚙️ Твоите зони</h2>
        <ul className="seg-list">
          {d.zones.vdot && <li><span>VDOT (бегова форма)</span><span><b>{d.zones.vdot}</b></span></li>}
          {d.zones.ftp_w && <li><span>FTP</span><span><b>{d.zones.ftp_w} W</b></span></li>}
          {d.zones.max_hr_bpm && <li><span>Макс. пулс{d.zones.max_hr_estimated ? " (оценка)" : ""}</span><span><b>{d.zones.max_hr_bpm} уд/мин</b></span></li>}
        </ul>
        <p className="hint mt">Нови стойности от тест? Обнови ги в Настройки → Физиология.</p>
      </div>
    </div>
  );
}
