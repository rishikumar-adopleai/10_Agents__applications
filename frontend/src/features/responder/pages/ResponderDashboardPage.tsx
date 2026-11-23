import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import {
  Calendar,
  Clock,
  Sparkles,
  ShieldAlert,
  Send,
  MessageSquare,
  Mail,
  UserCheck,
  CheckCircle2,
  Video,
  ExternalLink,
  RefreshCw,
  Search,
} from 'lucide-react';
import { apiClient } from '@/lib/apiClient';
import { StandardResponse } from '@/types/api';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { LoadingState } from '@/components/ui/FeedbackStates';

interface DashboardMetrics {
  total_active_conversations: number;
  sentiment_distribution: {
    positive: number;
    negative: number;
    neutral: number;
    automated: number;
    unsubscribe: number;
  };
  meeting_stats: {
    confirmed_meetings: number;
    pending_proposals: number;
    auto_booked_rate: string;
  };
  average_latency_ms: number;
  human_takeovers_active: number;
  provider_health: {
    microsoft_graph: string;
    sms_gateway: string;
    llm_gateway: string;
    organizer_mailbox: string;
  };
}

interface InboundPreview {
  conversation_id: string;
  contact_id: string;
  contact_name: string;
  contact_email: string;
  company_name: string;
  channel: string;
  status: string;
  is_human_takeover: boolean;
  last_message_snippet: string;
  last_message_time: string;
  pending_draft?: string;
  sentiment?: string;
}

export const ResponderDashboardPage: React.FC = () => {
  const navigate = useNavigate();
  const [filterChannel, setFilterChannel] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState<string>('');

  const { data: dashboardData, isLoading, refetch, isFetching } = useQuery<StandardResponse<DashboardMetrics>>({
    queryKey: ['responder-dashboard'],
    queryFn: async () => {
      const res = await apiClient.get<StandardResponse<DashboardMetrics>>('/responder/dashboard');
      return res.data;
    },
    refetchInterval: 15000,
  });

  const { data: inboxData } = useQuery<StandardResponse<InboundPreview[]>>({
    queryKey: ['responder-inbox', filterChannel],
    queryFn: async () => {
      const params = filterChannel !== 'all' ? `?channel=${filterChannel}` : '';
      const res = await apiClient.get<StandardResponse<InboundPreview[]>>(`/responder/inbox${params}`);
      return res.data;
    },
    refetchInterval: 15000,
  });

  const metrics = dashboardData?.data;
  const conversations = inboxData?.data || [];

  const filteredConversations = conversations.filter((c) => {
    if (!searchQuery) return true;
    const q = searchQuery.toLowerCase();
    return (
      c.contact_name?.toLowerCase().includes(q) ||
      c.company_name?.toLowerCase().includes(q) ||
      c.last_message_snippet?.toLowerCase().includes(q)
    );
  });

  if (isLoading && !dashboardData) {
    return <LoadingState message="Loading 24/7 Lead Responder Agent intelligence..." />;
  }

  return (
    <div className="space-y-6 p-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 bg-white p-6 rounded-xl border border-slate-200 shadow-xs">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-xl font-bold text-slate-900">
              Agent 4: 24/7 Lead Responder
            </h1>
            <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800 border border-emerald-200">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 mr-1.5 animate-pulse" />
              Autonomous Active
            </span>
          </div>
          <p className="text-xs text-slate-500 mt-1">
            Real-time multi-channel lead engagement with safety compliance, calendar orchestration & Microsoft Teams automation.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => refetch()}
            disabled={isFetching}
            className="flex items-center gap-1.5 text-xs"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isFetching ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
          <Button
            size="sm"
            onClick={() => navigate('/responder/monitoring')}
            className="bg-indigo-600 hover:bg-indigo-700 text-white flex items-center gap-1.5 text-xs"
          >
            <Sparkles className="w-3.5 h-3.5" />
            Launch 5-Node Simulator
          </Button>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Active Conversations */}
        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
              Active Conversations
            </span>
            <div className="w-8 h-8 rounded-lg bg-indigo-50 flex items-center justify-center text-indigo-600">
              <MessageSquare className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <span className="text-2xl font-bold text-slate-900">
              {metrics?.total_active_conversations ?? 0}
            </span>
            <span className="text-xs text-emerald-600 font-medium">Inbound Pipeline</span>
          </div>
          <div className="mt-3 flex items-center gap-1 text-[11px] text-slate-500">
            <span>Takeover Mode:</span>
            <span className="font-semibold text-amber-600">
              {metrics?.human_takeovers_active ?? 0} Active
            </span>
          </div>
        </div>

        {/* Confirmed Meetings */}
        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
              Confirmed Meetings
            </span>
            <div className="w-8 h-8 rounded-lg bg-emerald-50 flex items-center justify-center text-emerald-600">
              <Calendar className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <span className="text-2xl font-bold text-slate-900">
              {metrics?.meeting_stats?.confirmed_meetings ?? 0}
            </span>
            <span className="text-xs text-slate-500">
              / {metrics?.meeting_stats?.pending_proposals ?? 0} Proposals
            </span>
          </div>
          <div className="mt-3 flex items-center gap-1 text-[11px] text-slate-500">
            <span>Auto-Booked Rate:</span>
            <span className="font-semibold text-emerald-600">
              {metrics?.meeting_stats?.auto_booked_rate ?? '0%'}
            </span>
          </div>
        </div>

        {/* Sentiment Distribution */}
        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
              Sentiment Breakdown
            </span>
            <div className="w-8 h-8 rounded-lg bg-blue-50 flex items-center justify-center text-blue-600">
              <UserCheck className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-3 grid grid-cols-3 gap-1 text-center">
            <div className="bg-emerald-50 py-1 rounded">
              <span className="text-xs font-bold text-emerald-700">
                {metrics?.sentiment_distribution?.positive ?? 0}
              </span>
              <p className="text-[10px] text-emerald-600">Pos</p>
            </div>
            <div className="bg-slate-50 py-1 rounded">
              <span className="text-xs font-bold text-slate-700">
                {metrics?.sentiment_distribution?.neutral ?? 0}
              </span>
              <p className="text-[10px] text-slate-500">Neut</p>
            </div>
            <div className="bg-rose-50 py-1 rounded">
              <span className="text-xs font-bold text-rose-700">
                {metrics?.sentiment_distribution?.negative ?? 0}
              </span>
              <p className="text-[10px] text-rose-600">Neg</p>
            </div>
          </div>
          <div className="mt-2 text-[10px] text-slate-400 text-center">
            {metrics?.sentiment_distribution?.unsubscribe ?? 0} Opt-Outs Suppressed
          </div>
        </div>

        {/* Latency & Safety */}
        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
              Average Latency
            </span>
            <div className="w-8 h-8 rounded-lg bg-violet-50 flex items-center justify-center text-violet-600">
              <Clock className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <span className="text-2xl font-bold text-slate-900">
              {metrics?.average_latency_ms ?? 0}
            </span>
            <span className="text-xs text-slate-500">ms / 5 nodes</span>
          </div>
          <div className="mt-3 flex items-center gap-1.5 text-[11px] text-emerald-600">
            <CheckCircle2 className="w-3.5 h-3.5" />
            <span>Zero hallucinated calendar slots</span>
          </div>
        </div>
      </div>

      {/* Integration Providers Health */}
      <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-xs">
        <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-3">
          Integration Providers & Live Connections
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="p-3 rounded-lg border border-slate-200 bg-slate-50/50 flex items-start gap-3">
            <div className="p-2 rounded bg-indigo-100 text-indigo-700 shrink-0">
              <Calendar className="w-4 h-4" />
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <span className="text-xs font-semibold text-slate-900">Microsoft Graph</span>
                <span className="px-1.5 py-0.2 rounded text-[10px] font-medium bg-emerald-100 text-emerald-800">
                  {metrics?.provider_health?.microsoft_graph || 'Healthy'}
                </span>
              </div>
              <p className="text-[11px] text-slate-500 mt-0.5 truncate">
                Mailbox: {metrics?.provider_health?.organizer_mailbox || 'jeevanandham@adople.ai'}
              </p>
              <p className="text-[10px] text-slate-400 mt-0.5">
                Teams onlineMeetingProvider + getSchedule active
              </p>
            </div>
          </div>

          <div className="p-3 rounded-lg border border-slate-200 bg-slate-50/50 flex items-start gap-3">
            <div className="p-2 rounded bg-emerald-100 text-emerald-700 shrink-0">
              <MessageSquare className="w-4 h-4" />
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <span className="text-xs font-semibold text-slate-900">SMS Gateway</span>
                <span className="px-1.5 py-0.2 rounded text-[10px] font-medium bg-emerald-100 text-emerald-800">
                  {metrics?.provider_health?.sms_gateway || 'Healthy'}
                </span>
              </div>
              <p className="text-[11px] text-slate-500 mt-0.5">
                Direct SMS Dispatch + STOP Suppression
              </p>
              <p className="text-[10px] text-slate-400 mt-0.5">
                TCPA & 10DLC compliance guardrails enabled
              </p>
            </div>
          </div>

          <div className="p-3 rounded-lg border border-slate-200 bg-slate-50/50 flex items-start gap-3">
            <div className="p-2 rounded bg-violet-100 text-violet-700 shrink-0">
              <Sparkles className="w-4 h-4" />
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <span className="text-xs font-semibold text-slate-900">LLM Intent & Safety</span>
                <span className="px-1.5 py-0.2 rounded text-[10px] font-medium bg-emerald-100 text-emerald-800">
                  {metrics?.provider_health?.llm_gateway || 'Healthy'}
                </span>
              </div>
              <p className="text-[11px] text-slate-500 mt-0.5">
                Node 5 Orchestration + Grounded Drafting
              </p>
              <p className="text-[10px] text-slate-400 mt-0.5">
                Integrated with Pipeline 3 Demos & Knowledge Base
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Live Inbound Inquiries Table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
        <div className="p-4 border-b border-slate-200 flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3">
          <div>
            <h2 className="text-sm font-bold text-slate-900">Active Inbound Inquiries</h2>
            <p className="text-xs text-slate-500 mt-0.5">
              Live threads managed by the 24/7 Lead Responder Agent
            </p>
          </div>
          <div className="flex items-center gap-2 w-full sm:w-auto">
            {/* Search */}
            <div className="relative flex-1 sm:w-64">
              <Search className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400" />
              <input
                type="text"
                placeholder="Search leads, companies..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-8 pr-3 py-1.5 text-xs rounded-lg border border-slate-200 focus:outline-none focus:ring-1 focus:ring-indigo-500"
              />
            </div>
            {/* Channel filter */}
            <select
              value={filterChannel}
              onChange={(e) => setFilterChannel(e.target.value)}
              className="text-xs px-2.5 py-1.5 rounded-lg border border-slate-200 bg-white focus:outline-none"
            >
              <option value="all">All Channels</option>
              <option value="sms">SMS Only</option>
              <option value="email">Email Only</option>
            </select>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse text-xs">
            <thead>
              <tr className="bg-slate-50 border-b border-slate-200 text-slate-500 font-semibold">
                <th className="py-2.5 px-4">Channel</th>
                <th className="py-2.5 px-4">Contact & Company</th>
                <th className="py-2.5 px-4">Latest Inbound Message</th>
                <th className="py-2.5 px-4">State</th>
                <th className="py-2.5 px-4">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {filteredConversations.length === 0 ? (
                <tr>
                  <td colSpan={5} className="py-8 text-center text-slate-400">
                    No active conversations found matching criteria.
                  </td>
                </tr>
              ) : (
                filteredConversations.map((c) => (
                  <tr key={c.conversation_id} className="hover:bg-slate-50/70 transition-colors">
                    <td className="py-3 px-4">
                      <div className="flex items-center gap-1.5">
                        {c.channel === 'sms' ? (
                          <span className="p-1 rounded bg-emerald-50 text-emerald-600">
                            <MessageSquare className="w-3.5 h-3.5" />
                          </span>
                        ) : (
                          <span className="p-1 rounded bg-blue-50 text-blue-600">
                            <Mail className="w-3.5 h-3.5" />
                          </span>
                        )}
                        <span className="uppercase text-[10px] font-bold text-slate-600">
                          {c.channel}
                        </span>
                      </div>
                    </td>
                    <td className="py-3 px-4">
                      <div className="font-semibold text-slate-900">{c.contact_name}</div>
                      <div className="text-[11px] text-slate-500">{c.company_name}</div>
                    </td>
                    <td className="py-3 px-4 max-w-md">
                      <p className="text-slate-700 truncate">{c.last_message_snippet}</p>
                      <span className="text-[10px] text-slate-400">{c.last_message_time}</span>
                    </td>
                    <td className="py-3 px-4">
                      {c.is_human_takeover ? (
                        <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-semibold bg-amber-100 text-amber-800">
                          Human Takeover
                        </span>
                      ) : c.status === 'awaiting_approval' ? (
                        <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-semibold bg-indigo-100 text-indigo-800">
                          Draft Pending Approval
                        </span>
                      ) : (
                        <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-semibold bg-emerald-100 text-emerald-800">
                          Active AI
                        </span>
                      )}
                    </td>
                    <td className="py-3 px-4">
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => navigate(`/responder/inbox?conv=${c.conversation_id}`)}
                        className="text-xs flex items-center gap-1"
                      >
                        Open Inbox
                        <ExternalLink className="w-3 h-3" />
                      </Button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
