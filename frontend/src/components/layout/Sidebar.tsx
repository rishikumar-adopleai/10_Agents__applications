import React from 'react';
import { NavLink } from 'react-router-dom';
import { Radio } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useAuthStore } from '@/store/authStore';

interface NavItem {
  name: string;
  to: string;
  icon?: React.ElementType;
  badge?: string;
  adminOnly?: boolean;
}

interface NavSection {
  title: string;
  items: NavItem[];
}

const navSections: NavSection[] = [
  {
    title: 'AGENT 1: BUYING-SIGNAL RADAR',
    items: [
      { name: 'Daily Top 20', to: '/radar' },
    ],
  },
  {
    title: 'AGENT 2: RESEARCH & PERSONAL OUTREACH',
    items: [
      { name: 'Research Overview', to: '/research/overview' },
      { name: 'Research Queue', to: '/research/queue' },
      { name: 'Company Intelligence', to: '/research/company' },
      { name: 'Contact Discovery', to: '/research/contacts' },
      { name: 'Outreach Studio', to: '/research/outreach' },
      { name: 'Approval Center', to: '/research/approvals' },
    ],
  },
  {
    title: 'AGENT 4: 24/7 LEAD RESPONDER',
    items: [
      { name: 'Responder Dashboard', to: '/responder/dashboard' },
      { name: 'Unified Inbox', to: '/responder/inbox' },
      { name: 'Calendar & Meetings', to: '/responder/meetings' },
      { name: 'Workflow Telemetry', to: '/responder/monitoring' },
    ],
  },
];

export const Sidebar: React.FC = () => {
  const { user } = useAuthStore();
  const isAdmin = user?.roles.some((r) => r.name === 'ADMINISTRATOR' || r.name === 'SALES_MANAGER');

  const userInitials = user?.first_name && user?.last_name
    ? `${user.first_name[0]}${user.last_name[0]}`.toUpperCase()
    : 'AU';
  const displayName = user?.first_name ? `${user.first_name} ${user.last_name}` : 'Admin User';
  const displayRole = user?.roles?.[0]?.name ? user.roles[0].name.replace('_', ' ') : 'Administrator';

  return (
    <aside className="w-56 bg-white flex flex-col h-screen sticky top-0 select-none text-slate-700 border-r border-slate-200 shrink-0 shadow-xs">
      {/* Brand Header */}
      <div className="h-16 flex items-center px-4 pt-2 border-b border-slate-100">
        <div className="flex items-center space-x-2.5">
          <div className="w-7 h-7 rounded-lg bg-indigo-600 flex items-center justify-center text-white font-bold shadow-xs shrink-0">
            <Radio className="w-4 h-4 text-white" />
          </div>
          <div className="min-w-0">
            <span className="font-bold text-xs tracking-tight text-slate-900 block truncate">
              Enterprise Sales
            </span>
            <span className="text-[9px] text-slate-500 font-semibold tracking-wider uppercase block">
              SIGNAL RADAR
            </span>
          </div>
        </div>
      </div>

      {/* Nav Sections */}
      <nav className="flex-1 overflow-y-auto px-3 py-4 space-y-6">
        {navSections.map((section) => (
          <div key={section.title} className="space-y-1">
            <div className="px-2 text-[9px] font-bold text-slate-400 uppercase tracking-wider mb-2">
              {section.title}
            </div>
            {section.items.map((item) => {
              if (item.adminOnly && !isAdmin) return null;

              return (
                <NavLink
                  key={item.name}
                  to={item.to}
                  className={({ isActive }) =>
                    cn(
                      'flex items-center justify-between px-2.5 py-2 rounded-lg text-xs transition-colors',
                      isActive
                        ? 'bg-indigo-50/80 text-indigo-700 font-semibold border border-indigo-100/70'
                        : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900 font-medium'
                    )
                  }
                >
                  <span className="truncate">{item.name}</span>
                </NavLink>
              );
            })}
          </div>
        ))}
      </nav>

      {/* User Profile Footer */}
      <div className="p-4 border-t border-slate-200 bg-white">
        <div className="flex items-center space-x-3 min-w-0">
          <div className="w-8 h-8 rounded-full bg-slate-100 border border-slate-200 text-slate-700 text-xs font-bold flex items-center justify-center shrink-0">
            {userInitials}
          </div>
          <div className="min-w-0 flex-1">
            <p className="text-xs font-semibold text-slate-900 truncate leading-tight">
              {displayName}
            </p>
            <p className="text-[10px] text-slate-500 truncate leading-tight capitalize">
              {displayRole.toLowerCase()}
            </p>
          </div>
        </div>
      </div>
    </aside>
  );
};
