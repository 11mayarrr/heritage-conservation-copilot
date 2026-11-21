import { BrowserRouter, Route, Routes } from "react-router-dom";
import { AuthProvider, useAuth } from "./components/AuthProvider";
import { Layout } from "./components/Layout";
import Atlas from "./pages/Atlas";
import AuditLog from "./pages/AuditLog";
import Compare from "./pages/Compare";
import Dashboard from "./pages/Dashboard";
import Knowledge from "./pages/Knowledge";
import Login from "./pages/Login";
import Reports from "./pages/Reports";
import Review from "./pages/Review";
import Treatments from "./pages/Treatments";
import Upload from "./pages/Upload";

function Gate() {
  const { me, loading } = useAuth();
  if (loading) return <div className="empty">جارٍ التحميل…</div>;
  if (!me) return <Login />;
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<Dashboard />} />
          <Route path="upload" element={<Upload />} />
          <Route path="atlas/:id?" element={<Atlas />} />
          <Route path="review/:id?" element={<Review />} />
          <Route path="treatments/:id?" element={<Treatments />} />
          <Route path="compare" element={<Compare />} />
          <Route path="reports" element={<Reports />} />
          <Route path="knowledge" element={<Knowledge />} />
          <Route path="audit" element={<AuditLog />} />
          <Route path="*" element={<div className="empty">الصفحة غير موجودة.</div>} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <Gate />
    </AuthProvider>
  );
}
