import { useEffect, useState } from "react";
import { api } from "../api";

const METRIC_FIELDS = [
  ["ftp_w", "FTP (вата)", "напр. 210"],
  ["vo2max", "VO₂max", "напр. 45"],
  ["max_hr_bpm", "Макс. пулс (уд/мин)", "напр. 185"],
  ["lthr_bpm", "LTHR (уд/мин)", "напр. 168"],
  ["resting_hr_bpm", "Пулс в покой", "напр. 55"],
  ["weight_kg", "Тегло (кг)", "напр. 78"],
  ["height_cm", "Ръст (см)", "напр. 178"],
] as const;

export default function Settings({ onReset, onLogout }: { onReset: () => void; onLogout: () => void }) {
  const [connected, setConnected] = useState(false);
  const [apiKey, setApiKey] = useState("");
  const [athleteId, setAthleteId] = useState("");
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);
  const [metrics, setMetrics] = useState<Record<string, string>>({});
  const [metricsMsg, setMetricsMsg] = useState("");
  const [garminConnected, setGarminConnected] = useState(false);
  const [garminEmail, setGarminEmail] = useState("");
  const [garminPass, setGarminPass] = useState("");

  useEffect(() => {
    api.intervalsStatus().then((r) => setConnected(r.connected)).catch(() => {});
    api.garminStatus().then((r) => setGarminConnected(r.connected)).catch(() => {});
    api.getProfile().then((p: any) => {
      const m: Record<string, string> = {};
      for (const [key] of METRIC_FIELDS) m[key] = p[key] != null ? String(p[key]) : "";
      setMetrics(m);
    }).catch(() => {});
  }, []);

  async function saveMetrics() {
    setBusy(true); setMetricsMsg("");
    try {
      const body: Record<string, number | null> = {};
      for (const [key] of METRIC_FIELDS) {
        if (metrics[key] !== "" && !isNaN(+metrics[key])) body[key] = +metrics[key];
      }
      await api.updateMetrics(body);
      setMetricsMsg("✅ Записано! Зоните са преизчислени. Темповите цели в текущите тренировки се обновяват при следващо генериране на план.");
    } catch (e: any) { setMetricsMsg(`❌ ${e.message}`); }
    setBusy(false);
  }

  async function connect() {
    setBusy(true); setMsg("");
    try {
      await api.connectIntervals(apiKey, athleteId);
      setConnected(true);
      setMsg("✅ Свързано! Данните от Garmin ще идват през intervals.icu.");
    } catch (e: any) { setMsg(`❌ ${e.message}`); }
    setBusy(false);
  }

  async function push() {
    setBusy(true); setMsg("");
    try {
      const today = new Date().toISOString().slice(0, 10);
      const plan = await api.getPlan();
      const cur = plan.workouts.find((w) => w.date >= today);
      const r = await api.pushWeek(cur ? cur.plan_week : 1);
      setMsg(`✅ ${r.pushed} тренировки качени в intervals.icu календара — ще се синхронизират към Garmin.`);
    } catch (e: any) { setMsg(`❌ ${e.message}`); }
    setBusy(false);
  }

  async function pull() {
    setBusy(true); setMsg("");
    try {
      const r = await api.syncActivities();
      setMsg(r.synced === 0
        ? "Няма нови завършени тренировки за отбелязване."
        : `✅ ${r.synced} ${r.synced === 1 ? "тренировка е отбелязана" : "тренировки са отбелязани"}: ${r.matched.map((m) => `${m.workout} (${m.date})`).join(", ")}`);
    } catch (e: any) { setMsg(`❌ ${e.message}`); }
    setBusy(false);
  }

  async function connectGarminAcc() {
    setBusy(true); setMsg("");
    try {
      const r = await api.connectGarmin(garminEmail, garminPass);
      setGarminConnected(true);
      setGarminPass("");
      setMsg(`✅ Garmin е свързан (${r.athlete.name}). Тренировките ще се дърпат автоматично.`);
    } catch (e: any) { setMsg(`❌ ${e.message}`); }
    setBusy(false);
  }

  return (
    <div className="screen">
      <h1>Настройки</h1>

      <div className="card mt">
        <h2>💪 Физиология</h2>
        <p className="sub" style={{ marginBottom: 12 }}>
          Нов FTP тест, нов макс. пулс от състезание? Обнови стойностите тук по всяко време —
          зоните се преизчисляват веднага.
        </p>
        {METRIC_FIELDS.map(([key, label, ph]) => (
          <div className="field" key={key}>
            <label>{label}</label>
            <input type="number" inputMode="decimal" value={metrics[key] ?? ""}
              onChange={(e) => setMetrics({ ...metrics, [key]: e.target.value })} placeholder={ph} />
          </div>
        ))}
        <button className="btn" disabled={busy} onClick={saveMetrics}>Запази стойностите</button>
        {metricsMsg && <p className="hint mt">{metricsMsg}</p>}
      </div>

      <div className="card">
        <h2>🔗 intervals.icu {connected && <span className="badge done">свързано</span>}</h2>
        <p className="sub" style={{ marginBottom: 12 }}>
          Мостът към Garmin: часовникът ти синхронизира тренировки и възстановяване към intervals.icu,
          а плановете от Adaptio се появяват в Garmin календара ти. Ключ: intervals.icu → Settings → Developer.
        </p>
        {!connected ? (
          <>
            <div className="field">
              <label>API ключ</label>
              <input type="text" value={apiKey} onChange={(e) => setApiKey(e.target.value)} placeholder="xxxxxxxx" />
            </div>
            <div className="field">
              <label>Athlete ID</label>
              <input type="text" value={athleteId} onChange={(e) => setAthleteId(e.target.value)} placeholder="i123456" />
            </div>
            <button className="btn" disabled={!apiKey || !athleteId || busy} onClick={connect}>Свържи</button>
          </>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            <button className="btn ghost" disabled={busy} onClick={push}>
              📤 Качи текущата седмица в календара
            </button>
            <button className="btn ghost" disabled={busy} onClick={pull}>
              📥 Изтегли завършените тренировки
            </button>
          </div>
        )}
      </div>

      <div className="card">
        <h2>⌚ Garmin Connect (директно) {garminConnected && <span className="badge done">свързано</span>}</h2>
        <p className="sub" style={{ marginBottom: 12 }}>
          Директна връзка с твоя Garmin акаунт — завършените тренировки се дърпат без
          intervals.icu. Неофициален канал: работи стабилно, но Garmin може да го промени;
          акаунти с двустепенна верификация (MFA) не се поддържат.
        </p>
        {!garminConnected ? (
          <>
            <div className="field">
              <label>Garmin имейл</label>
              <input type="text" autoCapitalize="none" value={garminEmail}
                onChange={(e) => setGarminEmail(e.target.value)} placeholder="you@example.com" />
            </div>
            <div className="field">
              <label>Garmin парола</label>
              <input type="password" value={garminPass}
                onChange={(e) => setGarminPass(e.target.value)} placeholder="••••••" />
            </div>
            <button className="btn" disabled={!garminEmail || !garminPass || busy} onClick={connectGarminAcc}>
              Свържи Garmin
            </button>
          </>
        ) : (
          <button className="btn ghost" disabled={busy}
            onClick={async () => { await api.disconnectGarmin().catch(() => {}); setGarminConnected(false); }}>
            Изключи Garmin връзката
          </button>
        )}
      </div>

      {msg && <div className="coach-note">{msg}</div>}

      <div className="card">
        <h2>♻️ Начало отначало</h2>
        <p className="sub" style={{ marginBottom: 12 }}>Нова цел или нови данни? Мини отново през въпросника.</p>
        <button className="btn ghost" onClick={onReset}>Редактирай профила и генерирай нов план</button>
      </div>

      <div className="card">
        <h2>👤 Профил</h2>
        <button className="btn ghost" onClick={onLogout}>Излез от профила</button>
      </div>

      <p className="sub center mt">Adaptio v0.3 · направено с ❤️ и наука</p>
    </div>
  );
}
