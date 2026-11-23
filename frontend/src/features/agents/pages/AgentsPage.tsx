import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { PageHeader } from '@/components/layout/PageHeader';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { apiClient } from '@/lib/apiClient';
import { StandardResponse } from '@/types/api';
import { formatDate } from '@/lib/utils';
import {
  Radio,
  Play,
  RotateCw,
  Clock,
  Sparkles,
  Shield,
  FileText,
  Search,
  Users,
  Compass,
  ArrowRight,
  ExternalLink,
  Check,
  Copy,
  Building2,
  ShieldCheck,
  TrendingUp,
  Activity,
  Zap,
  Sliders,
  CheckCircle2,
  AlertCircle,
  Code2,
} from 'lucide-react';

const DEFAULT_RADAR_PARAMS = {
  country: "United States",
  industries: [
    "Healthcare",
    "Financial Services"
  ],
  employee_range: "any",
  operational_focus: [
    "fraud",
    "kyc",
    "prior_authorization",
    "claims"
  ],
  account_name: 'Acme Health Systems',
  domain: 'acmehealth.com',
  min_confidence: 0.8,
  signal_categories: [
    'manual_workload_hiring',
    'company_growth_news',
    'regulatory_deadlines_cms',
    'sec_edgar_10k_filings',
    'hubspot_inbound_intent',
  ],
};

export const AgentsPage: React.FC = () => {
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  // Form States for Agent 1 Input
  const [accountName, setAccountName] = useState('Acme Health Systems');
  const [domain, setDomain] = useState('acmehealth.com');
  const [minConfidence, setMinConfidence] = useState(0.8);
  const [jsonInput, setJsonInput] = useState<string>(
    JSON.stringify(DEFAULT_RADAR_PARAMS, null, 2)
  );
  const [inputMode, setInputMode] = useState<'form' | 'json'>('form');

  // Output States for Agent 1
  const [executionResult, setExecutionResult] = useState<any | null>(null);
  const [isExecuting, setIsExecuting] = useState(false);
  const [copiedResult, setCopiedResult] = useState(false);
  const [copiedReason, setCopiedReason] = useState(false);

  // Fetch recent tasks filtered for buying_signal_radar
  const { data: recentTasks = [], isLoading: tasksLoading } = useQuery({
    queryKey: ['agent-tasks', 'buying_signal_radar'],
    queryFn: async () => {
      const res = await apiClient.get<StandardResponse<any[]>>('/agent-tasks');
      // Filter strictly for Agent 1 tasks
      return (res.data.data || []).filter(
        (task) => task.agent_id === 'buying_signal_radar'
      );
    },
    refetchInterval: 5000,
  });

  // Execute Agent 1
  const handleExecute = async () => {
    setIsExecuting(true);
    setExecutionResult(null);

    try {
      let parameters: Record<string, any> = {};

      if (inputMode === 'json') {
        try {
          parameters = JSON.parse(jsonInput);
        } catch {
          parameters = { raw: jsonInput };
        }
      } else {
        parameters = {
          account_name: accountName,
          domain: domain,
          min_confidence: minConfidence,
          signal_categories: [
            'regulatory_changes',
            'hiring_spikes',
            'executive_changes',
            'sec_10k_filings',
            'tech_stack_migrations',
          ],
        };
      }

      const payload = {
        agent_id: 'buying_signal_radar',
        organization_id: 'org-default',
        correlation_id: `radar-exec-${Date.now()}`,
        parameters,
      };

      const res = await apiClient.post<StandardResponse<any>>('/agent-tasks/execute', payload);
      setExecutionResult(res.data.data);
      queryClient.invalidateQueries({ queryKey: ['agent-tasks'] });
      queryClient.invalidateQueries({ queryKey: ['radar'] });
    } catch (err: any) {
      setExecutionResult({
        error: err.response?.data?.message || err.message || 'Execution error occurred',
        status: 'terminal_failure',
      });
    } finally {
      setIsExecuting(false);
    }
  };

  const handleCopyResult = () => {
    if (!executionResult) return;
    navigator.clipboard.writeText(JSON.stringify(executionResult, null, 2));
    setCopiedResult(true);
    setTimeout(() => setCopiedResult(false), 2000);
  };

  const handleResetDefaults = () => {
    setAccountName('Acme Health Systems');
    setDomain('acmehealth.com');
    setMinConfidence(0.8);
    setJsonInput(JSON.stringify(DEFAULT_RADAR_PARAMS, null, 2));
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <PageHeader
        title="Agent 1: Buying-Signal Radar Console"
        description="Direct execution interface — Configure input criteria, trigger intent evaluation, and inspect live structured outputs."
        action={
          <div className="flex items-center space-x-2.5">
            <Button
              variant="outline"
              size="sm"
              onClick={() => navigate('/radar')}
              className="text-xs"
            >
              <Radio className="w-3.5 h-3.5 mr-1.5 text-brand-600" />
              Daily Top 20 Shortlist
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => navigate('/dashboard')}
              className="text-xs"
            >
              <Compass className="w-3.5 h-3.5 mr-1.5 text-slate-500" />
              Radar Dashboard
            </Button>
          </div>
        }
      />

      {/* Operational Highlights */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="bg-white dark:bg-slate-900 p-4 rounded-xl border border-slate-200 dark:border-slate-800 shadow-xs flex items-center justify-between">
          <div>
            <p className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
              Agent Sequence
            </p>
            <p className="text-xl font-bold text-slate-900 dark:text-slate-100 mt-0.5">
              Agent 01
            </p>
            <p className="text-[11px] text-brand-600 font-medium mt-0.5">
              Buying-Signal Radar
            </p>
          </div>
          <div className="w-9 h-9 rounded-lg bg-blue-50 dark:bg-blue-950/40 text-brand-600 flex items-center justify-center">
            <Radio className="w-4 h-4" />
          </div>
        </div>

        <div className="bg-white dark:bg-slate-900 p-4 rounded-xl border border-slate-200 dark:border-slate-800 shadow-xs flex items-center justify-between">
          <div>
            <p className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
              Operational Status
            </p>
            <p className="text-xl font-bold text-emerald-600 dark:text-emerald-400 mt-0.5 flex items-center space-x-1.5">
              <span className="w-2.5 h-2.5 rounded-full bg-emerald-500" />
              <span>Online & Ready</span>
            </p>
            <p className="text-[11px] text-slate-500 mt-0.5">
              Deterministic scoring bounds active
            </p>
          </div>
          <div className="w-9 h-9 rounded-lg bg-emerald-50 dark:bg-emerald-950/40 text-emerald-600 flex items-center justify-center">
            <Activity className="w-4 h-4" />
          </div>
        </div>

        <div className="bg-white dark:bg-slate-900 p-4 rounded-xl border border-slate-200 dark:border-slate-800 shadow-xs flex items-center justify-between">
          <div>
            <p className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
              Core Deliverable
            </p>
            <p className="text-xl font-bold text-slate-900 dark:text-slate-100 mt-0.5">
              Daily Top 20
            </p>
            <p className="text-[11px] text-slate-500 mt-0.5">
              US accounts with Why Now reasons
            </p>
          </div>
          <div className="w-9 h-9 rounded-lg bg-indigo-50 dark:bg-indigo-950/40 text-indigo-600 flex items-center justify-center">
            <Sparkles className="w-4 h-4" />
          </div>
        </div>
      </div>

      {/* Main Execution Split: INPUT (Left) and OUTPUT (Right) */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {/* FIRST AGENT INPUT PANEL */}
        <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 p-5 shadow-xs space-y-4">
          <div className="flex items-center justify-between border-b border-slate-100 dark:border-slate-800 pb-3">
            <div className="flex items-center space-x-2">
              <Sliders className="w-4 h-4 text-brand-600" />
              <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100">
                Agent 1: Input Parameters
              </h3>
            </div>

            <div className="flex items-center space-x-2">
              <div className="flex items-center border border-slate-200 dark:border-slate-700 rounded-md p-0.5 bg-slate-50 dark:bg-slate-800 text-xs">
                <button
                  type="button"
                  onClick={() => setInputMode('form')}
                  className={`px-2 py-0.5 rounded text-[11px] font-medium transition-colors ${
                    inputMode === 'form'
                      ? 'bg-white dark:bg-slate-900 text-brand-600 shadow-xs'
                      : 'text-slate-500'
                  }`}
                >
                  Form
                </button>
                <button
                  type="button"
                  onClick={() => setInputMode('json')}
                  className={`px-2 py-0.5 rounded text-[11px] font-medium transition-colors ${
                    inputMode === 'json'
                      ? 'bg-white dark:bg-slate-900 text-brand-600 shadow-xs'
                      : 'text-slate-500'
                  }`}
                >
                  JSON
                </button>
              </div>

              <button
                type="button"
                onClick={handleResetDefaults}
                className="text-[11px] text-brand-600 hover:text-brand-700 font-medium"
              >
                Reset
              </button>
            </div>
          </div>

          {inputMode === 'form' ? (
            <div className="space-y-3.5">
              <div>
                <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
                  Target Account Name
                </label>
                <input
                  type="text"
                  value={accountName}
                  onChange={(e) => setAccountName(e.target.value)}
                  placeholder="e.g. Acme Health Systems"
                  className="w-full px-3 py-2 text-xs rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-1 focus:ring-brand-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
                  Target Domain
                </label>
                <input
                  type="text"
                  value={domain}
                  onChange={(e) => setDomain(e.target.value)}
                  placeholder="e.g. acmehealth.com"
                  className="w-full px-3 py-2 text-xs rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-1 focus:ring-brand-500 font-mono"
                />
              </div>

              <div>
                <div className="flex items-center justify-between mb-1">
                  <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                    Confidence Threshold
                  </label>
                  <span className="text-xs font-mono font-bold text-brand-600">
                    {minConfidence}
                  </span>
                </div>
                <input
                  type="range"
                  min="0.5"
                  max="1.0"
                  step="0.05"
                  value={minConfidence}
                  onChange={(e) => setMinConfidence(parseFloat(e.target.value))}
                  className="w-full h-1.5 bg-slate-200 dark:bg-slate-700 rounded-lg appearance-none cursor-pointer accent-brand-600"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1.5">
                  Enabled Signal Detectors (All Active)
                </label>
                <div className="grid grid-cols-2 gap-2 text-[11px] text-slate-600 dark:text-slate-400">
                  <div className="flex items-center space-x-1.5 bg-slate-50 dark:bg-slate-850 p-2 rounded-md border border-slate-100 dark:border-slate-800">
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 shrink-0" />
                    <span>Regulatory & Compliance</span>
                  </div>
                  <div className="flex items-center space-x-1.5 bg-slate-50 dark:bg-slate-850 p-2 rounded-md border border-slate-100 dark:border-slate-800">
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 shrink-0" />
                    <span>Hiring & Headcount Spikes</span>
                  </div>
                  <div className="flex items-center space-x-1.5 bg-slate-50 dark:bg-slate-850 p-2 rounded-md border border-slate-100 dark:border-slate-800">
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 shrink-0" />
                    <span>Executive Departures</span>
                  </div>
                  <div className="flex items-center space-x-1.5 bg-slate-50 dark:bg-slate-850 p-2 rounded-md border border-slate-100 dark:border-slate-800">
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 shrink-0" />
                    <span>SEC 10-K Filings</span>
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <div>
              <textarea
                rows={11}
                value={jsonInput}
                onChange={(e) => setJsonInput(e.target.value)}
                className="w-full p-3 font-mono text-xs bg-slate-50 dark:bg-slate-950 border border-slate-300 dark:border-slate-700 rounded-lg focus:ring-1 focus:ring-brand-500 focus:outline-none text-slate-900 dark:text-slate-100 leading-relaxed"
              />
            </div>
          )}

          <div className="pt-2 border-t border-slate-100 dark:border-slate-800 flex justify-end">
            <Button
              onClick={handleExecute}
              isLoading={isExecuting}
              className="text-xs"
            >
              <Play className="w-3.5 h-3.5 mr-1.5" />
              Dispatch Agent 1 Execution
            </Button>
          </div>
        </div>

        {/* FIRST AGENT OUTPUT PANEL */}
        <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 p-5 shadow-xs space-y-4">
          <div className="flex items-center justify-between border-b border-slate-100 dark:border-slate-800 pb-3">
            <div className="flex items-center space-x-2">
              <Sparkles className="w-4 h-4 text-brand-600" />
              <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100">
                Agent 1: Execution Output
              </h3>
            </div>

            {executionResult && (
              <div className="flex items-center space-x-2">
                <Badge
                  variant={
                    executionResult.status === 'completed'
                      ? 'success'
                      : executionResult.status === 'waiting_for_review'
                      ? 'warning'
                      : 'danger'
                  }
                  size="sm"
                >
                  {executionResult.status || 'completed'}
                </Badge>
                <button
                  type="button"
                  onClick={handleCopyResult}
                  className="p-1 rounded text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
                  title="Copy Structured Result"
                >
                  {copiedResult ? (
                    <Check className="w-3.5 h-3.5 text-emerald-600" />
                  ) : (
                    <Copy className="w-3.5 h-3.5" />
                  )}
                </button>
              </div>
            )}
          </div>

          {!executionResult ? (
            <div className="py-16 text-center space-y-2">
              <Radio className="w-8 h-8 text-slate-300 dark:text-slate-700 mx-auto animate-pulse" />
              <p className="text-xs text-slate-500 font-medium">
                No active execution output loaded.
              </p>
              <p className="text-[11px] text-slate-400 max-w-xs mx-auto">
                Click "Dispatch Agent 1 Execution" on the left to run Buying-Signal Radar and view results here.
              </p>
            </div>
          ) : (
            <div className="space-y-3.5">
              {/* Output Summary Highlight */}
              <div className="p-3 rounded-lg bg-blue-50/60 dark:bg-blue-950/30 border border-blue-200/60 dark:border-blue-800/40 space-y-1.5">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] font-mono font-bold text-brand-700 dark:text-brand-300 uppercase tracking-wider">
                    Execution ID: {executionResult.execution_id?.slice(0, 12) || 'exec-live'}...
                  </span>
                  <span className="text-[11px] font-semibold text-emerald-600">
                    Uncertainty: {executionResult.uncertainty ?? '0.00'}
                  </span>
                </div>
                {executionResult.account_name && (
                  <p className="text-xs font-bold text-slate-900 dark:text-slate-100">
                    Account: {executionResult.account_name} ({executionResult.domain})
                  </p>
                )}
                {executionResult.why_now_reason && (
                  <p className="text-xs italic text-slate-700 dark:text-slate-300">
                    "{executionResult.why_now_reason}"
                  </p>
                )}
              </div>

              {/* Proposed Next Actions */}
              {executionResult.proposed_next_actions &&
                executionResult.proposed_next_actions.length > 0 && (
                  <div>
                    <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider block mb-1">
                      Proposed Next Actions:
                    </span>
                    <ul className="text-xs text-slate-700 dark:text-slate-300 space-y-1">
                      {executionResult.proposed_next_actions.map((action: string, i: number) => (
                        <li key={i} className="flex items-center space-x-1.5">
                          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 shrink-0" />
                          <span>{action}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

              {/* Full JSON Payload */}
              <div>
                <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider block mb-1">
                  Structured Result Payload:
                </span>
                <pre className="p-3 bg-slate-50 dark:bg-slate-950 rounded-lg text-[11px] font-mono text-slate-800 dark:text-slate-200 overflow-x-auto max-h-56 border border-slate-200 dark:border-slate-800 leading-relaxed">
                  {JSON.stringify(
                    executionResult.structured_result || executionResult,
                    null,
                    2
                  )}
                </pre>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Agent 1 Execution Stream */}
      <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 p-5 shadow-xs space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2.5">
            <Clock className="w-4 h-4 text-brand-600" />
            <div>
              <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100">
                Agent 1: Live Execution Log
              </h3>
              <p className="text-xs text-slate-500">
                Task executions recorded strictly for Buying-Signal Radar.
              </p>
            </div>
          </div>
          <span className="text-[11px] text-slate-400 font-mono flex items-center space-x-1.5">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
            <span>Polling every 5s</span>
          </span>
        </div>

        {tasksLoading ? (
          <div className="py-6 text-center text-xs text-slate-400">
            Loading execution records...
          </div>
        ) : recentTasks.length === 0 ? (
          <div className="py-6 text-center text-xs text-slate-500">
            No executions recorded yet. Use the input panel above to run Agent 1.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="border-b border-slate-200 dark:border-slate-800 bg-slate-50/70 dark:bg-slate-800/50 text-slate-500 font-semibold">
                  <th className="py-2.5 px-3">Agent</th>
                  <th className="py-2.5 px-3">Execution ID</th>
                  <th className="py-2.5 px-3">Status</th>
                  <th className="py-2.5 px-3">Uncertainty</th>
                  <th className="py-2.5 px-3">Timestamp</th>
                  <th className="py-2.5 px-3 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800 font-mono">
                {recentTasks.map((task: any) => (
                  <tr key={task.id} className="hover:bg-slate-50 dark:hover:bg-slate-800/50">
                    <td className="py-2.5 px-3 font-semibold text-brand-600">
                      Buying-Signal Radar
                    </td>
                    <td className="py-2.5 px-3 text-slate-500">
                      {task.execution_id?.slice(0, 10)}...
                    </td>
                    <td className="py-2.5 px-3">
                      <Badge
                        variant={
                          task.status === 'completed'
                            ? 'success'
                            : task.status === 'waiting_for_review'
                            ? 'warning'
                            : 'default'
                        }
                        size="sm"
                      >
                        {task.status}
                      </Badge>
                    </td>
                    <td className="py-2.5 px-3 text-slate-500">
                      {task.uncertainty !== null && task.uncertainty !== undefined
                        ? Number(task.uncertainty).toFixed(2)
                        : '0.00'}
                    </td>
                    <td className="py-2.5 px-3 text-slate-400 font-sans">
                      {task.created_at ? formatDate(task.created_at) : 'Just now'}
                    </td>
                    <td className="py-2.5 px-3 text-right">
                      <button
                        onClick={() => setExecutionResult(task)}
                        className="text-xs text-brand-600 hover:text-brand-700 font-sans font-medium"
                      >
                        Inspect Output
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};