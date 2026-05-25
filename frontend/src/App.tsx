import React, { createContext, useContext, useEffect, useState } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import Layout from './components/Layout/Layout';
import Dashboard from './pages/Dashboard';
import Events from './pages/Events';
import Alerts from './pages/Alerts';
import Rules from './pages/Rules';
import Search from './pages/Search';
import ThreatIntel from './pages/ThreatIntel';
import Login from './pages/Login';
import { getMe } from './api/auth';

interface AuthContextValue {
  username: string | null;
  authChecked: boolean;
  setUsername: (u: string | null) => void;
}

export const AuthContext = createContext<AuthContextValue>({
  username: null,
  authChecked: false,
  setUsername: () => {},
});

const PrivateRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { username, authChecked } = useContext(AuthContext);
  if (!authChecked) return <div className="min-h-screen bg-[#0f1117]" />;
  return username ? <>{children}</> : <Navigate to="/login" replace />;
};

const App: React.FC = () => {
  const [username, setUsername] = useState<string | null>(null);
  const [authChecked, setAuthChecked] = useState(false);

  useEffect(() => {
    getMe().then((u) => {
      setUsername(u);
      setAuthChecked(true);
    });
  }, []);

  return (
    <AuthContext.Provider value={{ username, authChecked, setUsername }}>
      <Routes>
        <Route
          path="/login"
          element={<Login onSuccess={(u) => setUsername(u)} />}
        />
        <Route
          path="/*"
          element={
            <PrivateRoute>
              <Layout>
                <Routes>
                  <Route path="/" element={<Dashboard />} />
                  <Route path="/events" element={<Events />} />
                  <Route path="/alerts" element={<Alerts />} />
                  <Route path="/rules" element={<Rules />} />
                  <Route path="/search" element={<Search />} />
                  <Route path="/threat-intel" element={<ThreatIntel />} />
                  <Route path="*" element={<Navigate to="/" replace />} />
                </Routes>
              </Layout>
            </PrivateRoute>
          }
        />
      </Routes>
    </AuthContext.Provider>
  );
};

export default App;
