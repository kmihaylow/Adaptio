import { useEffect, useState } from "react";
import Login from "./screens/Login";
import Onboarding from "./screens/Onboarding";
import Dashboard from "./screens/Dashboard";
import Today from "./screens/Today";
import PlanScreen from "./screens/PlanScreen";
import Settings from "./screens/Settings";
import { api, clearToken, getToken } from "./api";

type Tab = "progress" | "today" | "plan" | "settings";

export default function App() {
  // null = loading, "login" = needs auth, "onboarding" = no plan yet, "app" = ready
  const [stage, setStage] = useState<"loading" | "login" | "onboarding" | "app">("loading");
  const [backendDown, setBackendDown] = useState(false);
  const [tab, setTab] = useState<Tab>("progress");

  function boot() {
    setStage("loading");
    setBackendDown(false);
    api.checkHealth().then((ok) => {
      if (!ok) { setBackendDown(true); return; }
      if (!getToken()) { setStage("login"); return; }
      api.getPlan()
        .then(() => setStage("app"))
        .catch(() => setStage(getToken() ? "onboarding" : "login"));
    });
  }

  useEffect(boot, []);

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
  if (stage === "loading") {
    return <div className="screen center" style={{ paddingTop: "40vh" }}><span className="spin">⚙️</span></div>;
  }
  if (stage === "login") {
    return <Login onLogin={boot} />;
  }
  if (stage === "onboarding") {
    return <Onboarding onComplete={() => { setStage("app"); setTab("plan"); }} />;
  }

  return (
    <>
      {tab === "progress" && <Dashboard />}
      {tab === "today" && <Today />}
      {tab === "plan" && <PlanScreen />}
      {tab === "settings" && (
        <Settings
          onReset={() => setStage("onboarding")}
          onLogout={() => { api.logout().catch(() => {}); clearToken(); setStage("login"); }}
        />
      )}
      <nav className="nav">
        <button className={tab === "progress" ? "on" : ""} onClick={() => setTab("progress")}>
          <span className="ic">📈</span>Прогрес
        </button>
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
