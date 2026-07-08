import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider, useAuth } from "./lib/auth";
import Layout from "./components/Layout";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import Projects from "./pages/Projects";
import ProjectDetail from "./pages/ProjectDetail";
import Procurement from "./pages/Procurement";
import Rfis from "./pages/Rfis";
import Claims from "./pages/Claims";
import Documents from "./pages/Documents";
import Meetings from "./pages/Meetings";
import SiteReports from "./pages/SiteReports";
import Reports from "./pages/Reports";
import Copilot from "./pages/Copilot";
import Approvals from "./pages/Approvals";
import Memory from "./pages/Memory";
import Audit from "./pages/Audit";
import { Spinner } from "./components/ui";

function Protected() {
  const { user, loading } = useAuth();
  if (loading)
    return (
      <div className="flex h-full items-center justify-center">
        <Spinner />
      </div>
    );
  if (!user) return <Navigate to="/login" replace />;
  return <Layout />;
}

function LoginRoute() {
  const { user, loading } = useAuth();
  if (loading) return null;
  if (user) return <Navigate to="/" replace />;
  return <Login />;
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginRoute />} />
          <Route element={<Protected />}>
            <Route path="/" element={<Dashboard />} />
            <Route path="/projects" element={<Projects />} />
            <Route path="/projects/:id" element={<ProjectDetail />} />
            <Route path="/procurement" element={<Procurement />} />
            <Route path="/rfis" element={<Rfis />} />
            <Route path="/claims" element={<Claims />} />
            <Route path="/meetings" element={<Meetings />} />
            <Route path="/site-reports" element={<SiteReports />} />
            <Route path="/documents" element={<Documents />} />
            <Route path="/reports" element={<Reports />} />
            <Route path="/copilot" element={<Copilot />} />
            <Route path="/approvals" element={<Approvals />} />
            <Route path="/memory" element={<Memory />} />
            <Route path="/audit" element={<Audit />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
