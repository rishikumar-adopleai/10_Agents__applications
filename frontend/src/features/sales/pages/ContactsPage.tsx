import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { PageHeader } from '@/components/layout/PageHeader';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { LoadingState, ErrorState, EmptyState } from '@/components/ui/FeedbackStates';
import { apiClient } from '@/lib/apiClient';
import { StandardResponse, PaginatedResponse } from '@/types/api';
import { Contact } from '@/types/sales';
import { formatDate } from '@/lib/utils';
import { Users, Mail, Phone, ShieldX, UserCheck, Plus } from 'lucide-react';

export const ContactsPage: React.FC = () => {
  const [page, setPage] = useState(1);

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ['contacts', page],
    queryFn: async () => {
      const res = await apiClient.get<StandardResponse<PaginatedResponse<Contact>>>('/contacts', {
        params: { page, page_size: 15 },
      });
      return res.data.data;
    },
  });

  return (
    <div className="space-y-6">
      <PageHeader
        title="Enterprise Contacts"
        description="Prospective buyers and decision makers. Centrally protected by 3-attempt limit and suppression check."
        action={
          <Button>
            <Plus className="w-4 h-4 mr-2" />
            Add Contact
          </Button>
        }
      />

      {isLoading ? (
        <LoadingState message="Loading contacts..." />
      ) : isError ? (
        <ErrorState
          message={(error as Error)?.message || 'Failed to load contacts.'}
          onRetry={() => refetch()}
        />
      ) : !data || data.items.length === 0 ? (
        <EmptyState
          title="No contacts recorded"
          description="Enrich contacts through Research & Outreach or import from CRM."
        />
      ) : (
        <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 overflow-hidden shadow-xs">
          <table className="w-full text-left border-collapse text-sm">
            <thead>
              <tr className="border-b border-slate-200 dark:border-slate-800 bg-slate-50/75 dark:bg-slate-800/50 text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
                <th className="py-3 px-6">Contact</th>
                <th className="py-3 px-6">Email / Phone</th>
                <th className="py-3 px-6">Job Title</th>
                <th className="py-3 px-6">Outreach Attempts</th>
                <th className="py-3 px-6">Suppression Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
              {data.items.map((contact) => (
                <tr key={contact.id} className="hover:bg-slate-50/50 dark:hover:bg-slate-800/40">
                  <td className="py-3.5 px-6 font-semibold text-slate-900 dark:text-slate-100">
                    {contact.first_name} {contact.last_name}
                  </td>
                  <td className="py-3.5 px-6 text-xs font-mono text-slate-500">
                    <div>{contact.email}</div>
                    {contact.phone && <div className="text-slate-400">{contact.phone}</div>}
                  </td>
                  <td className="py-3.5 px-6 text-slate-600 dark:text-slate-300 text-xs">
                    {contact.job_title || 'Decision Maker'}
                  </td>
                  <td className="py-3.5 px-6">
                    <span className="font-mono text-xs px-2 py-0.5 rounded-sm bg-slate-100 dark:bg-slate-800 font-semibold">
                      0 / 3 max
                    </span>
                  </td>
                  <td className="py-3.5 px-6">
                    <Badge variant={contact.is_suppressed ? 'danger' : 'success'}>
                      {contact.is_suppressed ? 'Suppressed (Opted-Out)' : 'Eligible'}
                    </Badge>
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
