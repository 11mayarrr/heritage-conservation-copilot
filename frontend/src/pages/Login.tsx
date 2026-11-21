import { useState, type FormEvent } from "react";
import { ApiError } from "../api/client";
import { useAuth } from "../components/AuthProvider";

export default function Login() {
  const { login } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    try {
      await login(username.trim(), password);
    } catch (x) {
      setErr(x instanceof ApiError ? x.message : "تعذر الاتصال بالخادم. تأكد أنه يعمل ثم أعد المحاولة.");
      setPassword("");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="login-wrap">
      <form className="card login-card" onSubmit={submit}>
        <div className="brand-mark" style={{ margin: "0 auto 10px" }}>ط</div>
        <h1 style={{ textAlign: "center", marginBottom: 4 }}>مساعد ترميم التراث الطيني</h1>
        <p className="muted" style={{ textAlign: "center", marginTop: 0 }}>
          سجّل الدخول بحساب الفريق. الوكيل يقترح، والمختص يقرر.
        </p>
        {err && <div className="banner danger" role="alert">{err}</div>}
        <label>
          اسم المستخدم
          <input
            dir="ltr"
            autoComplete="username"
            autoCapitalize="none"
            spellCheck={false}
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            required
            autoFocus
          />
        </label>
        <label>
          كلمة السر
          <input
            dir="ltr"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </label>
        <button className="primary" type="submit" disabled={busy || !username || !password} style={{ width: "100%" }}>
          {busy ? "جارٍ الدخول…" : "دخول"}
        </button>
        <p className="muted" style={{ fontSize: "0.8rem", marginBottom: 0 }}>
          لا يوجد تسجيل ذاتي. تُنشأ الحسابات من الفريق عبر <code dir="ltr">scripts/manage_users.py</code>.
        </p>
      </form>
    </div>
  );
}
