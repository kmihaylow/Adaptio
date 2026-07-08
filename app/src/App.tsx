import { useEffect, useState } from "react";
import Onboarding from "./screens/Onboarding";
import Today from "./screens/Today";
import PlanScreen from "./screens/PlanScreen";
import Settings from "./screens/Settings";
import { api } from "./api";

type Tab = "today" | "plan" | "settings";

export default function App() {
  const [ready, setReady] = useState<boolean | null>(null); // null = loading
  const [backendDown, setBackendDown] = useState(false);
  const [tab, setTab] = useState<Tab>("today");

  function boot() {
    setReady(null);
    setBackendDown(false);
    api.checkHealth().then((ok) => {
      if (!ok) { setBackendDown(true); setReady(false); return; }
      api.getPlan().then(() => setReady(true)).catch(() => setReady(false));
    });
  }

  useEffect(boot, []);

  if (ready === null) {
    return <div className="screen center" style={{ paddingTop: "40vh" }}><span className="spin">⚙️</span></div>;
  }
  if (backendDown) {
    return (
      <div className="screen center" style={{ paddingTop: "30vh" }}>
        <div style={{ fontSize: "3rem" }}>🔌</div>
        <h2>Няма връзка със сървъра</h2>
        <p className="sub" style={{ textAlign: "center", maxWidth: 360 }}>
          Стартирай backend-а от папка <code>backend/</code>:
        </p>
        <pre style={{ background: "var(--card)", padding: "12px 16px", borderRadius: 8, fontSize: "0.85rem" }}>python -m adaptio.main</pre>
        <button className="btn mt" onClick={boot}>Опитай отново</button>
      </div>
    );
  }
  if (!ready) {
    return <Onboarding onComplete={() => { setReady(true); setTab("plan"); }} />;
  }

  return (
    <>
      {tab === "today" && <Today />}
      {tab === "plan" && <PlanScreen />}
      {tab === "settings" && <Settings onReset={() => setReady(false)} />}
      <nav className="nav">
        <button className={tab === "today" ? "on" : ""} onClick={() => setTab("today")}>
          <span className="ic">🎯</span>Днес
        </button>
        <button className={tab === "plan" ? "on" : ""} onClick={() => setTab("plan")}>
          <span className="ic">📅</span>Програма
        </button>
        <button className={tab === "settings" ? "on" : ""} onClick={() => setTab("settings")}>
          <span className="ic">⚙️</span>Настройки
        </button>
      </nav>
    </>
  );
}
