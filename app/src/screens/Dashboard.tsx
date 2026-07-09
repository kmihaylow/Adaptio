import { useEffect, useRef, useState } from "react";
import type { ActualActivity, ComparisonRow, Dashboard as Dash, LastAnalysis } from "../types";
import { api, fmtPace } from "../api";

const PHASE_BG: Record<string, string> = {
  base: "База", build: "Изграждане", peak: "Пик", recovery: "Възстановяване", taper: "Тейпър",
};

const VERDICT_ICON = { ok: "✅", over: "🔺", under: "🔻" } as const;

type AiReview = { verdict: string; execution_score: number; strengths: string[];
                  improvements: string[]; next_advice: string };

export default function Dashboard() {
  const [d, setD] = useState<Dash | null>(null);
  const [err, setErr] = useState("");
  const [syncMsg, setSyncMsg] = useState("");
  const [coachMsgs, setCoachMsgs] = useState<string[]>([]);
  const [last, setLast] = useState<LastAnalysis | null>(null);
  const [ai, setAi] = useState<AiReview | null>(null);
  const [aiBusy, setAiBusy] = useState(false);
  const [aiErr, setAiErr] = useState("");
  const [uploadMsg, setUploadMsg] = useState("");
  const [adhoc, setAdhoc] = useState<{ activity: ActualActivity; analysis: ComparisonRow[] } | null>(null);
  const [adhocAi, setAdhocAi] = useState<AiReview | null>(null);
  const [adhocBusy, setAdhocBusy] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  async function load() {
    // best-effort auto-import from intervals.icu before reading the stats;
    // fails silently when the integration isn't connected
    try {
      const s = await api.syncActivities();
      if (s.synced > 0)
        setSyncMsg(`📥 ${s.synced} ${s.synced === 1 ? "тренировка е отбелязана" : "тренировки са отбелязани"} автоматично от Garmin.`);
      if (s.messages?.length) setCoachMsgs(s.messages);
    } catch {}
    try { setD(await api.dashboard()); } catch (e: any) { setErr(e.message); }
    try { setLast(await api.analysisLast()); } catch { setLast(null); }
  }
  useEffect(() => { load(); }, []);

  async function deepAnalysis() {
    setAiBusy(true); setAiErr("");
    try { setAi(await api.analysisAI()); } catch (e: any) { setAiErr(e.message); }
    setAiBusy(false);
  }

  async function onUpload(f: File) {
    setUploadMsg("⏳ Обработвам файла...");
    setAdhoc(null); setAdhocAi(null);
    try {
      const r = await api.uploadActivity(f);
      setUploadMsg(r.synced > 0 ? "✅ Тренировката е разпозната и отбелязана!" : "");
      if (r.messages?.length) setCoachMsgs((m) => [...m, ...r.messages]);
      if (r.synced > 0) { setAi(null); load(); }
      else if (r.analysis?.length) setAdhoc({ activity: r.activity, analysis: r.analysis });
    } catch (e: any) { setUploadMsg(`❌ ${e.message}`); }
  }

  async function adhocAnalysis() {
    if (!adhoc) return;
    setAdhocBusy(true);
    try { setAdhocAi(await api.analysisAdhocAI(adhoc.activity)); }
    catch (e: any) { setUploadMsg(`❌ ${e.message}`); }
    setAdhocBusy(false);
  }

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

      {syncMsg && <div className="coach-note mt" onClick={() => setSyncMsg("")}>{syncMsg}</div>}
      {coachMsgs.map((m, i) => (
        <div className="coach-note mt" key={i} onClick={() => setCoachMsgs(coachMsgs.filter((_, j) => j !== i))}>
          🧠 {m}
        </div>
      ))}

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
        <h2>🏁 Последна тренировка</h2>
        {last ? (
          <>
            <p className="sub" style={{ marginTop: 6 }}>
              {last.workout.name} · {new Date(last.workout.date + "T00:00:00").toLocaleDateString("bg-BG", { day: "numeric", month: "long" })}
              {last.actual.name ? ` · ${last.actual.name}` : ""}
            </p>
            <p className="wo-desc" style={{ color: "#6ede8a" }}>
              {last.actual.moving_time_min} мин
              {last.actual.distance_km ? ` · ${last.actual.distance_km} км` : ""}
              {last.actual.pace_s_per_km ? ` · ${fmtPace(last.actual.pace_s_per_km)}/км` : ""}
              {last.actual.avg_watts ? ` · ${Math.round(last.actual.avg_watts)}W` : ""}
              {last.actual.avg_hr ? ` · ${Math.round(last.actual.avg_hr)} уд/мин` : ""}
            </p>
            <ul className="seg-list">
              {last.comparison.map((row, i) => (
                <li key={i} style={{ display: "block" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
                    <span>{VERDICT_ICON[row.verdict]} <b>{row.metric}</b></span>
                    <span style={{ whiteSpace: "nowrap" }}>{row.planned} → <b>{row.actual}</b></span>
                  </div>
                  <div className="hint" style={{ marginTop: 2 }}>{row.comment}</div>
                </li>
              ))}
            </ul>

            {!ai ? (
              <button className="btn small mt" disabled={aiBusy} onClick={deepAnalysis}>
                {aiBusy ? <span className="spin">⚙️</span> : "🧠 Дълбок анализ от треньора"}
              </button>
            ) : (
              <div className="coach-note mt">
                <p><b>{ai.verdict}</b> · Изпълнение: {ai.execution_score}/10</p>
                {ai.strengths.map((s, i) => <p key={`s${i}`} style={{ marginTop: 6 }}>👍 {s}</p>)}
                {ai.improvements.map((s, i) => <p key={`i${i}`} style={{ marginTop: 6 }}>🔧 {s}</p>)}
                <p style={{ marginTop: 8 }}><b>Напред:</b> {ai.next_advice}</p>
              </div>
            )}
            {aiErr && <p className="hint mt">❌ {aiErr}</p>}
          </>
        ) : (
          <p className="sub" style={{ marginTop: 6 }}>
            Още няма синхронизирана тренировка. Свържи intervals.icu от Настройки — или качи файл ръчно:
          </p>
        )}

        <input ref={fileRef} type="file" accept=".fit,.tcx,.gpx" style={{ display: "none" }}
          onChange={(e) => { const f = e.target.files?.[0]; if (f) onUpload(f); e.target.value = ""; }} />
        <button className="btn small ghost mt" onClick={() => fileRef.current?.click()}>
          📎 Качи тренировка (.fit / .tcx / .gpx)
        </button>
        {uploadMsg && <p className="hint mt">{uploadMsg}</p>}

        {adhoc && (
          <>
            <p className="sub mt"><b>Анализ на качената активност</b> (няма планирана за тази дата):</p>
            <ul className="seg-list">
              {adhoc.analysis.map((row, i) => (
                <li key={i} style={{ display: "block" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
                    <span>{VERDICT_ICON[row.verdict]} <b>{row.metric}</b></span>
                    <span style={{ whiteSpace: "nowrap" }}>{row.planned} → <b>{row.actual}</b></span>
                  </div>
                  <div className="hint" style={{ marginTop: 2 }}>{row.comment}</div>
                </li>
              ))}
            </ul>
            {!adhocAi ? (
              <button className="btn small mt" disabled={adhocBusy} onClick={adhocAnalysis}>
                {adhocBusy ? <span className="spin">⚙️</span> : "🧠 Дълбок анализ от треньора"}
              </button>
            ) : (
              <div className="coach-note mt">
                <p><b>{adhocAi.verdict}</b> · Изпълнение: {adhocAi.execution_score}/10</p>
                {adhocAi.strengths.map((s, i) => <p key={`s${i}`} style={{ marginTop: 6 }}>👍 {s}</p>)}
                {adhocAi.improvements.map((s, i) => <p key={`i${i}`} style={{ marginTop: 6 }}>🔧 {s}</p>)}
                <p style={{ marginTop: 8 }}><b>Напред:</b> {adhocAi.next_advice}</p>
              </div>
            )}
          </>
        )}
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
          {d.zones.w_per_kg && <li><span>Мощност/тегло</span><span><b>{d.zones.w_per_kg} W/kg</b></span></li>}
          {d.zones.max_hr_bpm && <li><span>Макс. пулс{d.zones.max_hr_estimated ? " (оценка)" : ""}</span><span><b>{d.zones.max_hr_bpm} уд/мин</b></span></li>}
          {d.zones.bmi && (
            <li><span>BMI</span><span><b>{d.zones.bmi}</b>{" "}
              <span className="sub">({d.zones.bmi < 18.5 ? "нисък" : d.zones.bmi < 25 ? "норма" : d.zones.bmi < 30 ? "наднормен" : "висок"})</span>
            </span></li>
          )}
        </ul>
        <p className="hint mt">Нови стойности от тест? Обнови ги в Настройки → Физиология.</p>
      </div>
    </div>
  );
}
