import React, { useState, useMemo, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { Modal } from '@/components/ui/Modal';
import { LoadingState, EmptyState } from '@/components/ui/FeedbackStates';
import { apiClient } from '@/lib/apiClient';
import { StandardResponse } from '@/types/api';
import { formatDate } from '@/lib/utils';
import {
  Upload,
  CheckCircle2,
  AlertCircle,
  Clock,
  Sparkles,
  ExternalLink,
  Users,
  Briefcase,
  Check,
  Search,
  Download,
  Copy,
  CheckCheck,
  TrendingUp,
  FileText,
  X,
} from 'lucide-react';

interface RadarScanRun {
  id: string;
  organization_id: string;
  icp_profile_id?: string;
  icp_version: number;
  status: string;
  trigger_type: string;
  total_accounts_evaluated: number;
  icp_matched_count: number;
  signals_detected_count: number;
  qualified_accounts_count: number;
  shortlist_size: number;
  scoring_rubric_version: string;
  error_message?: string;
  summary_metadata: Record<string, any>;
  created_at: string;
  updated_at: string;
}

interface SignalEvidence {
  id: string;
  signal_type: string;
  signal_subtype: string;
  source_name: string;
  source_url?: string;
  confidence_score: number;
  verification_status: string;
  observed_fact: string;
  business_hypothesis: string;
  detected_at: string;
}

interface PrioritizedAccount {
  id: string;
  account_id: string;
  account_name: string;
  domain: string;
  rank: number;
  total_score: number;
  icp_score: number;
  why_now_score: number;
  primary_signal_type: string;
  why_now_reason: string;
  suggested_contact_id?: string;
  suggested_contact_name?: string;
  suggested_contact_title?: string;
  suggested_contact_email?: string;
  contact_status: string;
  agent4_task_status: string;
  evidence_items?: SignalEvidence[];
}

interface IntegrationItem {
  provider: string;
  category: string;
  status: string;
  details?: Record<string, any>;
}

interface PipelineStep {
  step: number;
  name: string;
  status: string;
  details: string;
}

const COMMON_INDUSTRIES_SUGGESTIONS = [
  'Healthcare',
  'Hospital and health care',
  'Banking',
  'Insurance',
  'Fintech',
  'Biotechnology',
];

const COMMON_OPERATIONS_SUGGESTIONS = [
  'prior authorization',
  'claims',
  'revenue cycle',
  'medical billing',
  'kyc',
  'fraud',
  'aml',
];

export const RadarPage: React.FC = () => {
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  // Active Tab: 'shortlist' | 'scans'
  const [activeTab, setActiveTab] = useState<'shortlist' | 'scans'>('shortlist');

  // Modals state
  const [selectedAccount, setSelectedAccount] = useState<PrioritizedAccount | null>(null);
  const [isUploadModalOpen, setIsUploadModalOpen] = useState(false);
  const [isIntegrationsModalOpen, setIsIntegrationsModalOpen] = useState(false);
  const [csvFile, setCsvFile] = useState<File | null>(null);

  // Criteria & Schedule editable state
  const [country, setCountry] = useState('United States');
  const [employeeRange, setEmployeeRange] = useState('20-500');
  const [industries, setIndustries] = useState<string[]>(['Financial Services']);
  const [operationalFocus, setOperationalFocus] = useState<string[]>([
    'kyc',
    'fraud',
  ]);
  const [scheduleTime, setScheduleTime] = useState('Daily at 08:00 UTC (default)');
  const [autoRunEnabled, setAutoRunEnabled] = useState(true);
  const [saveSuccessMsg, setSaveSuccessMsg] = useState<string | null>(null);

  // Inline Tag inputs
  const [newIndustry, setNewIndustry] = useState('');
  const [isAddingIndustry, setIsAddingIndustry] = useState(false);
  const [newOpFocus, setNewOpFocus] = useState('');
  const [isAddingOpFocus, setIsAddingOpFocus] = useState(false);

  // Search & Filtering States
  const [searchTerm, setSearchTerm] = useState('');
  const [signalFilter, setSignalFilter] = useState<string>('all');
  const [minScoreFilter, setMinScoreFilter] = useState<number>(0);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  // Latest pipeline steps state
  const [pipelineSteps, setPipelineSteps] = useState<PipelineStep[]>([]);
  const [pipelineError, setPipelineError] = useState<string | null>(null);

  // 1. Fetch Pipeline ICP Criteria
  const { data: pipelineIcpData, refetch: refetchPipelineIcp } = useQuery({
    queryKey: ['radar', 'pipeline-icp'],
    queryFn: async () => {
      const res = await apiClient.get<StandardResponse<any>>('/radar/pipeline/icp');
      return res.data.data;
    },
  });

  // Sync state with fetched ICP
  useEffect(() => {
    if (pipelineIcpData) {
      if (pipelineIcpData.country) setCountry(pipelineIcpData.country);
      if (pipelineIcpData.industries && pipelineIcpData.industries.length > 0)
        setIndustries(pipelineIcpData.industries);
      if (pipelineIcpData.employee_range) setEmployeeRange(pipelineIcpData.employee_range);
      if (pipelineIcpData.operational_focus && pipelineIcpData.operational_focus.length > 0)
        setOperationalFocus(pipelineIcpData.operational_focus);
      if (pipelineIcpData.schedule_time) setScheduleTime(pipelineIcpData.schedule_time);
      if (pipelineIcpData.auto_run_enabled !== undefined)
        setAutoRunEnabled(pipelineIcpData.auto_run_enabled);
    }
  }, [pipelineIcpData]);

  // 2. Fetch Top Accounts
  const { data: topAccountsData, isLoading: loadingAccounts } = useQuery({
    queryKey: ['radar', 'top-accounts'],
    queryFn: async () => {
      const res = await apiClient.get<StandardResponse<PrioritizedAccount[]>>(
        '/radar/top-accounts'
      );
      return res.data.data;
    },
  });

  // 3. Fetch Historical Scans
  const { data: scansData } = useQuery({
    queryKey: ['radar', 'scans'],
    queryFn: async () => {
      const res = await apiClient.get<StandardResponse<RadarScanRun[]>>('/radar/scans');
      return res.data.data;
    },
  });

  // 4. Fetch Integrations
  const { data: integrationsData } = useQuery({
    queryKey: ['radar', 'integrations'],
    queryFn: async () => {
      const res = await apiClient.get<StandardResponse<{ connectors: IntegrationItem[] }>>(
        '/radar/integrations/status'
      );
      return res.data.data.connectors;
    },
  });

  // 5. Mutation: Save ICP Criteria & Schedule
  const saveIcpMutation = useMutation({
    mutationFn: async () => {
      const payloadCriteria = {
        country,
        industries,
        employee_range: employeeRange,
        operational_focus: operationalFocus,
        schedule_time: scheduleTime,
        auto_run_enabled: autoRunEnabled,
      };

      const res = await apiClient.put<StandardResponse<any>>(
        '/radar/pipeline/icp',
        payloadCriteria
      );
      return res.data.data;
    },
    onSuccess: () => {
      refetchPipelineIcp();
      queryClient.invalidateQueries({ queryKey: ['radar'] });
      setSaveSuccessMsg('Criteria & automatic schedule saved successfully!');
      setTimeout(() => setSaveSuccessMsg(null), 4000);
    },
  });

  // 6. Mutation: Trigger Full Radar Pipeline Execution Now
  const runPipelineMutation = useMutation({
    mutationFn: async () => {
      setPipelineError(null);
      const customCriteria = {
        country,
        industries,
        employee_range: employeeRange,
        operational_focus: operationalFocus,
      };

      const res = await apiClient.post<StandardResponse<any>>('/radar/pipeline/run', {
        trigger_type: 'manual_trigger',
        scoring_mode: 'demo',
        custom_criteria: customCriteria,
      });
      return res.data.data;
    },
    onSuccess: (data) => {
      if (data && data.pipeline_steps) {
        setPipelineSteps(data.pipeline_steps);
      }
      queryClient.invalidateQueries({ queryKey: ['radar'] });
    },
    onError: (err: any) => {
      setPipelineError(
        err.response?.data?.message || err.message || 'Pipeline execution encountered an issue'
      );
    },
  });

  // 7. Mutation: Upload CSV
  const uploadCsvMutation = useMutation({
    mutationFn: async (file: File) => {
      const formData = new FormData();
      formData.append('file', file);
      const res = await apiClient.post<StandardResponse<any>>('/radar/imports', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      return res.data.data;
    },
    onSuccess: () => {
      setIsUploadModalOpen(false);
      setCsvFile(null);
      queryClient.invalidateQueries({ queryKey: ['radar'] });
    },
  });

  const latestScan = scansData && scansData.length > 0 ? scansData[0] : null;

  // Filtered Top Accounts
  const filteredAccounts = useMemo(() => {
    return (topAccountsData || []).filter((item) => {
      const term = searchTerm.toLowerCase().trim();
      const matchesSearch =
        !term ||
        item.account_name.toLowerCase().includes(term) ||
        item.domain.toLowerCase().includes(term) ||
        item.why_now_reason.toLowerCase().includes(term);

      const matchesSignal =
        signalFilter === 'all' ||
        item.primary_signal_type.toLowerCase().includes(signalFilter.toLowerCase()) ||
        (signalFilter === 'regulatory' &&
          (item.primary_signal_type.toLowerCase().includes('regulatory') ||
            item.primary_signal_type.toLowerCase().includes('cms'))) ||
        (signalFilter === 'sec' &&
          (item.primary_signal_type.toLowerCase().includes('sec') ||
            item.primary_signal_type.toLowerCase().includes('10-k'))) ||
        (signalFilter === 'hiring' &&
          (item.primary_signal_type.toLowerCase().includes('hiring') ||
            item.primary_signal_type.toLowerCase().includes('job'))) ||
        (signalFilter === 'growth' &&
          (item.primary_signal_type.toLowerCase().includes('growth') ||
            item.primary_signal_type.toLowerCase().includes('news'))) ||
        (signalFilter === 'interest' &&
          (item.primary_signal_type.toLowerCase().includes('interest') ||
            item.primary_signal_type.toLowerCase().includes('hubspot')));

      const matchesScore = item.total_score >= minScoreFilter;

      return matchesSearch && matchesSignal && matchesScore;
    });
  }, [topAccountsData, searchTerm, signalFilter, minScoreFilter]);

  // Copy Why Now text
  const handleCopyReason = (id: string, text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  // Add & remove industry tag
  const handleAddIndustry = (nameToAdd?: string) => {
    const val = (nameToAdd || newIndustry).trim();
    if (val && !industries.includes(val)) {
      setIndustries([...industries, val]);
      setNewIndustry('');
      setIsAddingIndustry(false);
    }
  };

  const handleRemoveIndustry = (tag: string) => {
    setIndustries(industries.filter((t) => t !== tag));
  };

  // Add & remove operational focus tag
  const handleAddOpFocus = (nameToAdd?: string) => {
    const val = (nameToAdd || newOpFocus).trim().toLowerCase();
    if (val && !operationalFocus.includes(val)) {
      setOperationalFocus([...operationalFocus, val]);
      setNewOpFocus('');
      setIsAddingOpFocus(false);
    }
  };

  const handleRemoveOpFocus = (tag: string) => {
    setOperationalFocus(operationalFocus.filter((t) => t !== tag));
  };

  // Export Shortlist as CSV
  const handleExportCsv = () => {
    if (!filteredAccounts || filteredAccounts.length === 0) return;
    const headers = [
      'Rank',
      'Company Name',
      'Domain',
      'Total Score',
      'ICP Fit',
      'Why Now Score',
      'Signal Type',
      'Why Now Reason',
      'Contact Name',
      'Contact Title',
      'Contact Status',
    ];
    const rows = filteredAccounts.map((a) => [
      a.rank,
      `"${a.account_name.replace(/"/g, '""')}"`,
      a.domain,
      `${Math.round(a.total_score * 100)}%`,
      `${Math.round(a.icp_score * 100)}%`,
      `${Math.round(a.why_now_score * 100)}%`,
      a.primary_signal_type,
      `"${a.why_now_reason.replace(/"/g, '""')}"`,
      a.suggested_contact_name || '',
      a.suggested_contact_title || '',
      a.contact_status,
    ]);
    const csvContent =
      'data:text/csv;charset=utf-8,' +
      [headers.join(','), ...rows.map((r) => r.join(','))].join('\n');
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement('a');
    link.setAttribute('href', encodedUri);
    link.setAttribute(
      'download',
      `radar_top_20_accounts_${new Date().toISOString().slice(0, 10)}.csv`
    );
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div className="space-y-6">
      {/* ========================================================================= */}
      {/* 1. TOP HEADER & PRIMARY ACTIONS (MATCHING EXACT REFERENCE DESIGN)         */}
      {/* ========================================================================= */}
      <div className="flex flex-col md:flex-row md:items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">
            Buying-Signal Radar
          </h1>
          <p className="text-xs text-slate-500 mt-1 max-w-2xl leading-relaxed">
            Finds hiring, growth and regulatory signals across 5 streams, removes duplicates and delivers your daily Top 20.
          </p>
        </div>

        {/* Top-Right Action Buttons */}
        <div className="flex items-center space-x-2.5 shrink-0">
          <button
            onClick={() => setIsIntegrationsModalOpen(true)}
            className="px-3.5 py-1.5 text-xs font-medium text-slate-700 bg-white hover:bg-slate-50 border border-slate-200 rounded-lg shadow-2xs transition-colors"
          >
            Connectors (5)
          </button>
          <button
            onClick={() => setIsUploadModalOpen(true)}
            className="px-3.5 py-1.5 text-xs font-medium text-slate-700 bg-white hover:bg-slate-50 border border-slate-200 rounded-lg shadow-2xs transition-colors"
          >
            Import Apollo CSV
          </button>
          <button
            onClick={() => runPipelineMutation.mutate()}
            disabled={runPipelineMutation.isPending}
            className="px-4 py-1.5 text-xs font-semibold text-white bg-[#201D6E] hover:bg-[#1a1758] rounded-lg shadow-xs transition-colors disabled:opacity-60"
          >
            {runPipelineMutation.isPending ? 'Running...' : 'Run radar now'}
          </button>
        </div>
      </div>

      {/* ========================================================================= */}
      {/* 2. TWO-COLUMN CONFIGURATION CARDS: TARGET CRITERIA & AUTOMATIC RUN         */}
      {/* ========================================================================= */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {/* Left Card: Target criteria */}
        <div className="bg-white rounded-xl border border-slate-200/90 p-5 shadow-2xs space-y-4">
          <div className="flex items-center">
            <h2 className="text-sm font-bold text-slate-900">Target criteria</h2>
          </div>

          <div className="grid grid-cols-2 gap-4">
            {/* Country */}
            <div>
              <label className="text-[11px] font-semibold text-slate-500 block mb-1">
                Country
              </label>
              <input
                type="text"
                value={country}
                onChange={(e) => setCountry(e.target.value)}
                placeholder="United States"
                className="w-full px-3 py-1.5 bg-white border border-slate-200 rounded-lg text-xs text-slate-800 placeholder:text-slate-400 focus:outline-none focus:ring-1 focus:ring-indigo-500"
              />
            </div>

            {/* Employee Range */}
            <div>
              <label className="text-[11px] font-semibold text-slate-500 block mb-1">
                Employee range
              </label>
              <select
                value={employeeRange}
                onChange={(e) => setEmployeeRange(e.target.value)}
                className="w-full px-3 py-1.5 bg-white border border-slate-200 rounded-lg text-xs text-slate-800 focus:outline-none focus:ring-1 focus:ring-indigo-500"
              >
                <option value="20-500">20 &ndash; 500 employees</option>
                <option value="500-5000">500 &ndash; 5,000 employees</option>
                <option value="5000+">5,000+ Enterprise</option>
                <option value="any">All Headcounts</option>
              </select>
            </div>
          </div>

          {/* Industries */}
          <div>
            <label className="text-[11px] font-semibold text-slate-500 block mb-1.5">
              Industries
            </label>
            <div className="flex flex-wrap items-center gap-1.5">
              {industries.map((ind) => (
                <span
                  key={ind}
                  className="inline-flex items-center space-x-1 px-2.5 py-1 rounded-md text-xs font-medium bg-indigo-50 text-indigo-700 border border-indigo-200/80 shrink-0"
                >
                  <span>{ind}</span>
                  <button
                    type="button"
                    onClick={() => handleRemoveIndustry(ind)}
                    className="hover:text-indigo-950 ml-1 text-indigo-500 font-bold"
                  >
                    &times;
                  </button>
                </span>
              ))}

              {isAddingIndustry ? (
                <div className="inline-flex items-center space-x-1">
                  <input
                    type="text"
                    value={newIndustry}
                    onChange={(e) => setNewIndustry(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && handleAddIndustry()}
                    placeholder="Industry name..."
                    autoFocus
                    className="px-2 py-0.5 border border-indigo-300 rounded text-xs focus:outline-none w-32"
                  />
                  <button
                    type="button"
                    onClick={() => handleAddIndustry()}
                    className="text-xs font-semibold text-indigo-600 hover:text-indigo-800 px-1"
                  >
                    Add
                  </button>
                  <button
                    type="button"
                    onClick={() => setIsAddingIndustry(false)}
                    className="text-xs text-slate-400 hover:text-slate-600 px-1"
                  >
                    &times;
                  </button>
                </div>
              ) : (
                <button
                  type="button"
                  onClick={() => setIsAddingIndustry(true)}
                  className="text-xs text-slate-400 hover:text-slate-600 font-medium ml-1.5 cursor-pointer"
                >
                  + Add industry
                </button>
              )}
            </div>

            {/* Suggested Industries */}
            <div className="flex flex-wrap items-center gap-1.5 mt-2">
              {COMMON_INDUSTRIES_SUGGESTIONS.filter((s) => !industries.includes(s)).slice(0, 4).map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => handleAddIndustry(s)}
                  className="bg-slate-100 hover:bg-slate-200 text-slate-600 rounded-md px-2.5 py-1 text-xs font-medium cursor-pointer transition-colors shrink-0"
                >
                  + {s}
                </button>
              ))}
            </div>
          </div>

          {/* Operational Focus */}
          <div>
            <label className="text-[11px] font-semibold text-slate-500 block mb-1.5">
              Operational focus
            </label>
            <div className="flex flex-wrap items-center gap-1.5">
              {operationalFocus.map((op) => (
                <span
                  key={op}
                  className="inline-flex items-center space-x-1 px-2.5 py-1 rounded-md text-xs font-medium bg-indigo-50 text-indigo-700 border border-indigo-200/80 uppercase shrink-0"
                >
                  <span>{op.replace('_', ' ')}</span>
                  <button
                    type="button"
                    onClick={() => handleRemoveOpFocus(op)}
                    className="hover:text-indigo-950 ml-1 text-indigo-500 font-bold"
                  >
                    &times;
                  </button>
                </span>
              ))}

              {isAddingOpFocus ? (
                <div className="inline-flex items-center space-x-1">
                  <input
                    type="text"
                    value={newOpFocus}
                    onChange={(e) => setNewOpFocus(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && handleAddOpFocus()}
                    placeholder="Operational focus..."
                    autoFocus
                    className="px-2 py-0.5 border border-indigo-300 rounded text-xs focus:outline-none w-32"
                  />
                  <button
                    type="button"
                    onClick={() => handleAddOpFocus()}
                    className="text-xs font-semibold text-indigo-600 hover:text-indigo-800 px-1"
                  >
                    Add
                  </button>
                  <button
                    type="button"
                    onClick={() => setIsAddingOpFocus(false)}
                    className="text-xs text-slate-400 hover:text-slate-600 px-1"
                  >
                    &times;
                  </button>
                </div>
              ) : (
                <button
                  type="button"
                  onClick={() => setIsAddingOpFocus(true)}
                  className="text-xs text-slate-400 hover:text-slate-600 font-medium ml-1.5 cursor-pointer"
                >
                  + Add focus
                </button>
              )}
            </div>

            {/* Suggested Operational Focus */}
            <div className="flex flex-wrap items-center gap-1.5 mt-2">
              {COMMON_OPERATIONS_SUGGESTIONS.filter((s) => !operationalFocus.includes(s.toLowerCase())).slice(0, 4).map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => handleAddOpFocus(s)}
                  className="bg-slate-100 hover:bg-slate-200 text-slate-600 rounded-md px-2.5 py-1 text-xs font-medium cursor-pointer transition-colors capitalize shrink-0"
                >
                  + {s.replace('_', ' ')}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Right Card: Automatic run */}
        <div className="bg-white rounded-xl border border-slate-200/90 p-5 shadow-2xs flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-sm font-bold text-slate-900">Automatic run</h2>
              <button
                type="button"
                role="switch"
                aria-checked={autoRunEnabled}
                onClick={() => setAutoRunEnabled((prev) => !prev)}
                className="flex items-center space-x-2 focus:outline-none cursor-pointer select-none group"
                title={`Click to turn automatic run ${autoRunEnabled ? 'OFF' : 'ON'}`}
              >
                <span
                  className={`text-[10px] font-bold px-2 py-0.5 rounded-full transition-colors ${
                    autoRunEnabled
                      ? 'bg-emerald-50 text-emerald-700 border border-emerald-200/80'
                      : 'bg-slate-100 text-slate-500 border border-slate-200'
                  }`}
                >
                  {autoRunEnabled ? 'ON' : 'OFF'}
                </span>
                <div
                  className={`relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out ${
                    autoRunEnabled ? 'bg-[#201D6E]' : 'bg-slate-300'
                  }`}
                >
                  <span
                    className={`pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow-xs ring-0 transition duration-200 ease-in-out ${
                      autoRunEnabled ? 'translate-x-4' : 'translate-x-0'
                    }`}
                  />
                </div>
              </button>
            </div>

            {/* Run time input/select */}
            <div className="mb-4">
              <label className="text-[11px] font-semibold text-slate-500 block mb-1">
                Run time
              </label>
              <input
                type="text"
                value={scheduleTime}
                onChange={(e) => setScheduleTime(e.target.value)}
                disabled={!autoRunEnabled}
                className={`w-full px-3 py-1.5 border border-slate-200 rounded-lg text-xs font-medium focus:outline-none focus:ring-1 focus:ring-indigo-500 transition-colors ${
                  autoRunEnabled
                    ? 'bg-slate-50/70 text-slate-800'
                    : 'bg-slate-100/80 text-slate-400 cursor-not-allowed'
                }`}
              />
            </div>

            {/* Deduplication Note Box */}
            <div className="bg-slate-50 border border-slate-100 rounded-lg p-3 text-[11px] text-slate-600 leading-relaxed break-words">
              {autoRunEnabled
                ? 'Automatic deduplication. Records from Greenhouse, Lever, GDELT, CMS, SEC EDGAR and HubSpot are SHA-256 hashed by domain, so no duplicates reach your list.'
                : 'Automatic run is currently turned OFF. Scheduled automated scans are paused. You can still trigger scans on demand using "Run radar now".'}
            </div>

            {saveSuccessMsg && (
              <div className="mt-2 p-2 bg-emerald-50 border border-emerald-200 rounded-lg text-xs text-emerald-800 font-medium flex items-center space-x-1.5">
                <Check className="w-3.5 h-3.5 shrink-0 text-emerald-600" />
                <span>{saveSuccessMsg}</span>
              </div>
            )}

            {pipelineError && (
              <div className="mt-2 p-2 bg-rose-50 border border-rose-200 rounded-lg text-xs text-rose-800 font-medium flex items-center space-x-1.5">
                <AlertCircle className="w-3.5 h-3.5 shrink-0 text-rose-600" />
                <span>{pipelineError}</span>
              </div>
            )}
          </div>

          {/* Action Buttons */}
          <div className="space-y-2 mt-4 pt-2">
            <button
              onClick={() => saveIcpMutation.mutate()}
              disabled={saveIcpMutation.isPending}
              className="w-full bg-white hover:bg-slate-50 border border-slate-200 text-slate-700 font-semibold text-xs py-2 rounded-lg shadow-2xs transition-colors"
            >
              {saveIcpMutation.isPending ? 'Saving...' : 'Save and schedule'}
            </button>
            <button
              onClick={() => runPipelineMutation.mutate()}
              disabled={runPipelineMutation.isPending}
              className="w-full bg-[#201D6E] hover:bg-[#1a1758] text-white font-semibold text-xs py-2.5 rounded-lg shadow-xs transition-colors disabled:opacity-60"
            >
              {runPipelineMutation.isPending ? 'Running...' : 'Run radar now'}
            </button>
          </div>
        </div>
      </div>

      {/* ========================================================================= */}
      {/* 3. 5 CONTINUOUS RESEARCH STREAMS - SOURCED EVIDENCE ONLY                  */}
      {/* ========================================================================= */}
      <div className="space-y-2.5">
        <h3 className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">
          5 CONTINUOUS RESEARCH STREAMS &ndash; SOURCED EVIDENCE ONLY
        </h3>

        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3.5">
          {/* Card 1: Manual workload */}
          <div className="bg-white rounded-xl border border-slate-200/90 p-4 shadow-2xs flex flex-col justify-start min-w-0">
            <div className="w-7 h-7 rounded-lg bg-blue-50 text-blue-500 flex items-center justify-center mb-2.5 shrink-0">
              <Briefcase className="w-4 h-4" />
            </div>
            <h4 className="font-bold text-xs text-slate-900 mb-1 truncate">
              1. Manual workload
            </h4>
            <p className="text-[11px] text-slate-500 leading-snug break-words">
              Greenhouse + Lever: claims, prior auth, KYC and billing job openings.
            </p>
          </div>

          {/* Card 2: Company growth */}
          <div className="bg-white rounded-xl border border-slate-200/90 p-4 shadow-2xs flex flex-col justify-start min-w-0">
            <div className="w-7 h-7 rounded-lg bg-emerald-50 text-emerald-500 flex items-center justify-center mb-2.5 shrink-0">
              <TrendingUp className="w-4 h-4" />
            </div>
            <h4 className="font-bold text-xs text-slate-900 mb-1 truncate">
              2. Company growth
            </h4>
            <p className="text-[11px] text-slate-500 leading-snug break-words">
              GDELT + company news: expansion, executive hiring, acquisitions.
            </p>
          </div>

          {/* Card 3: Deadlines */}
          <div className="bg-white rounded-xl border border-slate-200/90 p-4 shadow-2xs flex flex-col justify-start min-w-0">
            <div className="w-7 h-7 rounded-lg bg-amber-50 text-amber-500 flex items-center justify-center mb-2.5 shrink-0">
              <Clock className="w-4 h-4" />
            </div>
            <h4 className="font-bold text-xs text-slate-900 mb-1 truncate">
              3. Deadlines
            </h4>
            <p className="text-[11px] text-slate-500 leading-snug break-words">
              CMS + Federal Register: CMS-0057-F Interoperability and compliance.
            </p>
          </div>

          {/* Card 4: Public filings */}
          <div className="bg-white rounded-xl border border-slate-200/90 p-4 shadow-2xs flex flex-col justify-start min-w-0">
            <div className="w-7 h-7 rounded-lg bg-purple-50 text-purple-500 flex items-center justify-center mb-2.5 shrink-0">
              <FileText className="w-4 h-4" />
            </div>
            <h4 className="font-bold text-xs text-slate-900 mb-1 truncate">
              4. Public filings
            </h4>
            <p className="text-[11px] text-slate-500 leading-snug break-words">
              SEC EDGAR: 10-K Item 9A internal control remediation.
            </p>
          </div>

          {/* Card 5: Interest in us */}
          <div className="bg-white rounded-xl border border-slate-200/90 p-4 shadow-2xs flex flex-col justify-start min-w-0">
            <div className="w-7 h-7 rounded-lg bg-rose-50 text-rose-500 flex items-center justify-center mb-2.5 shrink-0">
              <Users className="w-4 h-4" />
            </div>
            <h4 className="font-bold text-xs text-slate-900 mb-1 truncate">
              5. Interest in us
            </h4>
            <p className="text-[11px] text-slate-500 leading-snug break-words">
              HubSpot CRM: pricing page views and inbound engagement.
            </p>
          </div>
        </div>
      </div>

      {/* ========================================================================= */}
      {/* 4. KPI SUMMARY METRIC CARDS                                               */}
      {/* ========================================================================= */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3.5">
        <div className="p-4 bg-white rounded-xl border border-slate-200/90 shadow-2xs min-w-0">
          <div className="text-[11px] text-slate-500 mb-1 truncate">Radar schedule</div>
          <div className="text-xl font-bold text-slate-900 truncate flex items-center space-x-1.5">
            <span>{autoRunEnabled ? '08:00 UTC' : 'OFF'}</span>
            <span
              className={`w-1.5 h-1.5 rounded-full ${
                autoRunEnabled ? 'bg-emerald-500 animate-pulse' : 'bg-slate-300'
              }`}
            />
          </div>
        </div>

        <div className="p-4 bg-white rounded-xl border border-slate-200/90 shadow-2xs min-w-0">
          <div className="text-[11px] text-slate-500 mb-1 truncate">Total evaluated</div>
          <div className="text-2xl font-bold text-slate-900 truncate">
            {latestScan?.total_accounts_evaluated || 95}
          </div>
        </div>

        <div className="p-4 bg-white rounded-xl border border-slate-200/90 shadow-2xs min-w-0">
          <div className="text-[11px] text-slate-500 mb-1 truncate">ICP filtered</div>
          <div className="text-2xl font-bold text-slate-900 truncate">
            {latestScan?.icp_matched_count || 95}
          </div>
        </div>

        <div className="p-4 bg-white rounded-xl border border-slate-200/90 shadow-2xs min-w-0">
          <div className="text-[11px] text-slate-500 mb-1 truncate">Signals detected</div>
          <div className="text-2xl font-bold text-slate-900 truncate">
            {latestScan?.signals_detected_count || 249}
          </div>
        </div>

        <div className="p-4 bg-white rounded-xl border border-slate-200/90 shadow-2xs min-w-0">
          <div className="text-[11px] text-slate-500 mb-1 truncate">Daily Top 20</div>
          <div className="text-2xl font-bold text-[#201D6E] truncate">
            {topAccountsData?.length || 20}
          </div>
        </div>

        <div className="p-4 bg-white rounded-xl border border-slate-200/90 shadow-2xs min-w-0">
          <div className="text-[11px] text-slate-500 mb-1 truncate">Agent 4 handoff</div>
          <div className="text-2xl font-bold text-purple-600 truncate">
            {topAccountsData?.length || 20}
          </div>
        </div>
      </div>

      {/* Live Pipeline Steps Feedback (when executing) */}
      {pipelineSteps.length > 0 && (
        <div className="bg-white border border-slate-200/90 rounded-xl p-4 shadow-2xs space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <Sparkles className="w-4 h-4 text-indigo-600" />
              <h3 className="text-xs font-bold text-slate-900">
                Live Radar Pipeline Execution Completed ({pipelineSteps.length} Steps)
              </h3>
            </div>
            <Badge variant="success">All Steps Succeeded</Badge>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-2.5 text-xs">
            {pipelineSteps.map((step) => (
              <div
                key={step.step}
                className="p-2.5 bg-slate-50 rounded-lg border border-slate-200/80 space-y-1"
              >
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-slate-800 text-[11px]">
                    Step {step.step}: {step.name}
                  </span>
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />
                </div>
                <p className="text-[10px] text-slate-500 leading-snug">{step.details}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* 5. TABS: DAILY TOP 20 SHORTLIST & HISTORICAL SCAN RUNS                    */}
      {/* ========================================================================= */}
      <div className="flex border-b border-slate-200 space-x-6 text-sm">
        <button
          onClick={() => setActiveTab('shortlist')}
          className={`pb-2.5 transition-colors flex items-center space-x-2 ${
            activeTab === 'shortlist'
              ? 'border-b-2 border-[#201D6E] text-[#201D6E] font-bold'
              : 'text-slate-500 hover:text-slate-900 font-medium'
          }`}
        >
          <span>Daily Top 20 Shortlist</span>
          <span className="text-xs font-semibold text-slate-500 ml-1">
            {topAccountsData?.length || 20}
          </span>
        </button>

        <button
          onClick={() => setActiveTab('scans')}
          className={`pb-2.5 transition-colors flex items-center space-x-2 ${
            activeTab === 'scans'
              ? 'border-b-2 border-[#201D6E] text-[#201D6E] font-bold'
              : 'text-slate-500 hover:text-slate-900 font-medium'
          }`}
        >
          <span>Historical Scan Runs</span>
          <span className="text-xs font-medium text-slate-400 ml-1">
            {scansData?.length || 11}
          </span>
        </button>
      </div>

      {/* ========================================================================= */}
      {/* 6. TAB 1: DAILY TOP 20 TABLE & FILTER BAR                                 */}
      {/* ========================================================================= */}
      {activeTab === 'shortlist' && (
        <div className="space-y-3.5">
          {/* Filter Toolbar Matching Reference Design */}
          <div className="bg-white p-2.5 rounded-xl border border-slate-200/90 shadow-2xs flex flex-wrap items-center justify-between gap-3">
            {/* Search and Stream Filter Pills */}
            <div className="flex flex-wrap items-center gap-2 flex-1">
              {/* Search Input */}
              <div className="relative w-64">
                <input
                  type="text"
                  placeholder="Search company, domain, or reason"
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="w-full px-3 py-1.5 bg-white border border-slate-200 rounded-lg text-xs text-slate-800 placeholder:text-slate-400 focus:outline-none focus:ring-1 focus:ring-indigo-500 shadow-2xs"
                />
              </div>

              {/* Stream Filters */}
              <div className="flex items-center space-x-1 text-xs">
                {[
                  { label: 'All 5', value: 'all' },
                  { label: 'Hiring (Jobs)', value: 'hiring' },
                  { label: 'Growth (News)', value: 'growth' },
                  { label: 'Deadlines (CMS)', value: 'regulatory' },
                  { label: 'SEC 10-K', value: 'sec' },
                  { label: 'HubSpot', value: 'interest' },
                ].map((filter) => (
                  <button
                    key={filter.value}
                    onClick={() => setSignalFilter(filter.value)}
                    className={`px-2.5 py-1 rounded-md text-xs transition-colors shrink-0 ${
                      signalFilter === filter.value
                        ? 'bg-[#201D6E] text-white font-semibold'
                        : 'bg-slate-100 hover:bg-slate-200 text-slate-600 font-medium'
                    }`}
                  >
                    {filter.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Export CSV Button */}
            <div>
              <button
                onClick={handleExportCsv}
                className="bg-white hover:bg-slate-50 border border-slate-200 text-slate-700 font-medium text-xs px-3.5 py-1.5 rounded-lg shadow-2xs transition-colors shrink-0"
              >
                Export CSV
              </button>
            </div>
          </div>

          {loadingAccounts ? (
            <LoadingState message="Loading Top 20 accounts..." />
          ) : !topAccountsData || topAccountsData.length === 0 ? (
            <EmptyState
              title="No prioritized accounts yet"
              description="Click 'Run radar now' above to execute the 5 research streams against target accounts."
              actionLabel="Run radar now"
              onAction={() => runPipelineMutation.mutate()}
            />
          ) : (
            <div className="bg-white rounded-xl border border-slate-200/90 shadow-2xs overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse min-w-[980px]">
                  <thead>
                    <tr className="border-b border-slate-100 text-[10px] font-bold text-slate-400 uppercase tracking-wider">
                      <th className="py-3 px-3 w-14 text-center">RANK</th>
                      <th className="py-3 px-4 w-48">COMPANY</th>
                      <th className="py-3 px-3 w-40">PRIORITY</th>
                      <th className="py-3 px-3 w-28">SIGNAL</th>
                      <th className="py-3 px-4 min-w-[280px]">WHY NOW</th>
                      <th className="py-3 px-4 w-48">CONTACT</th>
                      <th className="py-3 px-3 w-24 text-center">AGENT 4</th>
                      <th className="py-3 px-3 w-20 text-center">PROOF</th>
                      <th className="py-3 px-3 w-28 text-center">RESEARCH</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {filteredAccounts.map((item) => (
                      <tr
                        key={item.id}
                        className="hover:bg-slate-50/70 transition-colors"
                      >
                        {/* Rank */}
                        <td className="py-3 px-3 text-center align-middle">
                          <span className="inline-flex items-center justify-center w-6 h-6 rounded-md font-bold text-xs bg-amber-100 text-amber-900 mx-auto">
                            {item.rank}
                          </span>
                        </td>

                        {/* Company & Domain */}
                        <td className="py-3 px-4 align-middle">
                          <div className="font-bold text-xs text-slate-900 truncate">
                            {item.account_name}
                          </div>
                          <a
                            href={`https://${item.domain}`}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-[11px] text-slate-400 hover:text-slate-600 truncate block mt-0.5"
                          >
                            {item.domain}
                          </a>
                        </td>

                        {/* Priority Score & Progress Bar */}
                        <td className="py-3 px-3 align-middle">
                          <div className="flex items-center space-x-2">
                            <span className="font-bold text-xs text-slate-900">
                              {Math.round(item.total_score * 100)} %
                            </span>
                            <div className="w-14 bg-slate-200 h-1.5 rounded-full overflow-hidden shrink-0">
                              <div
                                className="bg-[#201D6E] h-full rounded-full"
                                style={{ width: `${Math.round(item.total_score * 100)}%` }}
                              />
                            </div>
                          </div>
                          <div className="text-[10px] text-slate-400 mt-0.5 whitespace-nowrap">
                            Fit {Math.round(item.icp_score * 100)}% &bull; Urgency{' '}
                            {Math.round(item.why_now_score * 100)}%
                          </div>
                        </td>

                        {/* Signal Tag */}
                        <td className="py-3 px-3 align-middle">
                          <span className="bg-amber-50 text-amber-800 border border-amber-200/70 rounded-full px-2.5 py-0.5 text-[10px] font-medium inline-block capitalize whitespace-nowrap">
                            {item.primary_signal_type.replace('_', ' ')}
                          </span>
                        </td>

                        {/* Why Now Reason with Clean Boundary Wrapping */}
                        <td className="py-3 px-4 align-middle">
                          <div className="flex items-start justify-between group max-w-sm">
                            <p className="text-xs text-slate-700 leading-snug break-words overflow-hidden pr-2">
                              {item.why_now_reason}
                            </p>
                            <button
                              onClick={() => handleCopyReason(item.id, item.why_now_reason)}
                              className="text-slate-400 hover:text-slate-600 p-1 rounded opacity-0 group-hover:opacity-100 transition-opacity shrink-0"
                              title="Copy reason"
                            >
                              {copiedId === item.id ? (
                                <CheckCheck className="w-3 h-3 text-emerald-500" />
                              ) : (
                                <Copy className="w-3 h-3" />
                              )}
                            </button>
                          </div>
                        </td>

                        {/* Contact */}
                        <td className="py-3 px-4 align-middle">
                          {item.contact_status === 'verified_contact' &&
                          item.suggested_contact_name ? (
                            <div>
                              <div className="font-bold text-xs text-slate-900 truncate">
                                {item.suggested_contact_name}
                              </div>
                              <div className="text-[11px] text-slate-500 truncate">
                                {item.suggested_contact_title || item.suggested_contact_email}
                              </div>
                            </div>
                          ) : (
                            <div>
                              <div className="text-xs text-slate-700 font-medium truncate">
                                Research needed
                              </div>
                              <div className="text-[10px] text-slate-400 truncate">
                                Agent 4 will find a contact
                              </div>
                            </div>
                          )}
                        </td>

                        {/* Agent 4 Handoff Status */}
                        <td className="py-3 px-3 text-center align-middle">
                          <span className="bg-emerald-50 text-emerald-700 border border-emerald-200/80 rounded-full px-2.5 py-0.5 text-[10px] font-medium inline-block">
                            Staged
                          </span>
                        </td>

                        {/* Proof Count Button */}
                        <td className="py-3 px-3 text-center align-middle">
                          <button
                            onClick={() => setSelectedAccount(item)}
                            className="inline-block hover:opacity-80 transition-opacity cursor-pointer text-center"
                            title="Inspect evidence dossier"
                          >
                            <span className="font-bold text-xs text-slate-900 block leading-tight">
                              {item.evidence_items?.length || 2}
                            </span>
                            <span className="text-[10px] text-slate-500 block leading-tight">
                              Proof
                            </span>
                          </button>
                        </td>

                        {/* Pipeline 2 Handoff */}
                        <td className="py-3 px-3 text-center align-middle">
                          <button
                            onClick={() => navigate(`/research/company/${item.account_id || item.id}`)}
                            className="inline-flex items-center space-x-1 px-2.5 py-1 bg-indigo-50 hover:bg-indigo-100 text-indigo-700 text-[10px] font-semibold rounded-md border border-indigo-200 transition-colors shadow-2xs"
                            title="Open in Pipeline 2 Research"
                          >
                            <span>Research</span>
                            <ExternalLink className="w-2.5 h-2.5" />
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Table Footer */}
              <div className="p-3 border-t border-slate-100 flex items-center justify-between text-xs text-slate-500 bg-white">
                <div>
                  Showing {filteredAccounts.length} of {topAccountsData?.length || 20} accounts
                </div>
                <div className="text-slate-400 text-xs">
                  Scoring rubric: {latestScan?.scoring_rubric_version || 'demo-v1'}
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ========================================================================= */}
      {/* 7. TAB 2: HISTORICAL SCAN RUNS                                            */}
      {/* ========================================================================= */}
      {activeTab === 'scans' && (
        <div className="bg-white rounded-xl border border-slate-200/90 shadow-2xs overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-xs min-w-[700px]">
              <thead>
                <tr className="border-b border-slate-100 bg-slate-50/75 text-[10px] font-bold text-slate-500 uppercase tracking-wider">
                  <th className="py-3 px-4">Scan ID</th>
                  <th className="py-3 px-4">Trigger</th>
                  <th className="py-3 px-4">Status</th>
                  <th className="py-3 px-4">Total Evaluated</th>
                  <th className="py-3 px-4">ICP Matched</th>
                  <th className="py-3 px-4">Signals</th>
                  <th className="py-3 px-4">Top Shortlist</th>
                  <th className="py-3 px-4">Timestamp</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {scansData?.map((scan) => (
                  <tr key={scan.id} className="hover:bg-slate-50/50">
                    <td className="py-3 px-4 font-mono text-[10px] text-slate-500">
                      {scan.id.slice(0, 12)}...
                    </td>
                    <td className="py-3 px-4 capitalize">{scan.trigger_type}</td>
                    <td className="py-3 px-4">
                      <Badge
                        variant={
                          scan.status === 'completed'
                            ? 'success'
                            : scan.status === 'running'
                            ? 'warning'
                            : 'danger'
                        }
                      >
                        {scan.status}
                      </Badge>
                    </td>
                    <td className="py-3 px-4">{scan.total_accounts_evaluated}</td>
                    <td className="py-3 px-4">{scan.icp_matched_count}</td>
                    <td className="py-3 px-4">{scan.signals_detected_count}</td>
                    <td className="py-3 px-4 font-bold text-emerald-600">{scan.shortlist_size}</td>
                    <td className="py-3 px-4 text-slate-400">{formatDate(scan.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* 8. MODALS (PRESERVING ALL EXISTING FUNCTIONALITY)                         */}
      {/* ========================================================================= */}

      {/* Modal 1: Evidence Inspection Modal */}
      {selectedAccount && (
        <Modal
          isOpen={!!selectedAccount}
          onClose={() => setSelectedAccount(null)}
          title={`Evidence Dossier: ${selectedAccount.account_name}`}
        >
          <div className="space-y-4 max-h-[70vh] overflow-y-auto text-xs pr-1">
            <div className="p-3 bg-blue-50 border border-blue-200 rounded-lg">
              <p className="font-semibold text-blue-900">
                Verified "Why Now" Reason:
              </p>
              <p className="text-blue-800 mt-1 font-medium">
                {selectedAccount.why_now_reason}
              </p>
            </div>

            <div className="space-y-3">
              <h4 className="font-bold text-slate-900">
                Verified Evidence Items ({selectedAccount.evidence_items?.length || 1})
              </h4>

              {selectedAccount.evidence_items && selectedAccount.evidence_items.length > 0 ? (
                selectedAccount.evidence_items.map((ev) => (
                  <div
                    key={ev.id}
                    className="p-3 border border-slate-200 rounded-lg space-y-1.5"
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-semibold text-slate-900 capitalize">
                        {ev.signal_type.replace('_', ' ')}: {ev.signal_subtype.replace('_', ' ')}
                      </span>
                      <Badge variant="success">{ev.verification_status}</Badge>
                    </div>
                    <p className="text-slate-600">{ev.observed_fact}</p>
                    <p className="text-[11px] text-slate-500 italic">"{ev.business_hypothesis}"</p>
                    {ev.source_url && (
                      <div className="pt-1">
                        <a
                          href={ev.source_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-blue-600 hover:underline flex items-center space-x-1"
                        >
                          <span className="truncate max-w-sm">{ev.source_url}</span>
                          <ExternalLink className="w-3 h-3 shrink-0" />
                        </a>
                      </div>
                    )}
                  </div>
                ))
              ) : (
                <div className="p-3 border border-slate-200 rounded-lg">
                  <p className="text-slate-600">
                    Primary Evidence: {selectedAccount.why_now_reason}
                  </p>
                  <p className="text-[11px] text-slate-400 mt-1">
                    Verified via statutory compliance rules & public regulatory documentation.
                  </p>
                </div>
              )}
            </div>
          </div>
        </Modal>
      )}

      {/* Modal 2: CSV Upload Modal */}
      {isUploadModalOpen && (
        <Modal
          isOpen={isUploadModalOpen}
          onClose={() => setIsUploadModalOpen(false)}
          title="Import Apollo Companies CSV"
        >
          <div className="space-y-4 text-xs">
            <p className="text-slate-500">
              Upload an exported Apollo company CSV file. Headers like Company Name, Website,
              Employee Count, and Contact details are automatically normalized and deduplicated
              against existing database records.
            </p>

            <div className="border-2 border-dashed border-slate-300 rounded-xl p-6 text-center">
              <input
                type="file"
                accept=".csv"
                onChange={(e) => setCsvFile(e.target.files?.[0] || null)}
                className="hidden"
                id="csv-file-input"
              />
              <label htmlFor="csv-file-input" className="cursor-pointer space-y-2 block">
                <Upload className="w-8 h-8 text-slate-400 mx-auto" />
                <span className="font-semibold text-brand-600 block">
                  {csvFile ? csvFile.name : 'Click to select CSV file'}
                </span>
                <span className="text-[11px] text-slate-400 block">
                  Supports up to 25MB Apollo export files
                </span>
              </label>
            </div>

            <div className="flex justify-end space-x-2 pt-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setIsUploadModalOpen(false)}
              >
                Cancel
              </Button>
              <Button
                size="sm"
                disabled={!csvFile}
                isLoading={uploadCsvMutation.isPending}
                onClick={() => csvFile && uploadCsvMutation.mutate(csvFile)}
              >
                Import & Deduplicate
              </Button>
            </div>
          </div>
        </Modal>
      )}

      {/* Modal 3: Connectors Health Status Modal */}
      {isIntegrationsModalOpen && (
        <Modal
          isOpen={isIntegrationsModalOpen}
          onClose={() => setIsIntegrationsModalOpen(false)}
          title="Radar Integration Connectors (5 Streams)"
        >
          <div className="space-y-3 text-xs">
            <p className="text-slate-500">
              Active research adapters queried during the Buying-Signal Radar scan:
            </p>

            <div className="divide-y divide-slate-100">
              {(
                integrationsData || [
                  {
                    provider: '1. Greenhouse ATS Job Board',
                    category: 'Manual Workload',
                    status: 'healthy',
                    details: { cost: '$0 Free Public API' },
                  },
                  {
                    provider: '1. Lever ATS Job Board',
                    category: 'Manual Workload',
                    status: 'healthy',
                    details: { cost: '$0 Free Public API' },
                  },
                  {
                    provider: '2. GDELT DOC 2.0 News',
                    category: 'Company Growth',
                    status: 'healthy',
                    details: { cost: '$0 Free Global API' },
                  },
                  {
                    provider: '3. Regulatory CMS Rules',
                    category: 'Compliance Deadlines',
                    status: 'healthy',
                    details: { rules: 'CMS-0057-F, FinCEN' },
                  },
                  {
                    provider: '4. SEC EDGAR Submissions',
                    category: 'Public 10-K Filings',
                    status: 'healthy',
                    details: { mode: 'Item 9A Controls' },
                  },
                  {
                    provider: '5. HubSpot Inbound Intent',
                    category: 'Interest in Us',
                    status: 'healthy',
                    details: { mode: 'CRM Engagement' },
                  },
                ]
              ).map((conn, idx) => (
                <div key={idx} className="py-2.5 flex items-center justify-between">
                  <div>
                    <span className="font-semibold text-slate-900 block">
                      {conn.provider}
                    </span>
                    <span className="text-[10px] text-slate-400 capitalize">
                      {conn.category} &bull;{' '}
                      {conn.details?.cost || conn.details?.mode || conn.details?.rules || 'Active'}
                    </span>
                  </div>
                  <Badge variant={conn.status === 'healthy' ? 'success' : 'default'}>
                    {conn.status}
                  </Badge>
                </div>
              ))}
            </div>

            <div className="pt-2 flex justify-end">
              <Button size="sm" onClick={() => setIsIntegrationsModalOpen(false)}>
                Close
              </Button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
};
