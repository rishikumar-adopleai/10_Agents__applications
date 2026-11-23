import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Sparkles,
  ArrowRight,
  ShieldCheck,
  Brain,
  Calendar,
  Send,
  Video,
  Database,
  Play,
  RotateCw,
  Clock,
  CheckCircle2,
  AlertCircle,
  Eye,
  FileText,
  MessageSquare,
  Mail,
} from 'lucide-react';
import { apiClient } from '@/lib/apiClient';
import { StandardResponse } from '@/types/api';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { LoadingState } from '@/components/ui/FeedbackStates';

interface TelemetryLogItem {
  id: string;
  message_id: string;
  conversation_id: string;
  channel: string;
  node1_ingest: any;
  node2_context: any;
  node3_safety: any;
  node4_memory: any;
  node5_intent_draft: any;
  approval_status: string;
  send_status: string;
  total_latency_ms: number;
  status: string;
  timestamp: string;
}

interface SimulationResult {
  simulation_scenario: string;
  sender: string;
  body: string;
  channel: string;
  result: {
    status: string;
    conversation_id: string;
    message_id?: string;
    draft_reply?: string;
    approval_status?: string;
    send_status?: string;
    action?: string;
    decision?: string;
    reason?: string;
    node1: any;
    node2: any;
    node3: any;
    node4?: any;
    node5?: any;
  };
}

export const WorkflowMonitoringPage: React.FC = () => {
  const queryClient = useQueryClient();

  const [scenarioType, setScenarioType] = useState('2am_meeting_request');
  const [simChannel, setSimChannel] = useState<'sms' | 'email'>('sms');
  const [simSender, setSimSender] = useState('+14155550199');
  const [simBody, setSimBody] = useState('Can we meet next Thursday at 2:00 AM to discuss the AI platform?');
  const [simulationResult, setSimulationResult] = useState<SimulationResult | null>(null);
  const [expandedLog, setExpandedLog] = useState<TelemetryLogItem | null>(null);

  // 1. Fetch Telemetry Logs
  const { data, isLoading, refetch, isFetching } = useQuery<StandardResponse<TelemetryLogItem[]>>({
    queryKey: ['responder-monitoring-logs'],
    queryFn: async () => {
      const res = await apiClient.get<StandardResponse<TelemetryLogItem[]>>('/responder/monitoring');
      return res.data;
    },
    refetchInterval: 10000,
  });

  const logs = data?.data || [];

  // 2. Simulation Mutation
  const simulateMutation = useMutation({
    mutationFn: async () => {
      const payload = {
        scenario_type: scenarioType,
        sender: simSender,
        body: simBody,
        channel: simChannel,
      };
      const res = await apiClient.post<StandardResponse<SimulationResult>>('/responder/simulate', payload);
      return res.data;
    },
    onSuccess: (data) => {
      setSimulationResult(data.data);
      queryClient.invalidateQueries({ queryKey: ['responder-monitoring-logs'] });
      queryClient.invalidateQueries({ queryKey: ['responder-dashboard'] });
      queryClient.invalidateQueries({ queryKey: ['responder-meetings'] });
    },
  });

  const handleScenarioChange = (type: string) => {
    setScenarioType(type);
    if (type === '2am_meeting_request') {
      setSimChannel('sms');
      setSimSender('+14155550199');
      setSimBody('Can we meet next Thursday at 2:00 AM to discuss the AI platform?');
    } else if (type === 'lead_confirmation_3am') {
      setSimChannel('sms');
      setSimSender('+14155550199');
      setSimBody('Yes, 3 AM works for me. Please confirm.');
    } else if (type === 'opt_out_stop') {
      setSimChannel('sms');
      setSimSender('+14155550199');
      setSimBody('STOP');
    } else if (type === 'demo_request') {
      setSimChannel('email');
      setSimSender('bruce.wayne@wayneenterprises.com');
      setSimBody('Can you send me an interactive demo video of your autonomous voice sales agent?');
    } else if (type === 'negative_tone_buying_interest') {
      setSimChannel('email');
      setSimSender('carol.danvers@avengers-enterprise.com');
      setSimBody('Our existing CRM provider is completely broken and leaking lead data. Can your platform fix our compliance issues?');
    } else if (type === 'human_handoff') {
      setSimChannel('sms');
      setSimSender('+14155550199');
      setSimBody('Can I please speak directly with a human sales representative?');
    }
  };

  return (
    <div className="space-y-6 p-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 bg-white p-6 rounded-xl border border-slate-200 shadow-xs">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-xl font-bold text-slate-900">Pipeline 4: 5-Node Workflow Monitoring</h1>
            <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-violet-100 text-violet-800 border border-violet-200">
              <Sparkles className="w-3.5 h-3.5 mr-1" />
              Autonomous Engine Telemetry
            </span>
          </div>
          <p className="text-xs text-slate-500 mt-1">
            Exact 5-node architecture telemetry with interactive scenario simulation and real-time execution inspection.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            size="sm"
            variant="outline"
            onClick={() => refetch()}
            disabled={isFetching}
            className="text-xs flex items-center gap-1.5"
          >
            <RotateCw className={`w-3.5 h-3.5 ${isFetching ? 'animate-spin' : ''}`} />
            Refresh Logs
          </Button>
        </div>
      </div>

      {/* 5-Node Architecture Flow Visualizer */}
      <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-xs">
        <h2 className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-4">
          Internal 5-Node Processing Pipeline
        </h2>

        <div className="grid grid-cols-1 md:grid-cols-5 gap-3">
          {/* Node 1 */}
          <div className="p-3.5 rounded-lg border border-indigo-100 bg-indigo-50/40 relative">
            <div className="flex items-center gap-2 text-indigo-700 font-bold text-xs mb-1">
              <span className="w-5 h-5 rounded-full bg-indigo-600 text-white flex items-center justify-center text-[10px]">1</span>
              <span>Node 1: Ingest</span>
            </div>
            <p className="text-[11px] text-slate-600 leading-snug">
              Normalize sender (E.164 phone / email), atomic message persistence & SHA-256 deduplication.
            </p>
          </div>

          {/* Node 2 */}
          <div className="p-3.5 rounded-lg border border-blue-100 bg-blue-50/40 relative">
            <div className="flex items-center gap-2 text-blue-700 font-bold text-xs mb-1">
              <span className="w-5 h-5 rounded-full bg-blue-600 text-white flex items-center justify-center text-[10px]">2</span>
              <span>Node 2: Context</span>
            </div>
            <p className="text-[11px] text-slate-600 leading-snug">
              Identify lead/contact in PostgreSQL, associate account & bind conversation thread atomically.
            </p>
          </div>

          {/* Node 3 */}
          <div className="p-3.5 rounded-lg border border-amber-100 bg-amber-50/40 relative">
            <div className="flex items-center gap-2 text-amber-700 font-bold text-xs mb-1">
              <span className="w-5 h-5 rounded-full bg-amber-600 text-white flex items-center justify-center text-[10px]">3</span>
              <span>Node 3: Safety</span>
            </div>
            <p className="text-[11px] text-slate-600 leading-snug">
              Deterministic checks (STOP opt-out, takeover) + structured sentiment vs contact rejection classification.
            </p>
          </div>

          {/* Node 4 */}
          <div className="p-3.5 rounded-lg border border-violet-100 bg-violet-50/40 relative">
            <div className="flex items-center gap-2 text-violet-700 font-bold text-xs mb-1">
              <span className="w-5 h-5 rounded-full bg-violet-600 text-white flex items-center justify-center text-[10px]">4</span>
              <span>Node 4: Memory</span>
            </div>
            <p className="text-[11px] text-slate-600 leading-snug">
              Load history, Pipeline 2 research briefs, Pipeline 3 marketplace demos, calendar proposals & KB facts.
            </p>
          </div>

          {/* Node 5 */}
          <div className="p-3.5 rounded-lg border border-emerald-100 bg-emerald-50/40 relative">
            <div className="flex items-center gap-2 text-emerald-700 font-bold text-xs mb-1">
              <span className="w-5 h-5 rounded-full bg-emerald-600 text-white flex items-center justify-center text-[10px]">5</span>
              <span>Node 5: Intent & Draft</span>
            </div>
            <p className="text-[11px] text-slate-600 leading-snug">
              Owns intent classification, tool execution (Outlook & Teams booking, Demos, KB) & grounded AI drafting.
            </p>
          </div>
        </div>
      </div>

      {/* Interactive Scenario Simulator */}
      <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-xs space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-sm font-bold text-slate-900">Interactive Pipeline 4 Simulator</h2>
            <p className="text-xs text-slate-500 mt-0.5">
              Simulate live inbound messages and inspect the exact node-by-node execution pipeline in real-time.
            </p>
          </div>
          <span className="text-xs font-semibold px-2.5 py-1 rounded-full bg-slate-100 text-slate-700">
            Interactive Test Runner
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-2">
          {/* Preset Selector */}
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">
              Test Scenario Preset
            </label>
            <select
              value={scenarioType}
              onChange={(e) => handleScenarioChange(e.target.value)}
              className="w-full text-xs p-2 rounded-lg border border-slate-200 bg-white focus:outline-none focus:ring-1 focus:ring-indigo-500"
            >
              <option value="2am_meeting_request">1. 2:00 AM Meeting (Occupied $\rightarrow$ 3 AM Alternative)</option>
              <option value="lead_confirmation_3am">2. Lead Confirms 3 AM (Auto-Booked + Teams Link)</option>
              <option value="opt_out_stop">3. Explicit Opt-Out STOP (Hard Suppression)</option>
              <option value="demo_request">4. Pipeline 3 Demo Request (Marketplace Link)</option>
              <option value="negative_tone_buying_interest">5. Negative Tone + High Buying Interest</option>
              <option value="human_handoff">6. Human Agent Takeover Request</option>
            </select>
          </div>

          {/* Channel */}
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">Communication Channel</label>
            <select
              value={simChannel}
              onChange={(e) => setSimChannel(e.target.value as 'sms' | 'email')}
              className="w-full text-xs p-2 rounded-lg border border-slate-200 bg-white focus:outline-none focus:ring-1 focus:ring-indigo-500"
            >
              <option value="sms">SMS (+1 Virtual Number)</option>
              <option value="email">Email (Outlook Mail.Send)</option>
            </select>
          </div>

          {/* Sender */}
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">Inbound Sender</label>
            <input
              type="text"
              value={simSender}
              onChange={(e) => setSimSender(e.target.value)}
              className="w-full text-xs p-2 rounded-lg border border-slate-200 focus:outline-none focus:ring-1 focus:ring-indigo-500"
            />
          </div>
        </div>

        {/* Message Body */}
        <div>
          <label className="block text-xs font-semibold text-slate-700 mb-1">
            Simulated Inbound Message Body
          </label>
          <textarea
            rows={2}
            value={simBody}
            onChange={(e) => setSimBody(e.target.value)}
            className="w-full text-xs p-3 rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-indigo-500 font-sans"
          />
        </div>

        <div className="flex justify-end">
          <Button
            size="sm"
            onClick={() => simulateMutation.mutate()}
            disabled={simulateMutation.isPending || !simBody.trim()}
            className="bg-indigo-600 hover:bg-indigo-700 text-white font-semibold flex items-center gap-1.5 text-xs shadow-xs"
          >
            <Play className="w-3.5 h-3.5" />
            {simulateMutation.isPending ? 'Executing 5 Nodes...' : 'Run Live Pipeline Simulation'}
          </Button>
        </div>

        {/* Simulation Output Card */}
        {simulationResult && (() => {
          const simRes = (simulationResult as any)?.result || simulationResult;
          const scenarioTitle = simulationResult.simulation_scenario || scenarioType;
          const statusText = (simRes?.status || 'completed').toUpperCase();

          return (
            <div className="mt-4 p-5 rounded-xl border border-indigo-200 bg-indigo-50/30 space-y-4">
              <div className="flex items-center justify-between border-b border-indigo-100 pb-3">
                <div className="flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                  <span className="font-bold text-xs text-slate-900">
                    Simulation Execution Result: {scenarioTitle}
                  </span>
                </div>
                <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-indigo-100 text-indigo-800">
                  Status: {statusText}
                </span>
              </div>

              {/* Generated Draft Reply Banner */}
              {simRes?.draft_reply && (
                <div className="p-3.5 rounded-lg bg-white border border-indigo-100 space-y-1.5 shadow-xs">
                  <span className="text-[11px] font-bold text-indigo-700 uppercase tracking-wider block">
                    Node 5 Generated AI Draft Reply:
                  </span>
                  <p className="text-xs text-slate-800 whitespace-pre-wrap leading-relaxed font-sans">
                    {simRes.draft_reply}
                  </p>
                  <div className="text-[10px] text-slate-400 pt-1 flex items-center gap-3">
                    <span>Approval: {simRes.approval_status || 'pending'}</span>
                    <span>Dispatch: {simRes.send_status || 'held_for_human_review'}</span>
                  </div>
                </div>
              )}

              {/* If Suppressed */}
              {simRes?.action === 'suppressed' && (
                <div className="p-3.5 rounded-lg bg-rose-50 border border-rose-200 text-xs text-rose-800 font-medium">
                  Action: Hard Suppression Applied. Outbound AI replies blocked.
                  Reason: {simRes.reason}
                </div>
              )}

              {/* Node by Node Inspection Details */}
              <div className="grid grid-cols-1 md:grid-cols-5 gap-2 text-[11px]">
                <div className="bg-white p-2.5 rounded border border-slate-200">
                  <div className="font-bold text-slate-700 mb-1">Node 1 (Ingest)</div>
                  <div className="text-slate-500">Sender: {simRes?.node1?.normalized_sender}</div>
                  <div className="text-slate-400 text-[10px]">Duration: {simRes?.node1?.duration_ms}ms</div>
                </div>

                <div className="bg-white p-2.5 rounded border border-slate-200">
                  <div className="font-bold text-slate-700 mb-1">Node 2 (Context)</div>
                  <div className="text-slate-500">{simRes?.node2?.contact_name || 'Prospect'}</div>
                  <div className="text-slate-400 text-[10px]">{simRes?.node2?.identity_resolution_status}</div>
                </div>

                <div className="bg-white p-2.5 rounded border border-slate-200">
                  <div className="font-bold text-slate-700 mb-1">Node 3 (Safety)</div>
                  <div className="text-slate-500">Sent: {simRes?.node3?.sentiment}</div>
                  <div className="text-slate-400 text-[10px]">Decision: {simRes?.node3?.processing_decision}</div>
                </div>

                <div className="bg-white p-2.5 rounded border border-slate-200">
                  <div className="font-bold text-slate-700 mb-1">Node 4 (Memory)</div>
                  <div className="text-slate-500">History: {simRes?.node4?.history_count ?? 0} msgs</div>
                  <div className="text-slate-400 text-[10px]">Context bound</div>
                </div>

                <div className="bg-white p-2.5 rounded border border-slate-200">
                  <div className="font-bold text-slate-700 mb-1">Node 5 (Draft)</div>
                  <div className="text-slate-500">Intent: {simRes?.node5?.primary_intent || 'handled'}</div>
                  <div className="text-slate-400 text-[10px]">Auto-Appr: {String(simRes?.node5?.auto_approved ?? false)}</div>
                </div>
              </div>
            </div>
          );
        })()}
      </div>

      {/* Telemetry Logs Table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
        <div className="p-4 border-b border-slate-200 flex items-center justify-between">
          <div>
            <h2 className="text-sm font-bold text-slate-900">Recent Node Execution Telemetry Logs</h2>
            <p className="text-xs text-slate-500 mt-0.5">
              Live observability stream for incoming inquiries
            </p>
          </div>
          <span className="text-xs text-slate-500">
            Total records: {logs.length}
          </span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse text-xs">
            <thead>
              <tr className="bg-slate-50 border-b border-slate-200 text-slate-500 font-semibold">
                <th className="py-2.5 px-4">Execution ID</th>
                <th className="py-2.5 px-4">Channel</th>
                <th className="py-2.5 px-4">Safety Sentiment</th>
                <th className="py-2.5 px-4">Intent & Decision</th>
                <th className="py-2.5 px-4">Approval</th>
                <th className="py-2.5 px-4">Latency</th>
                <th className="py-2.5 px-4 text-right">Inspect</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {logs.length === 0 ? (
                <tr>
                  <td colSpan={7} className="py-8 text-center text-slate-400">
                    No execution telemetry logs recorded yet.
                  </td>
                </tr>
              ) : (
                logs.slice(0, 15).map((l) => (
                  <tr key={l.id} className="hover:bg-slate-50/70 transition-colors">
                    <td className="py-3 px-4 font-mono text-[11px] text-slate-700">
                      {l.id}
                    </td>
                    <td className="py-3 px-4">
                      <span className="uppercase text-[10px] font-bold text-slate-600">
                        {l.channel}
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      <span className={`inline-flex items-center px-1.5 py-0.2 rounded text-[10px] font-semibold ${
                        l.node3_safety?.sentiment === 'positive'
                          ? 'bg-emerald-100 text-emerald-800'
                          : l.node3_safety?.sentiment === 'negative'
                          ? 'bg-rose-100 text-rose-800'
                          : l.node3_safety?.sentiment === 'unsubscribe'
                          ? 'bg-purple-100 text-purple-800'
                          : 'bg-slate-100 text-slate-700'
                      }`}>
                        {l.node3_safety?.sentiment || 'neutral'}
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      <div className="font-semibold text-slate-800">
                        {l.node5_intent_draft?.primary_intent || l.node3_safety?.primary_intent || 'inquiry'}
                      </div>
                      <div className="text-[10px] text-slate-400">
                        {l.node3_safety?.processing_decision || 'continue'}
                      </div>
                    </td>
                    <td className="py-3 px-4">
                      <span className="text-[11px] font-medium text-slate-600">
                        {l.approval_status}
                      </span>
                    </td>
                    <td className="py-3 px-4 font-mono text-[11px] text-slate-600">
                      {l.total_latency_ms}ms
                    </td>
                    <td className="py-3 px-4 text-right">
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => setExpandedLog(expandedLog?.id === l.id ? null : l)}
                        className="text-xs py-1 px-2"
                      >
                        {expandedLog?.id === l.id ? 'Close' : 'Details'}
                      </Button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Expanded Telemetry Modal */}
      {expandedLog && (
        <div className="fixed inset-0 bg-black/40 backdrop-blur-xs flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-xl max-w-3xl w-full p-6 shadow-xl space-y-4 max-h-[85vh] overflow-y-auto">
            <div className="flex items-center justify-between border-b border-slate-200 pb-3">
              <div>
                <h3 className="text-sm font-bold text-slate-900">
                  Node Telemetry Details: {expandedLog.id}
                </h3>
                <span className="text-[11px] text-slate-500 font-mono">
                  Conversation: {expandedLog.conversation_id} • Latency: {expandedLog.total_latency_ms}ms
                </span>
              </div>
              <Button size="sm" variant="outline" onClick={() => setExpandedLog(null)}>
                Close
              </Button>
            </div>

            <div className="space-y-3 text-xs">
              <div className="p-3 bg-slate-50 rounded-lg border border-slate-200">
                <span className="font-bold text-slate-800 block mb-1">Node 1: Ingest</span>
                <pre className="text-[11px] text-slate-700 overflow-x-auto whitespace-pre-wrap">
                  {JSON.stringify(expandedLog.node1_ingest, null, 2)}
                </pre>
              </div>

              <div className="p-3 bg-slate-50 rounded-lg border border-slate-200">
                <span className="font-bold text-slate-800 block mb-1">Node 2: Context</span>
                <pre className="text-[11px] text-slate-700 overflow-x-auto whitespace-pre-wrap">
                  {JSON.stringify(expandedLog.node2_context, null, 2)}
                </pre>
              </div>

              <div className="p-3 bg-slate-50 rounded-lg border border-slate-200">
                <span className="font-bold text-slate-800 block mb-1">Node 3: Safety & Sentiment</span>
                <pre className="text-[11px] text-slate-700 overflow-x-auto whitespace-pre-wrap">
                  {JSON.stringify(expandedLog.node3_safety, null, 2)}
                </pre>
              </div>

              <div className="p-3 bg-slate-50 rounded-lg border border-slate-200">
                <span className="font-bold text-slate-800 block mb-1">Node 5: Intent, Tools & Draft</span>
                <pre className="text-[11px] text-slate-700 overflow-x-auto whitespace-pre-wrap">
                  {JSON.stringify(expandedLog.node5_intent_draft, null, 2)}
                </pre>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
