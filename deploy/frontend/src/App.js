import "@/index.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Toaster } from "@/components/ui/sonner";
import { AuthProvider, useAuth } from "@/context/AuthContext";
import LoginPage from "@/pages/LoginPage";
import ChangePasswordPage from "@/pages/ChangePasswordPage";
import ChangeCredentialsPage from "@/pages/ChangeCredentialsPage";
import LaunchpadPage from "@/pages/LaunchpadPage";
import AdminLayout from "@/pages/admin/AdminLayout";
import AppsPage from "@/pages/admin/AppsPage";
import UsersPage from "@/pages/admin/UsersPage";
import RolesPage from "@/pages/admin/RolesPage";
import EmployeesPage from "@/pages/admin/EmployeesPage";
import SettingsPage from "@/pages/admin/SettingsPage";
import CompaniesPage from "@/pages/admin/CompaniesPage";
import ApiKeysPage from "@/pages/admin/ApiKeysPage";
import CompanyAppsPage from "@/pages/admin/CompanyAppsPage";
import BrandingPage from "@/pages/admin/BrandingPage";
import AuditLogsPage from "@/pages/admin/AuditLogsPage";

const ProtectedRoute = ({ children, adminOnly = false }) => {
  const { user, loading, mustChangeCredentials } = useAuth();
  
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-white">
        <div className="animate-pulse text-gray-400">Loading...</div>
      </div>
    );
  }
  
  if (!user) {
    return <Navigate to="/login" replace />;
  }
  
  // Check if credential change is required (both email and password)
  if (mustChangeCredentials.email && mustChangeCredentials.password) {
    return <Navigate to="/change-credentials" replace />;
  }
  
  // Check if password change is required
  if (mustChangeCredentials.password || user.must_change_password) {
    return <Navigate to="/change-password" replace />;
  }
  
  if (adminOnly && !['sysadmin', 'company_admin'].includes(user.role)) {
    return <Navigate to="/launchpad" replace />;
  }
  
  return children;
};

const PublicRoute = ({ children }) => {
  const { user, loading } = useAuth();
  
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-white">
        <div className="animate-pulse text-gray-400">Loading...</div>
      </div>
    );
  }
  
  if (user) {
    return <Navigate to="/launchpad" replace />;
  }
  
  return children;
};

function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={
        <PublicRoute>
          <LoginPage />
        </PublicRoute>
      } />
      <Route path="/change-password" element={<ChangePasswordPage />} />
      <Route path="/change-credentials" element={<ChangeCredentialsPage />} />
      <Route path="/launchpad" element={
        <ProtectedRoute>
          <LaunchpadPage />
        </ProtectedRoute>
      } />
      <Route path="/admin" element={
        <ProtectedRoute adminOnly>
          <AdminLayout />
        </ProtectedRoute>
      }>
        <Route index element={<Navigate to="/admin/apps" replace />} />
        <Route path="companies" element={<CompaniesPage />} />
        <Route path="company-apps" element={<CompanyAppsPage />} />
        <Route path="apps" element={<AppsPage />} />
        <Route path="users" element={<UsersPage />} />
        <Route path="roles" element={<RolesPage />} />
        <Route path="employees" element={<EmployeesPage />} />
        <Route path="api-keys" element={<ApiKeysPage />} />
        <Route path="branding" element={<BrandingPage />} />
        <Route path="audit-logs" element={<AuditLogsPage />} />
        <Route path="settings" element={<SettingsPage />} />
      </Route>
      <Route path="/" element={<Navigate to="/launchpad" replace />} />
      <Route path="*" element={<Navigate to="/launchpad" replace />} />
    </Routes>
  );
}

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AppRoutes />
        <Toaster position="top-right" />
      </AuthProvider>
    </BrowserRouter>
  );
}

export default App;
