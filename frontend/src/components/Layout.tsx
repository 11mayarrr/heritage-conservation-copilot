import { useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { getUserName, setUserName } from "../api/client";

const SCOPED = ["/atlas", "/review", "/treatments"];

export function Layout() {
  const loc = useLocation();
  const [user, setUser] = useState(getUserName());
  // Keep the open case when moving between the case-scoped sections.
  const m = loc.pathname.match(/^\/(atlas|review|treatments)\/([\w-]+)/);
  const caseId = m?.[2] ?? new URLSearchParams(loc.search).get("id");
  const scoped = (p: string) => (caseId ? `${p}/${caseId}` : p);

  const items: [string, string][] = [
    ["/", "لوحة التحكم"],
    ["/upload", "رفع وتحليل الصور"],
    [scoped("/atlas"), "خريطة التلف"],
    [scoped("/review"), "المراجعة والتصحيح"],
    [scoped("/treatments"), "المعالجة والمواد"],
    ["/compare", "المقارنة الزمنية"],
    [caseId ? `/reports?id=${caseId}` : "/reports", "التقارير"],
    ["/knowledge", "قاعدة المعرفة"],
    ["/audit", "سجل التعديلات"],
  ];

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">ط</div>
          <div>
            <b>مساعد ترميم التراث الطيني</b>
            <small>Heritage Conservation Copilot</small>
          </div>
        </div>
        <nav className="nav" aria-label="الأقسام">
          {items.map(([to, label], i) => (
            <NavLink
              key={label}
              to={to}
              end={to === "/"}
              className={({ isActive }) =>
                isActive || (SCOPED.some((s) => to.startsWith(s)) && loc.pathname.startsWith(to.split("/").slice(0, 2).join("/")))
                  ? "active"
                  : ""
              }
            >
              <span className="num">{i + 1}</span>
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="user">
          <label style={{ color: "#c9bda8" }}>
            اسم المختص (يظهر في سجل التعديلات)
            <input
              value={user}
              onChange={(e) => {
                setUser(e.target.value);
                setUserName(e.target.value);
              }}
            />
          </label>
          <small style={{ color: "#a99c86" }}>نموذج أولي: لا يوجد تسجيل دخول حقيقي بعد.</small>
        </div>
      </aside>
      <main className="main">
        <Outlet />
      </main>
    </div>
  );
}
