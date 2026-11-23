import React, { useState, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import {
  Search,
  ExternalLink,
  Play,
  RotateCw,
  Sparkles,
  CheckCircle2,
  AlertCircle,
  Clock,
  Filter,
} from 'lucide-react';
import { apiClient } from '@/lib/apiClient';
import { StandardResponse } from '@/types/api';
import { LoadingState, EmptyState } from '@/components/ui/FeedbackStates';

interface QueueItem {
  account_id: string;
  company_name: string;
  domain: string;
  industry: string;
  priority_score: number;
  priority_tier: string;
  why_now: string;
  buying_signal: string;
  research_status: string;
  contacts_count: number;
  opportunity_offering: string;
  last_updated: string;
  is_synthetic: boolean;
}

export const ResearchQueuePage: React.FC = () => {
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [search, setSearch] = useState('');
  const [selectedIndustry, setSelectedIndustry] = useState('all');
  const [selectedPriority, setSelectedPriority] = useState('all');
  const [selectedStatus, setSelectedStatus] = useState('all');
  const [sortBy, setSortBy] = useState<'priority' | 'updated'>('priority');
  const [runningAccountIds, setRunningAccountIds] = useState<Record<string, boolean>>({});

  const { data: queueItems, isLoading } = useQuery({
    queryKey: ['research', 'queue', search, selectedIndustry, selectedPriority, selectedStatus],
    queryFn: async () => {
      const params = new URLSearchParams();
      if (search) params.append('search', search);
      if (selectedIndustry !== 'all') params.append('industry', selectedIndustry);
      if (selectedPriority !== 'all') params.append('priority', selectedPriority);
      if (selectedStatus !== 'all') params.append('research_status', selectedStatus);

      const res = await apiClient.get<StandardResponse<QueueItem[]>>(`/research/queue?${params.toString()}`);
      return res.data.data;
    },
  });

  const runResearchMutation = useMutation({
    mutationFn: async (accountId: string) => {
      setRunningAccountIds((prev) => ({ ...prev, [accountId]: true }));
      const res = await apiClient.post<StandardResponse<any>>(`/research/company/${accountId}/run`, {
        execution_mode: 'test',
      });
      return res.data.data;
    },
    onSuccess: (_, accountId) => {
      queryClient.invalidateQueries({ queryKey: ['research'] });
      setTimeout(() => {
        setRunningAccountIds((prev) => ({ ...prev, [accountId]: false }));
      }, 800);
    },
    onError: (_, accountId) => {
      setRunningAccountIds((prev) => ({ ...prev, [accountId]: false }));
    },
  });

  const sortedItems = useMemo(() => {
    if (!queueItems) return [];
    const list = [...queueItems];
    if (sortBy === 'priority') {
      list.sort((a, b) => b.priority_score - a.priority_score);
    } else {
      list.sort((a, b) => new Date(b.last_updated).getTime() - new Date(a.last_updated).getTime());
    }
    return list;
  }, [queueItems, sortBy]);

  const industries = ['All', 'Healthcare technology', 'Logistics & Supply Chain', 'Financial Services', 'Technology'];
  const priorities = ['All', 'High', 'Medium', 'Low'];
  const statuses = ['All', 'Pending', 'Researching', 'Completed', 'Needs Review', 'Blocked', 'Failed'];

  const getStatusBadge = (statusStr: string) => {
    switch (statusStr.toLowerCase()) {
      case 'completed':
        return (
          <span className="bg-emerald-50 text-emerald-700 border border-emerald-200 rounded-full px-2 py-0.5 text-[10px] font-medium flex items-center space-x-1 w-max">
            <CheckCircle2 className="w-2.5 h-2.5" />
            <span>Completed</span>
          </span>
        );
      case 'researching':
        return (
          <span className="bg-indigo-50 text-indigo-700 border border-indigo-200 rounded-full px-2 py-0.5 text-[10px] font-medium flex items-center space-x-1 w-max animate-pulse">
            <RotateCw className="w-2.5 h-2.5 animate-spin" />
            <span>Researching...</span>
          </span>
        );
      case 'needs review':
        return (
          <span className="bg-amber-50 text-amber-800 border border-amber-200 rounded-full px-2 py-0.5 text-[10px] font-medium flex items-center space-x-1 w-max">
            <Clock className="w-2.5 h-2.5" />
            <span>Needs Review</span>
          </span>
        );
      case 'blocked':
        return (
          <span className="bg-rose-50 text-rose-700 border border-rose-200 rounded-full px-2 py-0.5 text-[10px] font-medium flex items-center space-x-1 w-max">
            <AlertCircle className="w-2.5 h-2.5" />
            <span>Blocked</span>
          </span>
        );
      default:
        return (
          <span className="bg-slate-100 text-slate-600 border border-slate-200 rounded-full px-2 py-0.5 text-[10px] font-medium flex items-center space-x-1 w-max">
            <span>Pending</span>
          </span>
        );
    }
  };

  return (
    <div className="space-y-5">
      {/* 1. Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between pb-3 border-b border-slate-200 gap-3">
        <div>
          <div className="flex items-center space-x-2.5">
            <h1 className="text-xl font-bold tracking-tight text-slate-900">Research Queue</h1>
            <span className="bg-indigo-50 text-indigo-700 border border-indigo-200/80 rounded-full px-2.5 py-0.5 text-[10px] font-semibold">
              {queueItems?.length || 0} Accounts Ready
            </span>
          </div>
          <p className="text-xs text-slate-500 mt-1">
            Prioritized enterprise accounts staged from Buying-Signal Radar for deep company research and outreach drafting.
          </p>
        </div>

        <div className="flex items-center space-x-2">
          <button
            onClick={() => {
              if (queueItems && queueItems.length > 0) {
                runResearchMutation.mutate(queueItems[0].account_id);
              }
            }}
            disabled={runResearchMutation.isPending}
            className="px-3.5 py-1.5 text-xs font-semibold text-white bg-[#201D6E] hover:bg-[#1a1758] rounded-lg shadow-2xs transition-colors disabled:opacity-60 flex items-center space-x-1.5"
          >
            <Play className="w-3 h-3 fill-current" />
            <span>Process Next Account</span>
          </button>
        </div>
      </div>

      {/* 2. Filters & Search Bar */}
      <div className="p-3.5 bg-white rounded-xl border border-slate-200/90 shadow-2xs space-y-3">
        <div className="flex flex-col md:flex-row md:items-center gap-3 justify-between">
          <div className="relative flex-1 max-w-md">
            <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-2.5" />
            <input
              type="text"
              placeholder="Search by company name, domain, or buying signal..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full pl-9 pr-3.5 py-1.5 bg-slate-50 border border-slate-200 rounded-lg text-xs text-slate-800 placeholder:text-slate-400 focus:outline-none focus:ring-1 focus:ring-indigo-500"
            />
          </div>

          <div className="flex flex-wrap items-center gap-2 text-xs">
            {/* Sort Toggle */}
            <div className="flex items-center space-x-1 bg-slate-100 p-0.5 rounded-lg border border-slate-200/60">
              <button
                onClick={() => setSortBy('priority')}
                className={`px-2.5 py-1 rounded-md text-[11px] font-semibold transition-colors ${
                  sortBy === 'priority' ? 'bg-white text-slate-900 shadow-2xs' : 'text-slate-500 hover:text-slate-800'
                }`}
              >
                Sort: Priority
              </button>
              <button
                onClick={() => setSortBy('updated')}
                className={`px-2.5 py-1 rounded-md text-[11px] font-semibold transition-colors ${
                  sortBy === 'updated' ? 'bg-white text-slate-900 shadow-2xs' : 'text-slate-500 hover:text-slate-800'
                }`}
              >
                Sort: Updated
              </button>
            </div>
          </div>
        </div>

        {/* Filter Pills */}
        <div className="flex flex-wrap items-center gap-2 pt-1 text-xs">
          <span className="text-[11px] text-slate-400 flex items-center space-x-1 mr-1">
            <Filter className="w-3 h-3" />
            <span>Filter:</span>
          </span>

          <select
            value={selectedIndustry}
            onChange={(e) => setSelectedIndustry(e.target.value)}
            className="px-2.5 py-1 bg-slate-50 border border-slate-200 rounded-lg text-[11px] text-slate-700 font-medium"
          >
            {industries.map((ind) => (
              <option key={ind} value={ind.toLowerCase()}>
                Industry: {ind}
              </option>
            ))}
          </select>

          <select
            value={selectedPriority}
            onChange={(e) => setSelectedPriority(e.target.value)}
            className="px-2.5 py-1 bg-slate-50 border border-slate-200 rounded-lg text-[11px] text-slate-700 font-medium"
          >
            {priorities.map((pri) => (
              <option key={pri} value={pri.toLowerCase()}>
                Priority: {pri}
              </option>
            ))}
          </select>

          <select
            value={selectedStatus}
            onChange={(e) => setSelectedStatus(e.target.value)}
            className="px-2.5 py-1 bg-slate-50 border border-slate-200 rounded-lg text-[11px] text-slate-700 font-medium"
          >
            {statuses.map((st) => (
              <option key={st} value={st.toLowerCase()}>
                Status: {st}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* 3. Research Queue Data Table */}
      {isLoading ? (
        <LoadingState message="Loading research queue..." />
      ) : sortedItems.length === 0 ? (
        <EmptyState
          title="No companies in queue matching filter"
          description="Clear search or adjust filters to view staged target companies."
          actionLabel="Reset Filters"
          onAction={() => {
            setSearch('');
            setSelectedIndustry('all');
            setSelectedPriority('all');
            setSelectedStatus('all');
          }}
        />
      ) : (
        <div className="bg-white rounded-xl border border-slate-200/90 shadow-2xs overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse min-w-[1050px]">
              <thead>
                <tr className="border-b border-slate-100 text-[10px] font-bold text-slate-400 uppercase tracking-wider bg-slate-50/50">
                  <th className="py-3 px-4 w-52">COMPANY</th>
                  <th className="py-3 px-3 w-40">INDUSTRY</th>
                  <th className="py-3 px-3 w-36">PRIORITY</th>
                  <th className="py-3 px-4 min-w-[220px]">BUYING SIGNAL</th>
                  <th className="py-3 px-3 w-32">STATUS</th>
                  <th className="py-3 px-3 w-28 text-center">CONTACTS</th>
                  <th className="py-3 px-4 w-48">OPPORTUNITY</th>
                  <th className="py-3 px-3 w-32 text-right">ACTIONS</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-xs">
                {sortedItems.map((item) => {
                  const isRunning = runningAccountIds[item.account_id];
                  return (
                    <tr
                      key={item.account_id}
                      className="hover:bg-slate-50/70 transition-colors cursor-pointer"
                      onClick={() => navigate(`/research/company/${item.account_id}`)}
                    >
                      {/* Company & Domain */}
                      <td className="py-3.5 px-4 align-middle">
                        <div className="font-bold text-xs text-slate-900 truncate">
                          {item.company_name}
                        </div>
                        <a
                          href={`https://${item.domain}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          onClick={(e) => e.stopPropagation()}
                          className="text-[11px] text-slate-400 hover:text-slate-600 truncate block mt-0.5"
                        >
                          {item.domain}
                        </a>
                      </td>

                      {/* Industry */}
                      <td className="py-3.5 px-3 align-middle text-slate-600 truncate">
                        {item.industry}
                      </td>

                      {/* Priority Score & Progress */}
                      <td className="py-3.5 px-3 align-middle">
                        <div className="flex items-center space-x-2">
                          <span className="font-bold text-xs text-slate-900">
                            {item.priority_score}%
                          </span>
                          <div className="w-12 bg-slate-200 h-1.5 rounded-full overflow-hidden shrink-0">
                            <div
                              className="bg-[#201D6E] h-full rounded-full"
                              style={{ width: `${item.priority_score}%` }}
                            />
                          </div>
                        </div>
                        <span className="text-[10px] text-slate-400 capitalize block mt-0.5">
                          {item.priority_tier} Tier
                        </span>
                      </td>

                      {/* Buying Signal */}
                      <td className="py-3.5 px-4 align-middle">
                        <p className="text-xs text-slate-700 leading-snug break-words">
                          {item.buying_signal}
                        </p>
                      </td>

                      {/* Research Status */}
                      <td className="py-3.5 px-3 align-middle">
                        {isRunning ? (
                          <span className="bg-indigo-50 text-indigo-700 border border-indigo-200 rounded-full px-2 py-0.5 text-[10px] font-medium flex items-center space-x-1 w-max animate-pulse">
                            <RotateCw className="w-2.5 h-2.5 animate-spin" />
                            <span>Running...</span>
                          </span>
                        ) : (
                          getStatusBadge(item.research_status)
                        )}
                      </td>

                      {/* Contacts Found */}
                      <td className="py-3.5 px-3 text-center align-middle">
                        <span className="inline-flex items-center justify-center px-2 py-0.5 rounded-full text-[11px] font-bold bg-slate-100 text-slate-800">
                          {item.contacts_count}
                        </span>
                      </td>

                      {/* Opportunity Offering */}
                      <td className="py-3.5 px-4 align-middle">
                        <span className="text-xs text-slate-800 font-medium truncate block">
                          {item.opportunity_offering}
                        </span>
                      </td>

                      {/* Actions */}
                      <td className="py-3.5 px-3 align-middle text-right">
                        <div className="flex items-center justify-end space-x-1.5" onClick={(e) => e.stopPropagation()}>
                          <button
                            onClick={() => runResearchMutation.mutate(item.account_id)}
                            disabled={isRunning}
                            className="p-1.5 bg-slate-100 hover:bg-indigo-50 text-slate-600 hover:text-indigo-600 rounded-md border border-slate-200/80 transition-colors"
                            title="Start or refresh research"
                          >
                            <RotateCw className={`w-3 h-3 ${isRunning ? 'animate-spin text-indigo-600' : ''}`} />
                          </button>
                          <button
                            onClick={() => navigate(`/research/company/${item.account_id}`)}
                            className="px-2.5 py-1 bg-white hover:bg-slate-50 text-slate-700 text-[11px] font-semibold rounded-md border border-slate-200 shadow-2xs transition-colors flex items-center space-x-1"
                          >
                            <span>Details</span>
                            <ExternalLink className="w-2.5 h-2.5" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          <div className="p-3 border-t border-slate-100 flex items-center justify-between text-xs text-slate-500 bg-white">
            <div>
              Showing {sortedItems.length} companies in research queue
            </div>
            <div className="text-slate-400">
              Active mode: Test / Demo Fixtures
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
