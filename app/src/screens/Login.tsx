import { useState } from "react";
import { api, setToken } from "../api";

export default function Login({ onLogin }: { onLogin: () => void }) {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit() {
    setBusy(true); setErr("");
    try {
      const r = mode === "login"
        ? await api.login(username, password)
        : await api.register(username, password);
      setToken(r.token);
      onLogin();
    } catch (e: any) {
      setErr(e.message);
      setBusy(false);
    }
  }

  const canSubmit = username.trim().length >= 3 && password.length >= 6;

  return (
    <div className="screen" style={{ paddingTop: "18vh", maxWidth: 420 }}>
      <h1 style={{ textAlign: "center" }}>
        <span className="brand">Adaptio</span>
      </h1>
      <p className="sub" style={{ textAlign: "center", marginBottom: 24 }}>
        Твоят личен адаптивен треньор
      </p>

      <div className="opts cols2" style={{ marginBottom: 18 }}>
        <button className={`opt ${mode === "login" ? "selected" : ""}`} onClick={() => { setMode("login"); setErr(""); }}>
          Вход
        </button>
        <button className={`opt ${mode === "register" ? "selected" : ""}`} onClick={() => { setMode("register"); setErr(""); }}>
          Регистрация
        </button>
      </div>

      <div className="field">
        <label>Потребителско име</label>
        <input type="text" autoCapitalize="none" value={username}
          onChange={(e) => setUsername(e.target.value)} placeholder="напр. kiril" />
      </div>
      <div className="field">
        <label>Парола {mode === "register" && <span className="sub">(поне 6 символа)</span>}</label>
        <input type="password" value={password}
          onChange={(e) => setPassword(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && canSubmit && submit()} placeholder="••••••" />
      </div>

      {err && <div className="warning">⚠️ <span>{err}</span></div>}

      <button className="btn mt" disabled={!canSubmit || busy} onClick={submit}>
        {busy ? <span className="spin">⚙️</span> : mode === "login" ? "Влез" : "Създай профил"}
      </button>

      {mode === "register" && (
        <p className="hint mt" style={{ textAlign: "center" }}>
          Данните ти се пазят отделно от другите потребители.
        </p>
      )}
    </div>
  );
}
