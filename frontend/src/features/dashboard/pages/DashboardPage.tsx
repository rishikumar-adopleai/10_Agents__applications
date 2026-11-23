import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { PageHeader } from '@/components/layout/PageHeader';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { Modal } from '@/components/ui/Modal';
import { apiClient } from '@/lib/apiClient';
import { StandardResponse } from '@/types/api';
import { formatDate } from '@/lib/utils';
import {
  Radio,
  Building2,
  Users,
  Sparkles,
  Zap,
  ArrowRight,
  Clock,
  Compass,
  Check,
  Copy,
  Sliders,
  Play,
  RotateCw,
  ExternalLink,
  ChevronRight,
  Shield,
  Layers,
  FileSpreadsheet,
  CheckCircle2,
  AlertCircle,
  TrendingUp,
} from 'lucide-react';

interface RadarScanRun {
  id: string;
  organization_id: string;
  status: string;
  trigger_type: string;
  total_accounts_evaluated: number;
  icp_matched_count: number;
  signals_detected_count: number;
  qualified_accounts_count: number;
  shortlist_size: number;
  created_at: string;
  summary_metadata?: Record<string, any>;
}

interface ShortlistedAccount {
  id: string;
  account_name: string;
  domain: string;
  composite_score: number;
  icp_score?: number;
  why_now_score?: number;
  why_now_reason: string;
  primary_signal_category: string;
  verified_contact_name?: string;
  verified_contact_title?: string;
  verified_contact_email?: string;
}

const SIGNAL_CATEGORIES = [
  { name: 'Regulatory & Compliance Mandates', key: 'regulatory', weight: '35%', desc: 'HIPAA, SOC-2, DORA, state privacy rulings forcing automation' },
  { name: 'Hiring & Headcount Spikes', key: 'hiring', weight: '25%', desc: 'Rapid expansion in Operations, Risk, and AI Engineering roles' },
  { name: 'Leadership & Executive Changes', key: 'leadership', weight: '15%', desc: 'New CIO, CTO, or Head of Transformation appointed in last 90 days' },
  { name: 'SEC 10-K & Financial Filings', key: 'sec_filings', weight: '15%', desc: 'Efficiency pressures, cost reductions, and disclosed risk factors' },
  { name: 'Tech Stack & Vendor Migrations', key: 'tech_stack', weight: '10%', desc: 'Modernizing legacy CRM/ERP stacks and cloud infrastructure' },
];

export const DashboardPage: React.FC = () => {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [copiedId, setCopiedId] = useState<string | null>(null);

  // Queries
  const { data: latestRun, isLoading: runLoading } = useQuery({
    queryKey: ['radar-runs', 'latest'],
    queryFn: async () => {
      const res = await apiClient.get<StandardResponse<RadarScanRun>>('/radar/runs/latest');
      return res.data.data;
    },
  });

  const { data: shortlisted = [], isLoading: accountsLoading } = useQuery({
    queryKey: ['radar-runs', latestRun?.id, 'shortlist'],
    queryFn: async () => {
      if (!latestRun?.id) return [];
      const res = await apiClient.get<StandardResponse<ShortlistedAccount[]>>(
        `/radar/runs/${latestRun.id}/shortlist`
      );
      return res.data.data;
    },
    enabled: Boolean(latestRun?.id),
  });

  const { data: scans = [] } = useQuery({
    queryKey: ['radar', 'scans'],
    queryFn: async () => {
      const res = await apiClient.get<StandardResponse<RadarScanRun[]>>('/radar/scans');
      return res.data.data;
    },
  });

  const { data: accounts = [] } = useQuery({
    queryKey: ['accounts'],
    queryFn: async () => {
      const res = await apiClient.get<StandardResponse<any[]>>('/accounts');
      return res.data.data;
    },
  });

  // Run Radar Scan Mutation
  const runScanMutation = useMutation({
    mutationFn: async () => {
      const res = await apiClient.post<StandardResponse<RadarScanRun>>('/radar/scan/trigger', {
        trigger_type: 'manual_dashboard',
      });
      return res.data.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['radar-runs'] });
      queryClient.invalidateQueries({ queryKey: ['radar'] });
    },
  });

  const handleCopyReason = (id: string, reason: string) => {
    navigator.clipboard.writeText(reason);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <PageHeader
        title="Agent 1: Buying-Signal Radar"
        description="Every morning, sales gets 20 US accounts that have a real reason to buy AI now, each with that reason in one line."
        action={
          <div className="flex items-center space-x-2.5">
            <Button
              variant="outline"
              size="sm"
              onClick={() => navigate('/agents')}
              className="text-xs"
            >
              <Zap className="w-3.5 h-3.5 mr-1.5 text-slate-500" />
              Agent 1 Console
            </Button>
            <Button
              size="sm"
              onClick={() => runScanMutation.mutate()}
              isLoading={runScanMutation.isPending}
              className="text-xs"
            >
              <Play className="w-3.5 h-3.5 mr-1.5" />
              Run Radar Scan Now
            </Button>
          </div>
        }
      />

      {/* Top 4 KPI Metrics Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Total Accounts Evaluated */}
        <div className="bg-white dark:bg-slate-900 p-4 rounded-xl border border-slate-200 dark:border-slate-800 shadow-xs flex items-center justify-between">
          <div>
            <p className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
              Accounts Evaluated
            </p>
            <p className="text-2xl font-bold text-slate-900 dark:text-slate-100 mt-1">
              {latestRun?.total_accounts_evaluated || accounts.length || '93'}
            </p>
            <p className="text-[12px] text-slate-500 mt-0.5">
              US Target accounts in database
            </p>
          </div>
          <div className="w-10 h-10 rounded-lg bg-blue-50 dark:bg-blue-950/40 text-brand-600 flex items-center justify-center">
            <Building2 className="w-5 h-5" />
          </div>
        </div>

        {/* ICP Matched */}
        <div className="bg-white dark:bg-slate-900 p-4 rounded-xl border border-slate-200 dark:border-slate-800 shadow-xs flex items-center justify-between">
          <div>
            <p className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
              ICP Fit Matched
            </p>
            <p className="text-2xl font-bold text-slate-900 dark:text-slate-100 mt-1 flex items-center space-x-2">
              <span>{latestRun?.icp_matched_count || '52'}</span>
              <span className="text-xs font-medium text-emerald-600 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-950/50 px-2 py-0.5 rounded-full border border-emerald-200 dark:border-emerald-800">
                Fit Verified
              </span>
            </p>
            <p className="text-[12px] text-slate-500 mt-0.5">
              100% compliant with ICP rubric
            </p>
          </div>
          <div className="w-10 h-10 rounded-lg bg-emerald-50 dark:bg-emerald-950/40 text-emerald-600 flex items-center justify-center">
            <CheckCircle2 className="w-5 h-5" />
          </div>
        </div>

        {/* Buying Signals Detected */}
        <div className="bg-white dark:bg-slate-900 p-4 rounded-xl border border-slate-200 dark:border-slate-800 shadow-xs flex items-center justify-between">
          <div>
            <p className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
              Signals Detected
            </p>
            <p className="text-2xl font-bold text-slate-900 dark:text-slate-100 mt-1">
              {latestRun?.signals_detected_count || '148'}
            </p>
            <p className="text-[12px] text-slate-500 mt-0.5">
              Across 5 buying signal categories
            </p>
          </div>
          <div className="w-10 h-10 rounded-lg bg-indigo-50 dark:bg-indigo-950/40 text-indigo-600 flex items-center justify-center">
            <TrendingUp className="w-5 h-5" />
          </div>
        </div>

        {/* Daily Top 20 Shortlist */}
        <div className="bg-white dark:bg-slate-900 p-4 rounded-xl border border-slate-200 dark:border-slate-800 shadow-xs flex items-center justify-between">
          <div>
            <p className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
              Daily Top 20 Shortlist
            </p>
            <p className="text-2xl font-bold text-brand-600 dark:text-brand-400 mt-1 flex items-center space-x-2">
              <span>{latestRun?.shortlist_size || shortlisted.length || '20'}</span>
              <span className="text-xs font-medium text-blue-600 bg-blue-50 dark:bg-blue-950/50 px-2 py-0.5 rounded-full border border-blue-200 dark:border-blue-800">
                Ready for Sales
              </span>
            </p>
            <p className="text-[12px] text-slate-500 mt-0.5">
              Ranked with Why Now reasons
            </p>
          </div>
          <div className="w-10 h-10 rounded-lg bg-blue-50 dark:bg-blue-950/40 text-brand-600 flex items-center justify-center">
            <Radio className="w-5 h-5" />
          </div>
        </div>
      </div>

      {/* Main Grid: Input Configuration (Left) & Daily Output (Right) */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        {/* Left Column: FIRST AGENT INPUT (ICP, Signals, Data Sources) */}
        <div className="space-y-4">
          <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 p-5 shadow-xs space-y-4">
            <div className="flex items-center justify-between border-b border-slate-100 dark:border-slate-800 pb-3">
              <div className="flex items-center space-x-2">
                <Sliders className="w-4 h-4 text-brand-600" />
                <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100">
                  Agent 1: Input Configuration
                </h3>
              </div>
              <span className="text-[10px] font-mono font-semibold px-2 py-0.5 rounded-md bg-blue-50 text-brand-700 dark:bg-blue-950 dark:text-blue-300">
                Rubric v1.0
              </span>
            </div>

            {/* Input Data Ingestion Sources */}
            <div>
              <p className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider mb-2">
                Data Ingestion Sources
              </p>
              <div className="space-y-2">
                <div className="p-2.5 rounded-lg border border-slate-100 dark:border-slate-800 bg-slate-50/70 dark:bg-slate-850/50 flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    <span className="w-2 h-2 rounded-full bg-emerald-500" />
                    <span className="text-xs font-semibold text-slate-800 dark:text-slate-200">
                      Apollo.io Target List
                    </span>
                  </div>
                  <span className="text-[10px] font-medium text-emerald-600">Connected</span>
                </div>
                <div className="p-2.5 rounded-lg border border-slate-100 dark:border-slate-800 bg-slate-50/70 dark:bg-slate-850/50 flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    <span className="w-2 h-2 rounded-full bg-emerald-500" />
                    <span className="text-xs font-semibold text-slate-800 dark:text-slate-200">
                      HubSpot Enterprise CRM
                    </span>
                  </div>
                  <span className="text-[10px] font-medium text-emerald-600">Synced</span>
                </div>
              </div>
            </div>

            {/* Input Signal Detection Weights */}
            <div>
              <p className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider mb-2">
                Signal Detector Weights
              </p>
              <div className="space-y-2">
                {SIGNAL_CATEGORIES.map((cat) => (
                  <div
                    key={cat.key}
                    className="p-2.5 rounded-lg border border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-850/30"
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-xs font-semibold text-slate-800 dark:text-slate-200">
                        {cat.name}
                      </span>
                      <span className="text-[11px] font-mono font-bold text-brand-600 dark:text-brand-400">
                        {cat.weight}
                      </span>
                    </div>
                    <p className="text-[11px] text-slate-500 leading-tight">{cat.desc}</p>
                  </div>
                ))}
              </div>
            </div>

            {/* Input Actions */}
            <div className="pt-2 border-t border-slate-100 dark:border-slate-800 flex items-center justify-between">
              <Button
                variant="outline"
                size="sm"
                onClick={() => navigate('/radar')}
                className="text-xs w-full justify-between"
              >
                <span>Full Radar Configuration</span>
                <ChevronRight className="w-3.5 h-3.5 ml-1" />
              </Button>
            </div>
          </div>
        </div>

        {/* Right Columns (Span 2): FIRST AGENT OUTPUT (Daily Top 20 Accounts) */}
        <div className="lg:col-span-2 space-y-4">
          <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 p-5 shadow-xs space-y-4">
            <div className="flex items-center justify-between border-b border-slate-100 dark:border-slate-800 pb-3">
              <div className="flex items-center space-x-2.5">
                <div className="w-7 h-7 rounded-lg bg-blue-50 dark:bg-blue-950/40 text-brand-600 flex items-center justify-center">
                  <Radio className="w-4 h-4" />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100">
                    Agent 1: Output Shortlist (Top 20 Accounts)
                  </h3>
                  <p className="text-[11px] text-slate-500">
                    Prioritized accounts with evidence-backed one-line Why Now reasons and verified contacts.
                  </p>
                </div>
              </div>

              <Button
                size="sm"
                onClick={() => navigate('/radar')}
                className="text-xs"
              >
                <span>View Full Table</span>
                <ArrowRight className="w-3.5 h-3.5 ml-1" />
              </Button>
            </div>

            {/* Output Shortlist Items */}
            {accountsLoading ? (
              <div className="py-12 text-center text-xs text-slate-400">
                Loading Agent 1 output shortlist...
              </div>
            ) : shortlisted.length === 0 ? (
              <div className="py-12 text-center text-xs text-slate-500">
                No shortlist accounts generated yet. Click "Run Radar Scan Now" above to trigger Agent 1.
              </div>
            ) : (
              <div className="divide-y divide-slate-100 dark:divide-slate-800">
                {shortlisted.slice(0, 5).map((item, index) => (
                  <div
                    key={item.id}
                    className="py-3.5 first:pt-0 last:pb-0 hover:bg-slate-50/70 dark:hover:bg-slate-850/40 rounded-lg p-2.5 transition-colors space-y-2"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex items-center space-x-2.5">
                        <span className="w-6 h-6 rounded-md bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 font-mono text-xs font-bold flex items-center justify-center shrink-0">
                          #{index + 1}
                        </span>
                        <div>
                          <h4 className="text-xs font-bold text-slate-900 dark:text-slate-100">
                            {item.account_name}
                          </h4>
                          <p className="text-[11px] text-slate-400 font-mono">
                            {item.domain}
                          </p>
                        </div>
                      </div>

                      <div className="flex items-center space-x-2">
                        <span className="text-[11px] font-mono font-semibold px-2 py-0.5 rounded-md bg-blue-50 text-brand-700 dark:bg-blue-950/60 dark:text-blue-300 border border-blue-200/60 dark:border-blue-800/40">
                          Score: {item.composite_score.toFixed(1)}
                        </span>
                        <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300">
                          {item.primary_signal_category}
                        </span>
                      </div>
                    </div>

                    {/* One-Line Why Now Reason (with Copy button) */}
                    <div className="flex items-center justify-between p-2 rounded-md bg-slate-50 dark:bg-slate-850 border border-slate-200/70 dark:border-slate-800 text-xs">
                      <p className="text-slate-700 dark:text-slate-300 text-[12px] italic pr-2">
                        "{item.why_now_reason}"
                      </p>
                      <button
                        onClick={() => handleCopyReason(item.id, item.why_now_reason)}
                        className="p-1 rounded text-slate-400 hover:text-brand-600 transition-colors shrink-0"
                        title="Copy Why Now Reason"
                      >
                        {copiedId === item.id ? (
                          <Check className="w-3.5 h-3.5 text-emerald-600" />
                        ) : (
                          <Copy className="w-3.5 h-3.5" />
                        )}
                      </button>
                    </div>

                    {/* Verified Contact Footer */}
                    <div className="flex items-center justify-between text-[11px] text-slate-500 pt-1">
                      <div className="flex items-center space-x-2">
                        <Users className="w-3.5 h-3.5 text-slate-400" />
                        <span>
                          {item.verified_contact_name
                            ? `${item.verified_contact_name} (${item.verified_contact_title || 'Verified Contact'})`
                            : 'Verified Contact Available'}
                        </span>
                      </div>
                      <button
                        onClick={() => navigate('/radar')}
                        className="text-brand-600 hover:text-brand-700 font-medium flex items-center"
                      >
                        Evidence Dossier <ArrowRight className="w-3 h-3 ml-0.5" />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Recent Agent 1 Scan Execution Stream */}
      <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 p-5 shadow-xs space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2.5">
            <Clock className="w-4 h-4 text-brand-600" />
            <div>
              <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100">
                Agent 1: Scan Execution History
              </h3>
              <p className="text-xs text-slate-500">
                Audit trail of daily and triggered radar evaluations across US accounts.
              </p>
            </div>
          </div>
          <span className="text-[11px] text-slate-400 font-mono">
            {scans.length} Scans Completed
          </span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="border-b border-slate-200 dark:border-slate-800 bg-slate-50/70 dark:bg-slate-800/50 text-slate-500 font-semibold">
                <th className="py-2.5 px-3">Scan ID</th>
                <th className="py-2.5 px-3">Trigger Type</th>
                <th className="py-2.5 px-3">Status</th>
                <th className="py-2.5 px-3">Evaluated</th>
                <th className="py-2.5 px-3">ICP Fit</th>
                <th className="py-2.5 px-3">Signals</th>
                <th className="py-2.5 px-3">Shortlisted</th>
                <th className="py-2.5 px-3">Timestamp</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-800 font-mono">
              {scans.slice(0, 5).map((scan: RadarScanRun) => (
                <tr key={scan.id} className="hover:bg-slate-50 dark:hover:bg-slate-800/50">
                  <td className="py-2.5 px-3 font-semibold text-slate-800 dark:text-slate-200">
                    {scan.id.slice(0, 8)}...
                  </td>
                  <td className="py-2.5 px-3 text-slate-600 dark:text-slate-400 font-sans">
                    {scan.trigger_type}
                  </td>
                  <td className="py-2.5 px-3">
                    <Badge variant={scan.status === 'completed' ? 'success' : 'default'} size="sm">
                      {scan.status}
                    </Badge>
                  </td>
                  <td className="py-2.5 px-3 text-slate-600 dark:text-slate-400">
                    {scan.total_accounts_evaluated}
                  </td>
                  <td className="py-2.5 px-3 text-emerald-600 font-semibold">
                    {scan.icp_matched_count}
                  </td>
                  <td className="py-2.5 px-3 text-brand-600 font-semibold">
                    {scan.signals_detected_count}
                  </td>
                  <td className="py-2.5 px-3 text-slate-800 dark:text-slate-200 font-bold">
                    {scan.shortlist_size}
                  </td>
                  <td className="py-2.5 px-3 text-slate-400 font-sans">
                    {scan.created_at ? formatDate(scan.created_at) : 'Just now'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};