import { useEffect, useState } from "react";
import Onboarding from "./screens/Onboarding";
import Today from "./screens/Today";
import PlanScreen from "./screens/PlanScreen";
import Settings from "./screens/Settings";
import { api } from "./api";

type Tab = "today" | "plan" | "settings";

export default function App() {
  const [ready, setReady] = useState<boolean | null>(null); // null = loading
  const [tab, setTab] = useState<Tab>("today");

  useEffect(() => {
    api.getPlan().then(() => setReady(true)).catch(() => setReady(false));
  }, []);

  if (ready === null) {
    return <div className="screen center" style={{ paddingTop: "40vh" }}><span className="spin">⚙️</span></div>;
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
