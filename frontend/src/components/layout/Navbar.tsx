import React, { useState } from 'react';
import { Search, LogOut } from 'lucide-react';
import { useAuthStore } from '@/store/authStore';
import { apiClient } from '@/lib/apiClient';

export const Navbar: React.FC = () => {
  const { logout } = useAuthStore();
  const [searchQuery, setSearchQuery] = useState('');

  const handleLogout = async () => {
    try {
      await apiClient.post('/auth/logout');
    } catch {
      // Ignored
    } finally {
      logout();
      window.location.href = '/login';
    }
  };

  return (
    <header className="h-16 bg-[#F8FAFC] flex items-center justify-between px-8 sticky top-0 z-30">
      {/* Left: Search input matching reference design */}
      <div className="flex items-center flex-1 max-w-md">
        <div className="relative w-80">
          <input
            type="text"
            placeholder="Search accounts, signals, contacts"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full px-3.5 py-1.5 bg-white border border-slate-200 rounded-lg text-xs text-slate-800 placeholder:text-slate-400 focus:outline-none focus:ring-1 focus:ring-indigo-500 shadow-2xs transition-all"
          />
        </div>
      </div>

      {/* Right: Actions */}
      <div className="flex items-center space-x-3">
        {/* Discreet logout button keeping functionality */}
        <button
          onClick={handleLogout}
          title="Sign Out"
          className="p-1.5 text-slate-400 hover:text-slate-700 hover:bg-slate-200/60 rounded-lg transition-colors text-xs"
        >
          <LogOut className="w-4 h-4" />
        </button>
      </div>
    </header>
  );
};
