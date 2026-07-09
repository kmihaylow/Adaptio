import { useEffect, useState } from "react";
import type { Workout } from "../types";
import { api } from "../api";
import WorkoutCard from "../components/WorkoutCard";
import RatingSheet from "../components/RatingSheet";

const timeCheckKey = () => `adaptio_timecheck_${new Date().toLocaleDateString("sv-SE")}`;

export default function Today() {
  const [today, setToday] = useState<Workout[]>([]);
  const [upcoming, setUpcoming] = useState<Workout[]>([]);
  const [zones, setZones] = useState<Record<string, any>>({});
  const [rating, setRating] = useState<Workout | null>(null);
  const [coachMsg, setCoachMsg] = useState<string | null>(null);
  const [err, setErr] = useState("");
  const [timeAsked, setTimeAsked] = useState(() => !!localStorage.getItem(timeCheckKey()));

  async function load() {
    try {
      const r = await api.today();
      setToday(r.today);
      setUpcoming(r.upcoming);
      setZones(r.zones);
    } catch (e: any) {
      setErr(e.message);
    }
  }
  useEffect(() => { load(); }, []);

  const cardioToday = today.filter((w) => (w.sport === "run" || w.sport === "bike") && w.status === "planned");

  async function timeCheck(factor: number) {
    localStorage.setItem(timeCheckKey(), "1");
    setTimeAsked(true);
    if (factor !== 1) {
      for (const w of cardioToday) {
        try { await api.adjustTime(w.id, factor); } catch {}
      }
      setCoachMsg(factor < 1
        ? "Свих леката част на тренировката — качествената работа остава. По-добре кратка, отколкото пропусната."
        : "Удължих Z2 частта — допълнителният аеробен обем винаги е добра инвестиция.");
      load();
    }
  }

  async function skip(wo: Workout) {
    await api.setStatus(wo.id, "skipped");
    load();
  }

  const dateStr = new Date().toLocaleDateString("bg-BG", { weekday: "long", day: "numeric", month: "long" });

  return (
    <div className="screen">
      <p className="sub" style={{ textTransform: "capitalize" }}>{dateStr}</p>
      <h1>Днес</h1>
      <div className="mt" />

      {coachMsg && <div className="coach-note" onClick={() => setCoachMsg(null)}>🧠 {coachMsg}</div>}

      {cardioToday.length > 0 && (
        !timeAsked ? (
          <div className="card">
            <h2>⏱ Разполагаш ли с {cardioToday.reduce((a, w) => a + w.duration_min, 0)} мин днес?</h2>
            <p className="sub" style={{ marginBottom: 10 }}>
              Кажи ми и ще преразпределя — качествената работа остава, лекият обем се напасва.
            </p>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              <button className="btn small ghost" onClick={() => timeCheck(0.7)}>Имам по-малко</button>
              <button className="btn small" onClick={() => timeCheck(1)}>Точно толкова</button>
              <button className="btn small ghost" onClick={() => timeCheck(1.3)}>Имам повече</button>
            </div>
          </div>
        ) : (
          <button className="btn small ghost" style={{ marginBottom: 12 }}
            onClick={() => setTimeAsked(false)}>
            ⏱ Друго време днес? Преразпредели
          </button>
        )
      )}
      {err && (
        <>
          <div className="warning">⚠️ <span>{err}</span></div>
          <button className="btn mt" onClick={() => { setErr(""); load(); }}>Опитай отново</button>
        </>
      )}

      {today.length === 0 && !err && (
        <div className="card center">
          <div style={{ fontSize: "2.4rem" }}>😌</div>
          <h2 style={{ marginTop: 8 }}>Почивен ден</h2>
          <p className="sub">Възстановяването е част от тренировката. Разходка, стречинг, сън.</p>
        </div>
      )}

      {today.map((wo) => (
        <WorkoutCard key={wo.id} wo={wo} ftp={zones.ftp_w} onRate={setRating} onSkip={skip} />
      ))}

      {upcoming.length > 0 && (
        <>
          <h2 className="mt">Следващи тренировки</h2>
          {upcoming.map((wo) => <WorkoutCard key={wo.id} wo={wo} ftp={zones.ftp_w} />)}
        </>
      )}

      {rating && (
        <RatingSheet
          wo={rating}
          onClose={() => setRating(null)}
          onDone={(msg) => { setRating(null); setCoachMsg(msg); load(); }}
        />
      )}
    </div>
  );
}
