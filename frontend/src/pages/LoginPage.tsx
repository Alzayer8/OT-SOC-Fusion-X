import { useState } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";
import { Icon } from "../components/Icons";

export function LoginPage() {
  const auth = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const requestedFrom = (location.state as { from?: string } | null)?.from;
  const from =
    requestedFrom?.startsWith("/") && !requestedFrom.startsWith("//") ? requestedFrom : "/";

  if (auth.status === "authenticated") return <Navigate replace to={from} />;

  const submit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!username.trim() || !password) return;
    setBusy(true);
    setError(null);
    try {
      await auth.login(username.trim(), password);
      setPassword("");
      void navigate(from, { replace: true });
    } catch {
      setPassword("");
      setError("Sign in failed. Check the local username and password.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="login-page">
      <section className="login-card" aria-labelledby="login-title">
        <header className="login-card__brand">
          <span className="brand__mark" aria-hidden="true">
            <Icon name="shield" />
          </span>
          <div>
            <p className="page-header__eyebrow">Academic Synthetic Environment</p>
            <h1 id="login-title">OT-SOC Fusion X</h1>
            <p>Synthetic Oil &amp; Gas Transfer Lab</p>
          </div>
        </header>
        <div className="safety-banner">
          <strong>Synthetic / Offline</strong>
          <span>No live OT connection or process control</span>
        </div>
        <form className="login-form" onSubmit={(event) => void submit(event)}>
          <label>
            Username
            <input
              autoComplete="username"
              autoFocus
              maxLength={64}
              required
              value={username}
              onChange={(event) => setUsername(event.target.value)}
            />
          </label>
          <label>
            Password
            <input
              autoComplete="current-password"
              maxLength={128}
              required
              type={showPassword ? "text" : "password"}
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
          </label>
          <label className="checkbox-row">
            <input
              checked={showPassword}
              type="checkbox"
              onChange={(event) => setShowPassword(event.target.checked)}
            />
            Show password
          </label>
          {error ? (
            <p className="form-error" role="alert">
              {error}
            </p>
          ) : null}
          <button className="button" disabled={busy || !username.trim() || !password} type="submit">
            {busy ? "Signing in…" : "Sign In"}
          </button>
        </form>
        <p className="login-card__boundary">
          Local authenticated access only. Credentials are never stored in browser local storage.
        </p>
      </section>
    </main>
  );
}
