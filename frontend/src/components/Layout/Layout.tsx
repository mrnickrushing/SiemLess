import React from 'react';
import Sidebar from './Sidebar';

interface LayoutProps {
  children: React.ReactNode;
}

const Layout: React.FC<LayoutProps> = ({ children }) => {
  return (
    <div className="flex min-h-screen bg-cyber-bg">
      <Sidebar />
      <main className="flex-1 min-w-0 overflow-auto">
        <div className="min-h-screen p-6">
          {children}
        </div>
      </main>
    </div>
  );
};

export default Layout;
