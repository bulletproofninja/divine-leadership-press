import '@/App.css';
import 'react-quill-new/dist/quill.snow.css';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { useState, useEffect } from 'react';
import axios from 'axios';
import LandingPage from './pages/LandingPage';
import Dashboard from './pages/Dashboard';
import EditorPage from './pages/EditorPage';
import HelpPage from './pages/HelpPage';
import AdminAffiliatePage from './pages/AdminAffiliatePage';
import BillingPage from './pages/BillingPage';
import BillingSuccess from './pages/BillingSuccess';
import AdminCommissionsPage from './pages/AdminCommissionsPage';
import AffiliateConnectReturn from './pages/AffiliateConnectReturn';
import SettingsPage from './pages/SettingsPage';
import ResetPasswordPage from './pages/ResetPasswordPage';
import PublishingCenterPage from './pages/PublishingCenterPage';
import { Toaster } from './components/ui/sonner';

function App() {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem('token');
    if (!token) {
      setLoading(false);
      return;
    }
    axios.get(`${process.env.REACT_APP_BACKEND_URL}/api/auth/me`, {
      headers: { Authorization: `Bearer ${token}` },
      withCredentials: true,
    })
      .then((response) => {
        localStorage.setItem('user', JSON.stringify(response.data));
        setUser(response.data);
      })
      .catch(() => {
        localStorage.removeItem('token');
        localStorage.removeItem('user');
        setUser(null);
      })
      .finally(() => setLoading(false));
  }, []);

  const handleLogin = (token, userData) => {
    localStorage.setItem('token', token);
    localStorage.setItem('user', JSON.stringify(userData));
    setUser(userData);
  };

  const handleLogout = async () => {
    try {
      await axios.post(
        `${process.env.REACT_APP_BACKEND_URL}/api/auth/logout`,
        {},
        { withCredentials: true },
      );
    } finally {
      localStorage.removeItem('token');
      localStorage.removeItem('user');
      setUser(null);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-background">
        <div className="text-xl font-heading">Loading...</div>
      </div>
    );
  }

  return (
    <>
      <div className="noise-overlay" />
      <BrowserRouter>
        <Routes>
          <Route
            path="/"
            element={
              user ? (
                <Navigate to="/dashboard" replace />
              ) : (
                <LandingPage onLogin={handleLogin} />
              )
            }
          />
          <Route
            path="/dashboard"
            element={
              user ? (
                <Dashboard user={user} onLogout={handleLogout} />
              ) : (
                <Navigate to="/" replace />
              )
            }
          />
          <Route
            path="/editor/:documentId"
            element={
              user ? (
                <EditorPage user={user} onLogout={handleLogout} />
              ) : (
                <Navigate to="/" replace />
              )
            }
          />
          <Route path="/help" element={<HelpPage />} />
          <Route path="/reset-password" element={<ResetPasswordPage />} />
          <Route
            path="/billing"
            element={
              user ? (
                <BillingPage user={user} />
              ) : (
                <Navigate to="/" replace />
              )
            }
          />
          <Route
            path="/billing/success"
            element={
              user ? (
                <BillingSuccess />
              ) : (
                <Navigate to="/" replace />
              )
            }
          />
          <Route
            path="/admin/affiliate"
            element={
              user ? (
                <AdminAffiliatePage user={user} />
              ) : (
                <Navigate to="/" replace />
              )
            }
          />
          <Route
            path="/admin/commissions"
            element={
              user ? (
                <AdminCommissionsPage user={user} />
              ) : (
                <Navigate to="/" replace />
              )
            }
          />
          <Route
            path="/affiliate/connect/return"
            element={
              user ? (
                <AffiliateConnectReturn />
              ) : (
                <Navigate to="/" replace />
              )
            }
          />
          <Route
            path="/affiliate/connect/refresh"
            element={
              user ? (
                <AffiliateConnectReturn refreshMode />
              ) : (
                <Navigate to="/" replace />
              )
            }
          />
          <Route
            path="/publishing"
            element={user ? <PublishingCenterPage /> : <Navigate to="/" replace />}
          />
          <Route
            path="/settings"
            element={
              user ? (
                <SettingsPage user={user} setUser={setUser} />
              ) : (
                <Navigate to="/" replace />
              )
            }
          />
        </Routes>
      </BrowserRouter>
      <Toaster />
    </>
  );
}

export default App;
