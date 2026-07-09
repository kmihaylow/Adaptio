import { useMemo, useState } from "react";
import type { Profile, Sport } from "../types";
import { api } from "../api";
import InfoTip, { TIPS } from "../components/InfoTip";

const DAYS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Нд"];

// "И двете" is hidden for now — flip to true to bring it back instantly.
const SHOW_BOTH_SPORT = false;

const MIN_WEEKS: Record<string, number> = {
  "5k": 6, "10k": 8, half_marathon: 10, marathon: 14,
  ftp: 6, endurance: 8, vo2max: 6, general: 4, mixed: 8,
};

// realistic input ranges (mirror the backend's pydantic constraints)
const LIMITS = {
  age: [10, 90, "години"],
  weight: [30, 200, "кг"],
  height: [120, 220, "см"],
  maxHr: [120, 220, "уд/мин"],
  restingHr: [30, 100, "уд/мин"],
  vo2max: [20, 90, ""],
  ftp: [50, 500, "W"],
  lthr: [100, 210, "уд/мин"],
} as const;

function rangeErr(key: keyof typeof LIMITS, value: string): string | null {
  if (value === "") return null;
  const [lo, hi, unit] = LIMITS[key];
  const v = +value;
  if (isNaN(v) || v < lo || v > hi) return `Въведи реална стойност: ${lo}–${hi} ${unit}`.trim();
  return null;
}

type Draft = {
  sport: Sport | null;
  age: string; sex: "male" | "female"; weight: string; height: string;
  maxHr: string; restingHr: string; vo2max: string; ftp: string; lthr: string;
  raceDist: string; raceMin: string; raceSec: string;
  weeklyHours: number; days: number[]; level: string; strength: boolean; stretching: boolean;
  strengthSetting: "home" | "dumbbells" | "gym";
  hasRace: boolean; raceName: string; raceDate: string; weeks: number;
  runGoalType: string; runDistance: string; targetH: string; targetM: string; targetS: string;
  paceM: string; paceS: string; bikeGoalType: string;
  eq: { power_meter: boolean; smart_trainer: boolean; hr_monitor: boolean; smartwatch: boolean; gps_watch: boolean };
};

const init: Draft = {
  sport: null, age: "", sex: "male", weight: "", height: "",
  maxHr: "", restingHr: "", vo2max: "", ftp: "", lthr: "",
  raceDist: "", raceMin: "", raceSec: "",
  weeklyHours: 5, days: [0, 2, 4, 6], level: "", strength: false, stretching: false,
  strengthSetting: "home",
  hasRace: false, raceName: "", raceDate: "", weeks: 8,
  runGoalType: "race_time", runDistance: "10k", targetH: "0", targetM: "50", targetS: "0",
  paceM: "5", paceS: "30", bikeGoalType: "ftp",
  eq: { power_meter: false, smart_trainer: false, hr_monitor: false, smartwatch: false, gps_watch: false },
};

export default function Onboarding({ onComplete }: { onComplete: () => void }) {
  const [step, setStep] = useState(0);
  const [d, setD] = useState<Draft>(init);
  const [busy, setBusy] = useState(false);
  const [warnings, setWarnings] = useState<string[]>([]);
  const [err, setErr] = useState("");

  const isRun = d.sport === "run" || d.sport === "both";
  const isBike = d.sport === "bike" || d.sport === "both";
  const steps = 7;
  const set = (patch: Partial<Draft>) => setD({ ...d, ...patch });

  const weeksWarning = useMemo(() => {
    if (d.hasRace) {
      if (!d.raceDate) return null;
      const days = (new Date(d.raceDate).getTime() - Date.now()) / 86400000;
      const w = Math.floor(days / 7);
      const min = isRun ? MIN_WEEKS[d.runDistance] ?? 8 : MIN_WEEKS[d.bikeGoalType] ?? 6;
      if (w < min)
        return `До състезанието остават ~${Math.max(0, w)} седмици — под препоръчителния минимум от ${min} за тази цел. Планът ще е компромисен и резултатът може да не отговори на очакванията ти.`;
      return null;
    }
    const min = isRun && d.runGoalType !== "general" ? MIN_WEEKS[d.runDistance] ?? 8
      : isBike ? MIN_WEEKS[d.bikeGoalType] ?? 6 : 6;
    if (d.weeks < min)
      return `${d.weeks} седмици е кратък срок — физиологичната адаптация изисква поне ${min} седмици за тази цел. Ще видиш нещо, но не пълния ефект.`;
    return null;
  }, [d, isRun, isBike]);

  function buildProfile(): Profile {
    const distM: Record<string, number> = { "5k": 5000, "10k": 10000, half_marathon: 21097, marathon: 42195 };
    const targetTime = (+d.targetH * 3600) + (+d.targetM * 60) + (+d.targetS || 0);
    return {
      sport: d.sport!,
      age: +d.age, sex: d.sex, weight_kg: +d.weight,
      height_cm: d.height ? +d.height : null,
      max_hr_bpm: d.maxHr ? +d.maxHr : null,
      resting_hr_bpm: d.restingHr ? +d.restingHr : null,
      vo2max: d.vo2max ? +d.vo2max : null,
      ftp_w: d.ftp ? +d.ftp : null,
      lthr_bpm: d.lthr ? +d.lthr : null,
      recent_race: d.raceDist && (+d.raceMin > 0)
        ? { distance: d.raceDist, time_s: +d.raceMin * 60 + (+d.raceSec || 0) }
        : null,
      weekly_hours: d.weeklyHours,
      available_days: d.days,
      experience_years: 0,
      training_level: d.level as any,
      currently_training: d.level === "regular" || d.level === "athlete",
      strength_enabled: d.strength,
      strength_setting: d.strengthSetting,
      stretching_enabled: d.stretching,
      equipment: d.eq,
      goal: {
        run_goal_type: isRun ? (d.runGoalType as any) : null,
        run_distance: isRun && d.runGoalType !== "general" ? (d.runDistance as any) : null,
        target_time_s: isRun && d.runGoalType === "race_time" && targetTime > 0 ? targetTime : null,
        target_pace_s_per_km: isRun && d.runGoalType === "race_pace" ? +d.paceM * 60 + (+d.paceS || 0) : null,
        bike_goal_type: isBike ? (d.bikeGoalType as any) : null,
        race: d.hasRace && d.raceName && d.raceDate ? { name: d.raceName, date: d.raceDate } : null,
        weeks: d.hasRace ? null : d.weeks,
      },
    };
  }

  async function finish() {
    setBusy(true); setErr("");
    try {
      const r = await api.saveProfile(buildProfile());
      setWarnings(r.warnings);
      await api.generatePlan();
      onComplete();
    } catch (e: any) {
      setErr(e.message);
      setBusy(false);
    }
  }

  const step1Valid = !rangeErr("age", d.age) && d.age !== "" &&
    !rangeErr("weight", d.weight) && d.weight !== "" &&
    !rangeErr("height", d.height) && d.height !== "";
  const step2Valid = !rangeErr("maxHr", d.maxHr) && !rangeErr("restingHr", d.restingHr) &&
    !rangeErr("vo2max", d.vo2max) && !rangeErr("ftp", d.ftp) && !rangeErr("lthr", d.lthr);

  const canNext = [
    d.sport !== null,
    step1Valid,
    step2Valid,
    true,
    d.days.length >= 2 && d.level !== "",
    d.hasRace ? !!(d.raceName && d.raceDate) : d.weeks >= 2,
    true,
  ][step];

  return (
    <div className="screen">
      <h1>
        {step === 0 ? <>Здравей! Аз съм <span className="brand">Adaptio</span> 👋</> : "Разкажи ми за себе си"}
      </h1>
      <div className="dots">
        {Array.from({ length: steps }, (_, i) => <span key={i} className={i <= step ? "on" : ""} />)}
      </div>

      {step === 0 && (
        <>
          <p className="sub" style={{ marginBottom: 18 }}>
            Твоят личен адаптивен треньор. Кой спорт тренираш?
          </p>
          <div className="opts">
            {([["run", "🏃", "Бягане"], ["bike", "🚴", "Колоездене"], ["both", "🔥", "И двете"]] as const)
              .filter(([v]) => SHOW_BOTH_SPORT || v !== "both")
              .map(([v, e, t]) => (
                <button key={v} className={`opt ${d.sport === v ? "selected" : ""}`} onClick={() => set({ sport: v })}>
                  <span className="emoji">{e}</span>
                  <span className="t">{t}</span>
                </button>
              ))}
          </div>
        </>
      )}

      {step === 1 && (
        <>
          <div className="field">
            <label>Възраст</label>
            <input type="number" inputMode="numeric" value={d.age} onChange={(e) => set({ age: e.target.value })} placeholder="напр. 34" />
            {rangeErr("age", d.age) && <p className="hint" style={{ color: "var(--accent)" }}>{rangeErr("age", d.age)}</p>}
          </div>
          <div className="field">
            <label>Пол</label>
            <div className="opts cols2">
              <button className={`opt ${d.sex === "male" ? "selected" : ""}`} onClick={() => set({ sex: "male" })}>Мъж</button>
              <button className={`opt ${d.sex === "female" ? "selected" : ""}`} onClick={() => set({ sex: "female" })}>Жена</button>
            </div>
          </div>
          <div className="field">
            <label>Тегло (кг)</label>
            <input type="number" inputMode="decimal" value={d.weight} onChange={(e) => set({ weight: e.target.value })} placeholder="напр. 78" />
            {rangeErr("weight", d.weight) && <p className="hint" style={{ color: "var(--accent)" }}>{rangeErr("weight", d.weight)}</p>}
          </div>
          <div className="field">
            <label>Ръст (см)</label>
            <input type="number" inputMode="numeric" value={d.height} onChange={(e) => set({ height: e.target.value })} placeholder="напр. 178" />
            {rangeErr("height", d.height) && <p className="hint" style={{ color: "var(--accent)" }}>{rangeErr("height", d.height)}</p>}
            <p className="hint">Нужен за BMI — един от най-важните маркери за формата.</p>
          </div>
        </>
      )}

      {step === 2 && (
        <>
          <p className="sub" style={{ marginBottom: 14 }}>
            Всичко тук е <b>по желание</b> — колкото повече знаем, толкова по-точни са зоните. Ако не знаеш стойност, просто я остави празна.
          </p>
          <div className="field">
            <label>Максимален пулс (уд/мин) <InfoTip text={TIPS.maxHr} /></label>
            <input type="number" value={d.maxHr} onChange={(e) => set({ maxHr: e.target.value })} placeholder="празно = формула по възрастта" />
            {rangeErr("maxHr", d.maxHr) && <p className="hint" style={{ color: "var(--accent)" }}>{rangeErr("maxHr", d.maxHr)}</p>}
          </div>
          <div className="field">
            <label>Пулс в покой <InfoTip text={TIPS.restingHr} /></label>
            <input type="number" value={d.restingHr} onChange={(e) => set({ restingHr: e.target.value })} placeholder="напр. 55" />
            {rangeErr("restingHr", d.restingHr) && <p className="hint" style={{ color: "var(--accent)" }}>{rangeErr("restingHr", d.restingHr)}</p>}
          </div>
          <div className="field">
            <label>VO₂max <InfoTip text={TIPS.vo2max} /></label>
            <input type="number" value={d.vo2max} onChange={(e) => set({ vo2max: e.target.value })} placeholder="от часовника, напр. 45" />
            {rangeErr("vo2max", d.vo2max) && <p className="hint" style={{ color: "var(--accent)" }}>{rangeErr("vo2max", d.vo2max)}</p>}
          </div>
          {isBike && (
            <>
              <div className="field">
                <label>FTP (вата) <InfoTip text={TIPS.ftp} /></label>
                <input type="number" value={d.ftp} onChange={(e) => set({ ftp: e.target.value })} placeholder="напр. 210" />
                {rangeErr("ftp", d.ftp) && <p className="hint" style={{ color: "var(--accent)" }}>{rangeErr("ftp", d.ftp)}</p>}
              </div>
              <div className="field">
                <label>LTHR (уд/мин) <InfoTip text={TIPS.lthr} /></label>
                <input type="number" value={d.lthr} onChange={(e) => set({ lthr: e.target.value })} placeholder="напр. 168" />
                {rangeErr("lthr", d.lthr) && <p className="hint" style={{ color: "var(--accent)" }}>{rangeErr("lthr", d.lthr)}</p>}
              </div>
            </>
          )}
          {isRun && (
            <div className="field">
              <label>Скорошно бегово състезание/тест <InfoTip text={TIPS.recentRace} /></label>
              <select value={d.raceDist} onChange={(e) => set({ raceDist: e.target.value })}>
                <option value="">Нямам скорошен резултат</option>
                <option value="5k">5 км</option>
                <option value="10k">10 км</option>
                <option value="half_marathon">Полумаратон</option>
                <option value="marathon">Маратон</option>
              </select>
              {d.raceDist && (
                <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
                  <input type="number" value={d.raceMin} onChange={(e) => set({ raceMin: e.target.value })} placeholder="мин" />
                  <input type="number" value={d.raceSec} onChange={(e) => set({ raceSec: e.target.value })} placeholder="сек" />
                </div>
              )}
            </div>
          )}
        </>
      )}

      {step === 3 && (
        <>
          <h2>С какво разполагаш?</h2>
          <p className="sub" style={{ marginBottom: 14 }}>
            Това определя как ще са зададени тренировките: ватове → пулсови зони → усещане (RPE).
          </p>
          <div className="opts">
            {isBike && ([["power_meter", "⚡ Пауърметър (педали/курбел)"], ["smart_trainer", "🖥️ Смарт тренажор"]] as const).map(([k, t]) => (
              <button key={k} className={`opt ${d.eq[k] ? "selected" : ""}`}
                onClick={() => set({ eq: { ...d.eq, [k]: !d.eq[k] } })}>{t}</button>
            ))}
            {([["hr_monitor", "❤️ Пулсомер-колан"], ["smartwatch", "⌚ Смарт часовник (пулс на китка)"]] as const).map(([k, t]) => (
              <button key={k} className={`opt ${d.eq[k] ? "selected" : ""}`}
                onClick={() => set({ eq: { ...d.eq, [k]: !d.eq[k] } })}>{t}</button>
            ))}
            {isRun && (
              <button className={`opt ${d.eq.gps_watch ? "selected" : ""}`}
                onClick={() => set({ eq: { ...d.eq, gps_watch: !d.eq.gps_watch } })}>📍 GPS часовник</button>
            )}
          </div>
          <p className="hint mt">Нищо от изброените? Не е проблем — програмата ще е по усещане и пак работи.</p>
        </>
      )}

      {step === 4 && (
        <>
          <h2>Как тренираш в момента?</h2>
          <p className="sub" style={{ marginBottom: 10 }}>
            Това определя колко смело започва планът — начинаещ и атлет никога не получават една и съща първа седмица.
          </p>
          <div className="opts" style={{ marginBottom: 14 }}>
            {([
              ["beginner", "🌱 Не тренирам / започвам сега", "Плавно навлизане: 70% обем, дълга база, 1 качествена тренировка"],
              ["occasional", "🚶 Спорадично (1-2 пъти седмично)", "Внимателен старт с постепенно навлизане в структура"],
              ["regular", "🏃 Редовно (3-4 пъти, с постоянство)", "Стартираш близо до пълния обем, 2 качествени тренировки"],
              ["athlete", "🏆 Атлет — години опит и състезания", "Пълен обем от първата седмица, минимална база, бърза прогресия"],
            ] as const).map(([v, t, sub]) => (
              <button key={v} className={`opt ${d.level === v ? "selected" : ""}`} onClick={() => set({ level: v })}>
                <span className="t">{t}</span>
                <span className="d">{sub}</span>
              </button>
            ))}
          </div>
          <h2>Колко време имаш седмично?</h2>
          <div className="card center">
            <div style={{ fontSize: "2.2rem", fontWeight: 800 }}>{d.weeklyHours} ч</div>
            <input type="range" min={2} max={15} step={0.5} value={d.weeklyHours}
              onChange={(e) => set({ weeklyHours: +e.target.value })} />
          </div>
          <h2 className="mt">В кои дни можеш да тренираш?</h2>
          <div className="day-chips">
            {DAYS.map((day, i) => (
              <button key={i} className={d.days.includes(i) ? "on" : ""}
                onClick={() => set({ days: d.days.includes(i) ? d.days.filter((x) => x !== i) : [...d.days, i].sort() })}>
                {day}
              </button>
            ))}
          </div>
          {d.days.length < 2 && <p className="hint mt">Избери поне 2 дни.</p>}

          <h2 className="mt">Допълнителни модули</h2>
          <p className="sub" style={{ marginBottom: 10 }}>
            Кратки сесии, които пазят от контузии. Избери каквото ти допада (или нищо).
          </p>
          <div className="opts cols2">
            <button className={`opt ${d.strength ? "selected" : ""}`} onClick={() => set({ strength: !d.strength })}>
              <span className="t">💪 Силови</span>
              <span className="d">1-2× седмично по ~30 мин, вкъщи</span>
            </button>
            <button className={`opt ${d.stretching ? "selected" : ""}`} onClick={() => set({ stretching: !d.stretching })}>
              <span className="t">🧘 Стречинг</span>
              <span className="d">2× седмично по ~12 мин, след тренировка</span>
            </button>
          </div>

          {d.strength && (
            <>
              <h2 className="mt">Къде ще правиш силовите?</h2>
              <div className="opts">
                {([
                  ["home", "🏠 Вкъщи, без екипировка", "Собствено тегло — раница с книги върши работа"],
                  ["dumbbells", "🏠 Вкъщи, имам дъмбели", "Дъмбели/пудовка — по-силен стимул от собственото тегло"],
                  ["gym", "🏋️ Във фитнес зала", "Щанги и машини — най-ефективното развитие на сила"],
                ] as const).map(([v, t, sub]) => (
                  <button key={v} className={`opt ${d.strengthSetting === v ? "selected" : ""}`}
                    onClick={() => set({ strengthSetting: v })}>
                    <span className="t">{t}</span>
                    <span className="d">{sub}</span>
                  </button>
                ))}
              </div>
            </>
          )}
        </>
      )}

      {step === 5 && (
        <>
          <h2>Каква е целта?</h2>
          <div className="opts cols2" style={{ marginBottom: 14 }}>
            <button className={`opt ${d.hasRace ? "selected" : ""}`} onClick={() => set({ hasRace: true })}>
              <span className="t">🏁 Готвя се за състезание</span>
            </button>
            <button className={`opt ${!d.hasRace ? "selected" : ""}`} onClick={() => set({ hasRace: false })}>
              <span className="t">📈 Искам прогрес</span>
            </button>
          </div>

          {d.hasRace ? (
            <>
              <div className="field">
                <label>Име на състезанието</label>
                <input type="text" value={d.raceName} onChange={(e) => set({ raceName: e.target.value })} placeholder="напр. Витоша 100" />
              </div>
              <div className="field">
                <label>Дата</label>
                <input type="date" value={d.raceDate} onChange={(e) => set({ raceDate: e.target.value })} />
              </div>
            </>
          ) : (
            <div className="card center">
              <div className="sub">Искам да видя резултати за</div>
              <div style={{ fontSize: "2rem", fontWeight: 800 }}>{d.weeks} седмици</div>
              <input type="range" min={4} max={24} value={d.weeks} onChange={(e) => set({ weeks: +e.target.value })} />
            </div>
          )}

          {isRun && (
            <>
              <h2 className="mt">Бягане</h2>
              <div className="field">
                <label>Тип цел</label>
                <select value={d.runGoalType} onChange={(e) => set({ runGoalType: e.target.value })}>
                  <option value="race_time">Време за дистанция</option>
                  <option value="race_pace">Целево темпо за дистанция</option>
                  <option value="finish">Просто да завърша дистанцията</option>
                  <option value="general">Обща форма</option>
                </select>
              </div>
              {d.runGoalType !== "general" && (
                <div className="field">
                  <label>Дистанция</label>
                  <select value={d.runDistance} onChange={(e) => set({ runDistance: e.target.value })}>
                    <option value="5k">5 км</option>
                    <option value="10k">10 км</option>
                    <option value="half_marathon">Полумаратон</option>
                    <option value="marathon">Маратон</option>
                  </select>
                </div>
              )}
              {d.runGoalType === "race_time" && (
                <div className="field">
                  <label>Целево време (ч : мин : сек)</label>
                  <div style={{ display: "flex", gap: 8 }}>
                    <input type="number" value={d.targetH} onChange={(e) => set({ targetH: e.target.value })} placeholder="ч" />
                    <input type="number" value={d.targetM} onChange={(e) => set({ targetM: e.target.value })} placeholder="мин" />
                    <input type="number" value={d.targetS} onChange={(e) => set({ targetS: e.target.value })} placeholder="сек" />
                  </div>
                </div>
              )}
              {d.runGoalType === "race_pace" && (
                <div className="field">
                  <label>Целево темпо (мин : сек / км)</label>
                  <div style={{ display: "flex", gap: 8 }}>
                    <input type="number" value={d.paceM} onChange={(e) => set({ paceM: e.target.value })} placeholder="мин" />
                    <input type="number" value={d.paceS} onChange={(e) => set({ paceS: e.target.value })} placeholder="сек" />
                  </div>
                </div>
              )}
            </>
          )}

          {isBike && (
            <>
              <h2 className="mt">Колоездене</h2>
              <div className="opts">
                {([["ftp", "⚡ Вдигане на FTP", "Повече мощност на прага — по-бърз навсякъде"],
                  ["endurance", "🛣️ Издръжливост", "По-дълги карания без да гориш"],
                  ["vo2max", "🫁 VO₂max", "Вдигане на аеробния таван"],
                  ["general", "🎯 Поддържане на форма", "Балансирана седмица без тежки блокове — стабилно добра кондиция"],
                  ["mixed", "🔄 Всичко по малко", "Редуване на sweet spot, VO₂max и праг — развива и трите системи"]] as const).map(([v, t, sub]) => (
                  <button key={v} className={`opt ${d.bikeGoalType === v ? "selected" : ""}`} onClick={() => set({ bikeGoalType: v })}>
                    <span className="t">{t}</span>
                    <span className="d">{sub}</span>
                  </button>
                ))}
              </div>
            </>
          )}

          {weeksWarning && <div className="warning mt">⚠️ <span>{weeksWarning}</span></div>}
        </>
      )}

      {step === 6 && (
        <>
          <h2>Готови сме! 🎉</h2>
          <div className="card">
            <p className="sub">
              {d.sport === "run" ? "🏃 Бягане" : d.sport === "bike" ? "🚴 Колоездене" : "🏃🚴 Бягане + колоездене"} ·{" "}
              {d.weeklyHours} ч/седмица · {d.days.length} тренировъчни дни
              {d.hasRace ? ` · 🏁 ${d.raceName}` : ` · ${d.weeks} седмици план`}
            </p>
          </div>
          {weeksWarning && <div className="warning">⚠️ <span>{weeksWarning}</span></div>}
          {warnings.map((w, i) => <div className="warning" key={i}>⚠️ <span>{w}</span></div>)}
          {err && <div className="warning">❌ <span>{err}</span></div>}
          <p className="sub" style={{ marginBottom: 16 }}>
            Ще изготвя научно обоснована прогресивна програма (VDOT на Даниелс за бягане, зони на Коган за колоездене),
            съобразена с твоите данни, време и екипировка. След всяка тренировка ще ме учиш какво работи за теб.
          </p>
          <button className="btn" disabled={busy} onClick={finish}>
            {busy ? <span className="spin">⚙️</span> : "Генерирай програмата ми"}
          </button>
        </>
      )}

      {step < 6 && (
        <div style={{ display: "flex", gap: 10, marginTop: 24 }}>
          {step > 0 && (
            <button className="btn ghost" style={{ width: "35%" }} onClick={() => setStep(step - 1)}>Назад</button>
          )}
          <button className="btn" disabled={!canNext} onClick={() => setStep(step + 1)}>Напред</button>
        </div>
      )}
    </div>
  );
}
