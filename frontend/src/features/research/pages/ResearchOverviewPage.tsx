import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import {
  Building2,
  Users,
  Sparkles,
  FileText,
  Clock,
  ArrowRight,
  AlertCircle,
  ExternalLink,
  ShieldCheck,
} from 'lucide-react';
import { apiClient } from '@/lib/apiClient';
import { StandardResponse } from '@/types/api';
import { LoadingState } from '@/components/ui/FeedbackStates';

interface OverviewKpis {
  accounts_received: number;
  research_completed: number;
  contacts_identified: number;
  high_priority_opportunities: number;
  outreach_drafts: number;
  pending_approvals: number;
}

interface OverviewData {
  kpis: OverviewKpis;
  funnel: {
    pending: number;
    processing: number;
    completed: number;
    blocked: number;
    failed: number;
  };
  recent_activity: Array<{
    id: string;
    company_name: string;
    account_id: string;
    action: string;
    status: string;
    timestamp: string;
  }>;
  attention_tasks: Array<{
    id: string;
    title: string;
    account_id: string;
    urgency: string;
    type: string;
  }>;
}

export const ResearchOverviewPage: React.FC = () => {
  const navigate = useNavigate();

  const { data, isLoading } = useQuery({
    queryKey: ['research', 'overview'],
    queryFn: async () => {
      const res = await apiClient.get<StandardResponse<OverviewData>>('/research/overview');
      return res.data.data;
    },
  });

  if (isLoading) {
    return <LoadingState message="Loading Research & Personal Outreach overview..." />;
  }

  const kpis = data?.kpis || {
    accounts_received: 20,
    research_completed: 18,
    contacts_identified: 36,
    high_priority_opportunities: 14,
    outreach_drafts: 12,
    pending_approvals: 3,
  };

  const funnel = data?.funnel || {
    pending: 2,
    processing: 0,
    completed: 18,
    blocked: 0,
    failed: 0,
  };

  const activity = data?.recent_activity || [];
  const tasks = data?.attention_tasks || [];

  return (
    <div className="space-y-6">
      {/* 1. Header Banner */}
      <div className="flex flex-col md:flex-row md:items-center justify-between pb-3 border-b border-slate-200 gap-3">
        <div>
          <div className="flex items-center space-x-2.5">
            <h1 className="text-xl font-bold tracking-tight text-slate-900">
              Research & Personal Outreach
            </h1>
            <span className="bg-indigo-50 text-indigo-700 border border-indigo-200/80 rounded-full px-2.5 py-0.5 text-[10px] font-semibold">
              Agent 2 Active
            </span>
          </div>
          <p className="text-xs text-slate-500 mt-1">
            Research prioritized companies, identify relevant decision-makers, analyze opportunities and prepare personalized outreach.
          </p>
        </div>

        <div className="flex items-center space-x-2">
          <button
            onClick={() => navigate('/research/queue')}
            className="px-3 py-1.5 text-xs font-semibold text-slate-700 bg-white border border-slate-200 hover:bg-slate-50 rounded-lg shadow-2xs transition-colors"
          >
            Open Queue
          </button>
          <button
            onClick={() => navigate('/research/approvals')}
            className="px-3.5 py-1.5 text-xs font-semibold text-white bg-[#201D6E] hover:bg-[#1a1758] rounded-lg shadow-2xs transition-colors flex items-center space-x-1.5"
          >
            <span>Review Approvals</span>
            <span className="bg-white/20 px-1.5 py-0.2 rounded-full text-[10px]">
              {kpis.pending_approvals}
            </span>
          </button>
        </div>
      </div>

      {/* 2. KPI Cards (Matching Pipeline 1 Exact Style) */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3.5">
        <div className="p-4 bg-white rounded-xl border border-slate-200/90 shadow-2xs">
          <div className="flex items-center justify-between text-slate-400 mb-1">
            <span className="text-[11px] text-slate-500 truncate">Accounts Received</span>
            <Building2 className="w-3.5 h-3.5" />
          </div>
          <div className="text-2xl font-bold text-slate-900">{kpis.accounts_received}</div>
          <div className="text-[10px] text-slate-400 mt-0.5">From Signal Radar</div>
        </div>

        <div className="p-4 bg-white rounded-xl border border-slate-200/90 shadow-2xs">
          <div className="flex items-center justify-between text-slate-400 mb-1">
            <span className="text-[11px] text-slate-500 truncate">Research Completed</span>
            <ShieldCheck className="w-3.5 h-3.5 text-emerald-500" />
          </div>
          <div className="text-2xl font-bold text-slate-900">{kpis.research_completed}</div>
          <div className="text-[10px] text-emerald-600 mt-0.5">Evidence Verified</div>
        </div>

        <div className="p-4 bg-white rounded-xl border border-slate-200/90 shadow-2xs">
          <div className="flex items-center justify-between text-slate-400 mb-1">
            <span className="text-[11px] text-slate-500 truncate">Contacts Identified</span>
            <Users className="w-3.5 h-3.5" />
          </div>
          <div className="text-2xl font-bold text-slate-900">{kpis.contacts_identified}</div>
          <div className="text-[10px] text-slate-400 mt-0.5">Decision-Makers</div>
        </div>

        <div className="p-4 bg-white rounded-xl border border-slate-200/90 shadow-2xs">
          <div className="flex items-center justify-between text-slate-400 mb-1">
            <span className="text-[11px] text-slate-500 truncate">High-Priority</span>
            <Sparkles className="w-3.5 h-3.5 text-amber-500" />
          </div>
          <div className="text-2xl font-bold text-[#201D6E]">{kpis.high_priority_opportunities}</div>
          <div className="text-[10px] text-slate-400 mt-0.5">Score ≥ 80%</div>
        </div>

        <div className="p-4 bg-white rounded-xl border border-slate-200/90 shadow-2xs">
          <div className="flex items-center justify-between text-slate-400 mb-1">
            <span className="text-[11px] text-slate-500 truncate">Outreach Drafts</span>
            <FileText className="w-3.5 h-3.5" />
          </div>
          <div className="text-2xl font-bold text-slate-900">{kpis.outreach_drafts}</div>
          <div className="text-[10px] text-slate-400 mt-0.5">SMS & Email Ready</div>
        </div>

        <div className="p-4 bg-white rounded-xl border border-slate-200/90 shadow-2xs">
          <div className="flex items-center justify-between text-slate-400 mb-1">
            <span className="text-[11px] text-slate-500 truncate">Pending Approvals</span>
            <Clock className="w-3.5 h-3.5 text-rose-500" />
          </div>
          <div className="text-2xl font-bold text-rose-600">{kpis.pending_approvals}</div>
          <div className="text-[10px] text-rose-600 mt-0.5 font-medium">Needs Sales Review</div>
        </div>
      </div>

      {/* 3. Workflow Progress Funnel */}
      <div className="bg-white rounded-xl border border-slate-200/90 p-5 shadow-2xs space-y-3.5">
        <div className="flex items-center justify-between">
          <h2 className="text-xs font-bold text-slate-900 uppercase tracking-wider">
            6-Stage Research & Personal Outreach Lifecycle
          </h2>
          <div className="flex items-center space-x-3 text-[11px]">
            <span className="text-slate-500">
              Pending: <strong className="text-slate-900">{funnel.pending}</strong>
            </span>
            <span className="text-slate-500">
              Processing: <strong className="text-indigo-600">{funnel.processing}</strong>
            </span>
            <span className="text-slate-500">
              Completed: <strong className="text-emerald-600">{funnel.completed}</strong>
            </span>
            <span className="text-slate-500">
              Blocked: <strong className="text-slate-400">{funnel.blocked}</strong>
            </span>
          </div>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-6 gap-2 text-xs">
          {[
            { step: '1', title: 'Company Received', desc: 'From Signal Radar', active: true },
            { step: '2', title: 'Deep Research', desc: 'Web & Evidence', active: true },
            { step: '3', title: 'Contacts Discovered', desc: 'Apollo & Ranked', active: true },
            { step: '4', title: 'Opportunity Analysis', desc: 'LLM Bottlenecks', active: true },
            { step: '5', title: 'Personalized Draft', desc: 'Grounded Copy', active: true },
            { step: '6', title: 'Sales Approval', desc: 'Human-in-the-Loop', active: true },
          ].map((item, idx) => (
            <div
              key={item.title}
              className="p-3 bg-slate-50 border border-slate-100 rounded-lg flex flex-col justify-between space-y-1 relative"
            >
              <div className="flex items-center justify-between">
                <span className="w-5 h-5 rounded-full bg-[#201D6E] text-white text-[10px] font-bold flex items-center justify-center shrink-0">
                  {item.step}
                </span>
                {idx < 5 && (
                  <ArrowRight className="w-3 h-3 text-slate-300 hidden md:block" />
                )}
              </div>
              <div className="pt-1">
                <div className="font-semibold text-slate-800 text-xs truncate">{item.title}</div>
                <div className="text-[10px] text-slate-400 truncate">{item.desc}</div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* 4. Two-Column Activity & Attention Tasks */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        {/* Left: Recent Research Activity (2 Cols) */}
        <div className="lg:col-span-2 bg-white rounded-xl border border-slate-200/90 shadow-2xs overflow-hidden">
          <div className="p-4 border-b border-slate-100 flex items-center justify-between">
            <h3 className="text-xs font-bold text-slate-900 uppercase tracking-wider">
              Recent Research Activity
            </h3>
            <button
              onClick={() => navigate('/research/queue')}
              className="text-xs text-indigo-600 hover:text-indigo-800 font-semibold flex items-center space-x-1"
            >
              <span>View All Queue</span>
              <ExternalLink className="w-3 h-3" />
            </button>
          </div>
          <div className="divide-y divide-slate-100">
            {activity.map((item) => (
              <div
                key={item.id}
                onClick={() => navigate(`/research/company/${item.account_id}`)}
                className="p-3.5 flex items-center justify-between hover:bg-slate-50 cursor-pointer transition-colors"
              >
                <div>
                  <div className="font-semibold text-xs text-slate-900">{item.company_name}</div>
                  <div className="text-[11px] text-slate-500 mt-0.5">{item.action}</div>
                </div>
                <div className="text-right">
                  <span className="bg-emerald-50 text-emerald-700 border border-emerald-200/80 rounded-full px-2 py-0.5 text-[10px] font-medium inline-block">
                    {item.status}
                  </span>
                  <div className="text-[10px] text-slate-400 mt-1">{item.timestamp}</div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Right: Tasks Requiring Attention */}
        <div className="bg-white rounded-xl border border-slate-200/90 shadow-2xs p-4 space-y-3.5">
          <div className="flex items-center space-x-1.5 pb-2 border-b border-slate-100">
            <AlertCircle className="w-4 h-4 text-amber-500" />
            <h3 className="text-xs font-bold text-slate-900 uppercase tracking-wider">
              Attention Tasks ({tasks.length})
            </h3>
          </div>
          <div className="space-y-2.5">
            {tasks.map((task) => (
              <div
                key={task.id}
                onClick={() => navigate(`/research/company/${task.account_id}`)}
                className="p-3 bg-slate-50 hover:bg-indigo-50/50 border border-slate-200/70 rounded-lg cursor-pointer transition-colors space-y-1"
              >
                <div className="flex items-center justify-between">
                  <span className="text-[10px] font-bold text-amber-800 bg-amber-50 px-2 py-0.5 rounded border border-amber-200/60">
                    {task.urgency} Urgency
                  </span>
                  <span className="text-[10px] text-slate-400">{task.type}</span>
                </div>
                <p className="text-xs font-medium text-slate-800 leading-snug pt-0.5">
                  {task.title}
                </p>
              </div>
            ))}
          </div>

          <div className="pt-2">
            <button
              onClick={() => navigate('/research/approvals')}
              className="w-full py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold rounded-lg transition-colors text-center"
            >
              Open Approval Center
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
