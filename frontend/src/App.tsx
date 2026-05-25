import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import Layout from './components/Layout/Layout';
import Dashboard from './pages/Dashboard';
import Events from './pages/Events';
import Alerts from './pages/Alerts';
import Rules from './pages/Rules';
import Search from './pages/Search';
import ThreatIntel from './pages/ThreatIntel';
import Login from './pages/Login';
import { getToken } from './api/client';

const PrivateRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  return getToken() ? <>{children}</> : <Navigate to="/login" replace />;
};

const App: React.FC = () => {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
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
  );
};

export default App;
