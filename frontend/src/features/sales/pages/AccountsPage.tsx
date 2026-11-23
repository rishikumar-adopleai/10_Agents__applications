import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { PageHeader } from '@/components/layout/PageHeader';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { LoadingState, ErrorState, EmptyState } from '@/components/ui/FeedbackStates';
import { apiClient } from '@/lib/apiClient';
import { StandardResponse, PaginatedResponse } from '@/types/api';
import { Account } from '@/types/sales';
import { formatDate } from '@/lib/utils';
import { Building2, Globe, Users, ExternalLink, Plus } from 'lucide-react';

export const AccountsPage: React.FC = () => {
  const [page, setPage] = useState(1);

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ['accounts', page],
    queryFn: async () => {
      const res = await apiClient.get<StandardResponse<PaginatedResponse<Account>>>('/accounts', {
        params: { page, page_size: 15 },
      });
      return res.data.data;
    },
  });

  return (
    <div className="space-y-6">
      <PageHeader
        title="Enterprise Accounts"
        description="Target enterprise accounts monitored for buying signals, tech stack changes, and outreach engagement."
        action={
          <Button>
            <Plus className="w-4 h-4 mr-2" />
            Add Account
          </Button>
        }
      />

      {isLoading ? (
        <LoadingState message="Loading accounts..." />
      ) : isError ? (
        <ErrorState
          message={(error as Error)?.message || 'Failed to load accounts.'}
          onRetry={() => refetch()}
        />
      ) : !data || data.items.length === 0 ? (
        <EmptyState
          title="No accounts registered"
          description="Add enterprise prospect accounts or let Buying-Signal Radar discover intent spikes."
        />
      ) : (
        <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 overflow-hidden shadow-xs">
          <table className="w-full text-left border-collapse text-sm">
            <thead>
              <tr className="border-b border-slate-200 dark:border-slate-800 bg-slate-50/75 dark:bg-slate-800/50 text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
                <th className="py-3 px-6">Company</th>
                <th className="py-3 px-6">Domain</th>
                <th className="py-3 px-6">Industry</th>
                <th className="py-3 px-6">Tier</th>
                <th className="py-3 px-6">Created</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
              {data.items.map((acc) => (
                <tr key={acc.id} className="hover:bg-slate-50/50 dark:hover:bg-slate-800/40">
                  <td className="py-3.5 px-6 font-semibold text-slate-900 dark:text-slate-100 flex items-center space-x-3">
                    <div className="w-8 h-8 rounded-lg bg-blue-50 dark:bg-blue-950/40 text-blue-600 flex items-center justify-center font-bold text-xs">
                      <Building2 className="w-4 h-4" />
                    </div>
                    <span>{acc.name}</span>
                  </td>
                  <td className="py-3.5 px-6 font-mono text-xs text-slate-500">
                    {acc.domain || '—'}
                  </td>
                  <td className="py-3.5 px-6 text-slate-600 dark:text-slate-300">
                    {acc.industry || 'General'}
                  </td>
                  <td className="py-3.5 px-6">
                    <Badge variant="info">{acc.tier || 'Standard'}</Badge>
                  </td>
                  <td className="py-3.5 px-6 text-xs text-slate-400">
                    {formatDate(acc.created_at)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};
