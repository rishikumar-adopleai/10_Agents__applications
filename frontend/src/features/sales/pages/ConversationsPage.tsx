import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { PageHeader } from '@/components/layout/PageHeader';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { LoadingState, ErrorState, EmptyState } from '@/components/ui/FeedbackStates';
import { apiClient } from '@/lib/apiClient';
import { StandardResponse, PaginatedResponse } from '@/types/api';
import { formatDate } from '@/lib/utils';
import { MessageSquare, PhoneCall, ShieldCheck, UserX } from 'lucide-react';

export const ConversationsPage: React.FC = () => {
  const [page, setPage] = useState(1);

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ['conversations', page],
    queryFn: async () => {
      const res = await apiClient.get<StandardResponse<PaginatedResponse<any>>>('/conversations', {
        params: { page, page_size: 15 },
      });
      return res.data.data;
    },
  });

  return (
    <div className="space-y-6">
      <PageHeader
        title="Inbound Conversations"
        description="24/7 Lead Responder messaging threads across SMS and email with private contact memory."
      />

      {isLoading ? (
        <LoadingState message="Loading conversations..." />
      ) : isError ? (
        <ErrorState
          message={(error as Error)?.message || 'Failed to load conversations.'}
          onRetry={() => refetch()}
        />
      ) : !data || data.items.length === 0 ? (
        <EmptyState
          title="No active conversations"
          description="Inbound SMS and email replies from verified prospects will appear here automatically."
        />
      ) : (
        <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 overflow-hidden shadow-xs">
          <table className="w-full text-left border-collapse text-sm">
            <thead>
              <tr className="border-b border-slate-200 dark:border-slate-800 bg-slate-50/75 dark:bg-slate-800/50 text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
                <th className="py-3 px-6">Channel</th>
                <th className="py-3 px-6">Contact / Number</th>
                <th className="py-3 px-6">Status</th>
                <th className="py-3 px-6">Human Takeover</th>
                <th className="py-3 px-6">Last Message</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
              {data.items.map((conv: any) => (
                <tr key={conv.id} className="hover:bg-slate-50/50 dark:hover:bg-slate-800/40">
                  <td className="py-3.5 px-6 font-semibold flex items-center space-x-2">
                    <MessageSquare className="w-4 h-4 text-brand-600" />
                    <span>{conv.channel || 'SMS'}</span>
                  </td>
                  <td className="py-3.5 px-6 font-mono text-xs text-slate-600 dark:text-slate-300">
                    {conv.contact_id || 'Inbound Lead'}
                  </td>
                  <td className="py-3.5 px-6">
                    <Badge variant={conv.status === 'active' ? 'success' : 'default'}>
                      {conv.status || 'Active'}
                    </Badge>
                  </td>
                  <td className="py-3.5 px-6 text-xs">
                    {conv.is_human_takeover ? (
                      <span className="text-amber-600 font-semibold">Human Handling</span>
                    ) : (
                      <span className="text-slate-400">Autonomous Responder</span>
                    )}
                  </td>
                  <td className="py-3.5 px-6 text-xs text-slate-400">
                    {formatDate(conv.updated_at || conv.created_at)}
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
