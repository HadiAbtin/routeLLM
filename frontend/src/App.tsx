import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Login } from './pages/Login';
import { ChangePassword } from './pages/ChangePassword';
import { Dashboard } from './pages/Dashboard';
import { Providers } from './pages/Providers';
import { Keys } from './pages/Keys';
import { KeyDetails } from './pages/KeyDetails';
import { Runs } from './pages/Runs';
import { Settings } from './pages/Settings';
import { RequireAuth } from './components/RequireAuth';
import { useAuthStore } from './store/authStore';
import { useEffect } from 'react';

function App() {
  const { token, fetchUser } = useAuthStore();

  useEffect(() => {
    if (token) {
      fetchUser();
    }
  }, [token, fetchUser]);

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route
          path="/change-password"
          element={
            <RequireAuth>
              <ChangePassword />
            </RequireAuth>
          }
        />
        <Route
          path="/dashboard"
          element={
            <RequireAuth>
              <Dashboard />
            </RequireAuth>
          }
        />
        <Route
          path="/providers"
          element={
            <RequireAuth>
              <Providers />
            </RequireAuth>
          }
        />
        <Route
          path="/keys"
          element={
            <RequireAuth>
              <Keys />
            </RequireAuth>
          }
        />
        <Route
          path="/keys/:id"
          element={
            <RequireAuth>
              <KeyDetails />
            </RequireAuth>
          }
        />
        <Route
          path="/runs"
          element={
            <RequireAuth>
              <Runs />
            </RequireAuth>
          }
        />
        <Route
          path="/settings"
          element={
            <RequireAuth>
              <Settings />
            </RequireAuth>
          }
        />
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
