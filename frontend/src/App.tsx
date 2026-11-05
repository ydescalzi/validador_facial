import { lazy, Suspense } from "react";
import StudentPage from "./pages/StudentPage";

// El panel de administración se carga solo cuando se entra a /admin
const AdminPage = lazy(() => import("./pages/AdminPage"));

export default function App() {
  const esAdmin = window.location.pathname.replace(/\/+$/, "").endsWith("/admin");
  return esAdmin ? (
    <Suspense fallback={<p style={{ padding: 24 }}>Cargando panel…</p>}>
      <AdminPage />
    </Suspense>
  ) : <StudentPage />;
}
