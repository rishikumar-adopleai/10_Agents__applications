import React from 'react';
import { PageHeader } from '@/components/layout/PageHeader';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { formatCurrency, formatDate } from '@/lib/utils';
import { DollarSign, CheckCircle2, AlertCircle, Plus, FileText } from 'lucide-react';

const SAMPLE_DEALS = [
  {
    id: 'opp-101',
    name: 'Enterprise SOC-2 Platform Expansion',
    account: 'Acme Health Systems',
    amount: 180000,
    stage: 'Discovery Completed',
    discovery_verified: true,
    commercial_approval: 'Approved',
    close_date: '2026-12-15',
  },
  {
    id: 'opp-102',
    name: 'AI Agent Fleet Pilot',
    account: 'Apex Global Logistics',
    amount: 65000,
    stage: 'Discovery In Progress',
    discovery_verified: false,
    commercial_approval: 'Blocked (Requires Discovery)',
    close_date: '2026-12-30',
  },
  {
    id: 'opp-103',
    name: 'Unified Revenue Automation',
    account: 'Summit FinTech',
    amount: 240000,
    stage: 'Proposal Review',
    discovery_verified: true,
    commercial_approval: 'Pending Sales Manager Review',
    close_date: '2027-01-15',
  },
];

export const DealsPage: React.FC = () => {
  return (
    <div className="space-y-6">
      <PageHeader
        title="Deals & Commercial Desk"
        description="Active revenue pipeline. Deal Desk generates proposals only after discovery verification is logged."
        action={
          <Button>
            <Plus className="w-4 h-4 mr-2" />
            Create Opportunity
          </Button>
        }
      />

      <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 overflow-hidden shadow-xs">
        <table className="w-full text-left border-collapse text-sm">
          <thead>
            <tr className="border-b border-slate-200 dark:border-slate-800 bg-slate-50/75 dark:bg-slate-800/50 text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
              <th className="py-3 px-6">Opportunity</th>
              <th className="py-3 px-6">Account</th>
              <th className="py-3 px-6">Deal Value</th>
              <th className="py-3 px-6">Discovery Gate</th>
              <th className="py-3 px-6">Commercial Status</th>
              <th className="py-3 px-6">Target Close</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
            {SAMPLE_DEALS.map((deal) => (
              <tr key={deal.id} className="hover:bg-slate-50/50 dark:hover:bg-slate-800/40">
                <td className="py-3.5 px-6 font-semibold text-slate-900 dark:text-slate-100">
                  {deal.name}
                </td>
                <td className="py-3.5 px-6 text-xs text-slate-600 dark:text-slate-300">
                  {deal.account}
                </td>
                <td className="py-3.5 px-6 font-bold text-slate-900 dark:text-slate-100">
                  {formatCurrency(deal.amount)}
                </td>
                <td className="py-3.5 px-6">
                  {deal.discovery_verified ? (
                    <span className="inline-flex items-center text-xs text-emerald-600 font-semibold">
                      <CheckCircle2 className="w-4 h-4 mr-1" /> Verified
                    </span>
                  ) : (
                    <span className="inline-flex items-center text-xs text-amber-600 font-semibold">
                      <AlertCircle className="w-4 h-4 mr-1" /> Pending Discovery
                    </span>
                  )}
                </td>
                <td className="py-3.5 px-6">
                  <Badge
                    variant={
                      deal.commercial_approval.includes('Approved')
                        ? 'success'
                        : deal.commercial_approval.includes('Blocked')
                        ? 'danger'
                        : 'warning'
                    }
                  >
                    {deal.commercial_approval}
                  </Badge>
                </td>
                <td className="py-3.5 px-6 text-xs text-slate-400">{deal.close_date}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};
