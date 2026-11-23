import React, { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useSearchParams } from 'react-router-dom';
import {
  MessageSquare,
  Mail,
  Send,
  User,
  Building2,
  Calendar,
  CheckCircle2,
  AlertCircle,
  Video,
  Sparkles,
  ExternalLink,
  Edit3,
  UserX,
  Play,
  RotateCw,
  Search,
  BookOpen,
} from 'lucide-react';
import { apiClient } from '@/lib/apiClient';
import { StandardResponse } from '@/types/api';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { Modal } from '@/components/ui/Modal';
import { LoadingState } from '@/components/ui/FeedbackStates';

interface ConversationSummary {
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

interface MessageItem {
  id: string;
  direction: 'inbound' | 'outbound';
  sender: string;
  recipient: string;
  body: string;
  channel: string;
  created_at: string;
  status: string;
}

interface ConversationDetail {
  conversation_id?: string;
  channel?: string;
  status?: string;
  is_human_takeover?: boolean;
  conversation?: {
    id: string;
    channel: string;
    status: string;
    is_human_takeover: boolean;
    created_at: string;
  };
  contact: {
    id: string;
    name: string;
    email: string;
    phone: string;
    title: string;
    account_id: string;
  };
  account?: {
    id: string;
    name: string;
    domain: string;
    industry: string;
  };
  messages: MessageItem[];
  pending_approval?: {
    approval_id: string;
    draft_content: string;
    source_evidence?: string;
  };
  active_proposal?: {
    proposal_id: string;
    offered_slots: Array<{
      start: string;
      end: string;
      display: string;
      time_str?: string;
    }>;
  };
  confirmed_meeting?: {
    booking_id: string;
    start_time: string;
    teams_join_url?: string;
    outlook_event_id?: string;
  };
  research_brief?: {
    summary?: string;
    company_overview?: string;
    pain_points?: string[];
  };
  marketplace_demos?: Array<{
    name: string;
    demo_video_url?: string;
    product_url?: string;
    overview?: string;
  }>;
}

export const UnifiedInboxPage: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const queryClient = useQueryClient();

  const selectedConvId = searchParams.get('conv');
  const [activeTab, setActiveTab] = useState<'all' | 'sms' | 'email'>('all');
  const [searchFilter, setSearchFilter] = useState('');
  const [editedDraft, setEditedDraft] = useState('');
  const [manualMessage, setManualMessage] = useState('');
  const [syncStatusMsg, setSyncStatusMsg] = useState<{ type: 'success' | 'warning' | 'error'; text: string } | null>(null);

  // Manual Inbound Ingestion State
  const [isLogModalOpen, setIsLogModalOpen] = useState(false);
  const [inboundSender, setInboundSender] = useState('');
  const [inboundChannel, setInboundChannel] = useState<'email' | 'sms'>('email');
  const [inboundBody, setInboundBody] = useState('');

  // 1. Fetch Inbound Threads
  const { data: inboxData, isLoading: loadingInbox } = useQuery<StandardResponse<ConversationSummary[]>>({
    queryKey: ['responder-inbox-threads', activeTab],
    queryFn: async () => {
      const p = activeTab !== 'all' ? `?channel=${activeTab}` : '';
      const res = await apiClient.get<StandardResponse<ConversationSummary[]>>(`/responder/inbox${p}`);
      return res.data;
    },
    refetchInterval: 10000,
  });

  const threads = inboxData?.data || [];

  // Auto-select first thread if none selected
  useEffect(() => {
    if (!selectedConvId && threads.length > 0) {
      setSearchParams({ conv: threads[0].conversation_id });
    }
  }, [threads, selectedConvId, setSearchParams]);

  // 2. Fetch Selected Conversation Details
  const {
    data: detailData,
    isLoading: loadingDetail,
    refetch: refetchDetail,
  } = useQuery<StandardResponse<ConversationDetail>>({
    queryKey: ['responder-conversation-detail', selectedConvId],
    queryFn: async () => {
      if (!selectedConvId) throw new Error('No conversation selected');
      const res = await apiClient.get<StandardResponse<ConversationDetail>>(`/responder/conversations/${selectedConvId}`);
      return res.data;
    },
    enabled: !!selectedConvId,
    refetchInterval: 10000,
  });

  const convDetail = detailData?.data;
  const contactName = convDetail?.contact?.name || 'Inbound Prospect';
  const contactInitial = contactName.charAt(0) || 'P';
  const isTakeover = convDetail?.conversation?.is_human_takeover ?? convDetail?.is_human_takeover ?? false;
  const channelName = (convDetail?.conversation?.channel ?? convDetail?.channel ?? 'sms').toUpperCase();
  const messagesList = Array.isArray(convDetail?.messages) ? convDetail.messages : [];
  const offeredSlots = Array.isArray(convDetail?.active_proposal?.offered_slots)
    ? convDetail.active_proposal.offered_slots
    : [];

  // Sync draft content when detail loads
  useEffect(() => {
    if (convDetail?.pending_approval?.draft_content) {
      setEditedDraft(convDetail.pending_approval.draft_content);
    } else {
      setEditedDraft('');
    }
  }, [convDetail?.pending_approval?.draft_content]);

  // 3. Approve Draft Mutation
  const approveMutation = useMutation({
    mutationFn: async () => {
      if (!selectedConvId) return;
      return apiClient.post(`/responder/conversations/${selectedConvId}/approve`, {
        approved_content: editedDraft,
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['responder-inbox-threads'] });
      queryClient.invalidateQueries({ queryKey: ['responder-conversation-detail', selectedConvId] });
      queryClient.invalidateQueries({ queryKey: ['responder-dashboard'] });
    },
  });

  // 4. Human Takeover Mutation
  const takeoverMutation = useMutation({
    mutationFn: async () => {
      if (!selectedConvId) return;
      return apiClient.post(`/responder/conversations/${selectedConvId}/takeover`);
    },
    onSuccess: () => {
      refetchDetail();
      queryClient.invalidateQueries({ queryKey: ['responder-inbox-threads'] });
    },
  });

  // 5. Resume AI Mutation
  const resumeMutation = useMutation({
    mutationFn: async () => {
      if (!selectedConvId) return;
      return apiClient.post(`/responder/conversations/${selectedConvId}/resume`);
    },
    onSuccess: () => {
      refetchDetail();
      queryClient.invalidateQueries({ queryKey: ['responder-inbox-threads'] });
    },
  });

  // 6. Sync Microsoft Outlook Inbox Mutation
  const syncMutation = useMutation({
    mutationFn: async () => {
      const res = await apiClient.post<StandardResponse<any>>('/responder/sync-inbox');
      return res.data;
    },
    onSuccess: (data) => {
      const payload = data?.data;
      if (payload?.status === 'success') {
        setSyncStatusMsg({
          type: 'success',
          text: `Synced ${payload.synced_count ?? 0} new lead email replies from Microsoft Outlook inbox.`,
        });
      } else if (payload?.status === 'permission_denied') {
        setSyncStatusMsg({
          type: 'warning',
          text: 'Microsoft Graph requires Mail.Read Application Permission in Azure Portal to automatically read inbox replies. You can also ingest replies using the "Log Inbound Reply" button.',
        });
      } else {
        setSyncStatusMsg({
          type: 'warning',
          text: payload?.error || 'Inbox sync completed.',
        });
      }
      queryClient.invalidateQueries({ queryKey: ['responder-inbox-threads'] });
      queryClient.invalidateQueries({ queryKey: ['responder-dashboard'] });
      if (selectedConvId) {
        queryClient.invalidateQueries({ queryKey: ['responder-conversation-detail', selectedConvId] });
      }
    },
    onError: (err: any) => {
      setSyncStatusMsg({
        type: 'error',
        text: 'Failed to sync with Microsoft Graph: ' + (err?.message || 'Check network connection'),
      });
    },
  });

  // 7. Manual Lead Reply Ingestion Mutation
  const inboundMutation = useMutation({
    mutationFn: async () => {
      const payload = {
        sender: inboundSender.trim(),
        recipient: 'sales@adople.ai',
        body: inboundBody.trim(),
        channel: inboundChannel,
        provider: 'manual_intake',
        auto_dispatch: false,
      };
      const res = await apiClient.post<StandardResponse<any>>('/responder/inbound', payload);
      return res.data;
    },
    onSuccess: (data) => {
      setIsLogModalOpen(false);
      setInboundBody('');
      setSyncStatusMsg({
        type: 'success',
        text: `Inbound reply from ${inboundSender} processed through 5-Node Agent 4 pipeline successfully!`,
      });
      queryClient.invalidateQueries({ queryKey: ['responder-inbox-threads'] });
      queryClient.invalidateQueries({ queryKey: ['responder-dashboard'] });
      const newConvId = data?.data?.conversation_id;
      if (newConvId) {
        setSearchParams({ conv: newConvId });
      }
    },
    onError: (err: any) => {
      alert('Failed to ingest reply: ' + (err?.message || 'Unknown error'));
    },
  });

  const handleOpenLogModal = () => {
    if (convDetail?.contact?.email) {
      setInboundSender(convDetail.contact.email);
      setInboundChannel('email');
    } else if (convDetail?.contact?.phone) {
      setInboundSender(convDetail.contact.phone);
      setInboundChannel('sms');
    } else {
      setInboundSender('');
    }
    setInboundBody('');
    setIsLogModalOpen(true);
  };

  const filteredThreads = threads.filter((t) => {
    if (!searchFilter) return true;
    const q = searchFilter.toLowerCase();
    return (
      t.contact_name?.toLowerCase().includes(q) ||
      t.company_name?.toLowerCase().includes(q) ||
      t.last_message_snippet?.toLowerCase().includes(q)
    );
  });

  return (
    <div className="h-[calc(100vh-4rem)] flex flex-col bg-slate-50">
      {/* Top Bar */}
      <div className="bg-white border-b border-slate-200 px-6 py-3 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-3">
          <h1 className="text-base font-bold text-slate-900">Unified Inbound Communications</h1>
          <span className="text-xs text-slate-500">
            Real-time SMS & Microsoft Outlook integration with Human-in-the-Loop review
          </span>
        </div>
        <div className="flex items-center gap-2">
          <Button
            size="sm"
            variant="outline"
            onClick={handleOpenLogModal}
            className="text-xs flex items-center gap-1.5 border-indigo-200 text-indigo-700 hover:bg-indigo-50"
          >
            <Send className="w-3.5 h-3.5" />
            Ingest Lead Reply
          </Button>

          <Button
            size="sm"
            variant="outline"
            onClick={() => syncMutation.mutate()}
            disabled={syncMutation.isPending}
            className="text-xs flex items-center gap-1.5"
          >
            <RotateCw className={`w-3.5 h-3.5 ${syncMutation.isPending ? 'animate-spin' : ''}`} />
            {syncMutation.isPending ? 'Syncing Outlook...' : 'Sync Outlook Inbox'}
          </Button>
        </div>
      </div>

      {/* Sync Status Feedback Banner */}
      {syncStatusMsg && (
        <div className={`px-6 py-2.5 flex items-center justify-between text-xs shrink-0 ${
          syncStatusMsg.type === 'success'
            ? 'bg-emerald-50 text-emerald-800 border-b border-emerald-200'
            : syncStatusMsg.type === 'warning'
            ? 'bg-amber-50 text-amber-800 border-b border-amber-200'
            : 'bg-rose-50 text-rose-800 border-b border-rose-200'
        }`}>
          <div className="flex items-center gap-2">
            {syncStatusMsg.type === 'success' ? (
              <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
            ) : (
              <AlertCircle className="w-4 h-4 text-amber-600 shrink-0" />
            )}
            <span>{syncStatusMsg.text}</span>
          </div>
          <button
            onClick={() => setSyncStatusMsg(null)}
            className="text-xs font-semibold hover:underline px-2 py-0.5"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Main 3-Column Workspace */}
      <div className="flex-1 flex overflow-hidden">
        {/* ================================================================= */}
        {/* LEFT PANEL: Conversation Thread List */}
        {/* ================================================================= */}
        <div className="w-80 bg-white border-r border-slate-200 flex flex-col shrink-0">
          {/* Filter & Search */}
          <div className="p-3 border-b border-slate-100 space-y-2">
            <div className="relative">
              <Search className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400" />
              <input
                type="text"
                placeholder="Search threads..."
                value={searchFilter}
                onChange={(e) => setSearchFilter(e.target.value)}
                className="w-full pl-8 pr-3 py-1.5 text-xs rounded-lg border border-slate-200 focus:outline-none focus:ring-1 focus:ring-indigo-500"
              />
            </div>
            <div className="flex rounded-lg bg-slate-100 p-0.5 text-xs font-medium">
              {(['all', 'sms', 'email'] as const).map((tab) => (
                <button
                  key={tab}
                  onClick={() => setActiveTab(tab)}
                  className={`flex-1 py-1 text-center rounded-md transition-colors ${
                    activeTab === tab
                      ? 'bg-white text-slate-900 shadow-xs font-semibold'
                      : 'text-slate-600 hover:text-slate-900'
                  }`}
                >
                  {tab.toUpperCase()}
                </button>
              ))}
            </div>
          </div>

          {/* Threads Scrollable Area */}
          <div className="flex-1 overflow-y-auto divide-y divide-slate-100">
            {loadingInbox ? (
              <div className="p-4 text-center text-xs text-slate-400">Loading threads...</div>
            ) : filteredThreads.length === 0 ? (
              <div className="p-6 text-center text-xs text-slate-400">No conversations found.</div>
            ) : (
              filteredThreads.map((t) => {
                const isSelected = t.conversation_id === selectedConvId;
                return (
                  <button
                    key={t.conversation_id}
                    onClick={() => setSearchParams({ conv: t.conversation_id })}
                    className={`w-full text-left p-3.5 transition-colors flex flex-col gap-1.5 ${
                      isSelected
                        ? 'bg-indigo-50/70 border-l-4 border-l-indigo-600'
                        : 'hover:bg-slate-50'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-1.5 min-w-0">
                        {t.channel === 'sms' ? (
                          <MessageSquare className="w-3.5 h-3.5 text-emerald-600 shrink-0" />
                        ) : (
                          <Mail className="w-3.5 h-3.5 text-blue-600 shrink-0" />
                        )}
                        <span className="font-semibold text-xs text-slate-900 truncate">
                          {t.contact_name}
                        </span>
                      </div>
                      <span className="text-[10px] text-slate-400 whitespace-nowrap">
                        {t.last_message_time}
                      </span>
                    </div>

                    <div className="text-[11px] font-medium text-slate-500 truncate">
                      {t.company_name}
                    </div>

                    <p className="text-xs text-slate-600 line-clamp-2">
                      {t.last_message_snippet}
                    </p>

                    <div className="flex items-center gap-1.5 mt-0.5">
                      {t.is_human_takeover && (
                        <span className="px-1.5 py-0.2 rounded text-[9px] font-bold bg-amber-100 text-amber-800">
                          Human
                        </span>
                      )}
                      {t.status === 'awaiting_approval' && (
                        <span className="px-1.5 py-0.2 rounded text-[9px] font-bold bg-indigo-100 text-indigo-800">
                          Pending Approval
                        </span>
                      )}
                    </div>
                  </button>
                );
              })
            )}
          </div>
        </div>

        {/* ================================================================= */}
        {/* CENTER PANEL: Live Message Timeline & Human Approval Box */}
        {/* ================================================================= */}
        <div className="flex-1 flex flex-col bg-slate-50 overflow-hidden">
          {loadingDetail ? (
            <div className="flex-1 flex items-center justify-center">
              <LoadingState message="Loading conversation timeline..." />
            </div>
          ) : !convDetail ? (
            <div className="flex-1 flex flex-col items-center justify-center p-8 text-center text-slate-400">
              <div className="w-12 h-12 rounded-full bg-slate-100 flex items-center justify-center text-slate-400 mb-3">
                <MessageSquare className="w-6 h-6" />
              </div>
              <h3 className="text-sm font-bold text-slate-700">No Conversation Selected</h3>
              <p className="text-xs text-slate-500 max-w-sm mt-1">
                Select an active lead thread from the left panel, or trigger a simulated message from Workflow Telemetry.
              </p>
            </div>
          ) : (
            <>
              {/* Active Thread Header */}
              <div className="bg-white border-b border-slate-200 px-6 py-3.5 flex items-center justify-between shrink-0">
                <div className="flex items-center gap-3">
                  <div className="w-9 h-9 rounded-full bg-indigo-100 text-indigo-700 font-bold flex items-center justify-center text-sm">
                    {contactInitial}
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-bold text-sm text-slate-900">
                        {contactName}
                      </span>
                      <span className="text-xs text-slate-500 font-medium">
                        — {convDetail.contact?.title || 'Decision Maker'} at {convDetail.account?.name || 'Prospect'}
                      </span>
                    </div>
                    <div className="flex items-center gap-2 text-[11px] text-slate-500 mt-0.5">
                      <span>{convDetail.contact?.email || 'No email provided'}</span>
                      {convDetail.contact?.phone && <span>• {convDetail.contact.phone}</span>}
                    </div>
                  </div>
                </div>

                {/* Takeover Control */}
                <div className="flex items-center gap-2">
                  {isTakeover ? (
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => resumeMutation.mutate()}
                      disabled={resumeMutation.isPending}
                      className="border-emerald-200 text-emerald-700 hover:bg-emerald-50 text-xs flex items-center gap-1.5"
                    >
                      <Play className="w-3.5 h-3.5" />
                      Resume AI Automation
                    </Button>
                  ) : (
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => takeoverMutation.mutate()}
                      disabled={takeoverMutation.isPending}
                      className="border-amber-200 text-amber-700 hover:bg-amber-50 text-xs flex items-center gap-1.5"
                    >
                      <UserX className="w-3.5 h-3.5" />
                      Take Over Conversation
                    </Button>
                  )}
                </div>
              </div>

              {/* Human Takeover Notice Banner */}
              {isTakeover && (
                <div className="bg-amber-50 border-b border-amber-200 px-6 py-2 flex items-center gap-2 text-xs text-amber-800 font-medium shrink-0">
                  <AlertCircle className="w-4 h-4 text-amber-600 shrink-0" />
                  <span>
                    Human Takeover is active for this conversation. Autonomous AI replies are paused.
                  </span>
                </div>
              )}

              {/* Confirmed Meeting Alert Banner */}
              {convDetail.confirmed_meeting?.teams_join_url && (
                <div className="bg-emerald-50 border-b border-emerald-200 px-6 py-2.5 flex items-center justify-between text-xs text-emerald-900 shrink-0">
                  <div className="flex items-center gap-2">
                    <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
                    <span className="font-semibold">
                      Discovery Meeting Confirmed for {convDetail.confirmed_meeting.start_time}
                    </span>
                  </div>
                  <a
                    href={convDetail.confirmed_meeting.teams_join_url}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1 text-xs font-bold text-white bg-emerald-600 hover:bg-emerald-700 px-2.5 py-1 rounded shadow-xs"
                  >
                    <Video className="w-3.5 h-3.5" />
                    Join Microsoft Teams
                  </a>
                </div>
              )}

              {/* Messages Chat Stream */}
              <div className="flex-1 overflow-y-auto p-6 space-y-4">
                {messagesList.length === 0 ? (
                  <div className="text-center py-8 text-xs text-slate-400">
                    No message history recorded for this conversation.
                  </div>
                ) : (
                  messagesList.map((m) => {
                    const isInbound = m.direction === 'inbound';
                    return (
                      <div
                        key={m.id}
                        className={`flex flex-col ${isInbound ? 'items-start' : 'items-end'}`}
                      >
                        <div className="flex items-center gap-1.5 mb-1 px-1">
                          <span className="text-[10px] font-bold text-slate-500 uppercase">
                            {isInbound ? contactName : 'Adople AI Sales Assistant'}
                          </span>
                          <span className="text-[10px] text-slate-400">
                            {m.created_at}
                          </span>
                        </div>

                        <div
                          className={`max-w-xl rounded-2xl p-4 text-xs shadow-xs leading-relaxed ${
                            isInbound
                              ? 'bg-white text-slate-800 border border-slate-200 rounded-tl-xs'
                              : 'bg-indigo-600 text-white rounded-tr-xs'
                          }`}
                        >
                          <p className="whitespace-pre-wrap">{m.body}</p>
                        </div>
                      </div>
                    );
                  })
                )}
              </div>

              {/* Human-in-the-Loop Review & AI Approval Box */}
              {convDetail.pending_approval ? (
                <div className="bg-white border-t border-slate-200 p-4 shadow-lg shrink-0">
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <Sparkles className="w-4 h-4 text-indigo-600" />
                      <span className="text-xs font-bold text-slate-900">
                        Node 5 Generated AI Draft (Awaiting Approval)
                      </span>
                      <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-indigo-50 text-indigo-700 border border-indigo-200">
                        Grounded with Verified Context
                      </span>
                    </div>
                    <span className="text-[11px] text-slate-400">
                      Channel: {channelName}
                    </span>
                  </div>

                  <div className="relative">
                    <textarea
                      rows={3}
                      value={editedDraft}
                      onChange={(e) => setEditedDraft(e.target.value)}
                      className="w-full text-xs p-3 rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-indigo-500 bg-slate-50 font-sans leading-relaxed"
                      placeholder="Review or customize AI response before sending..."
                    />
                  </div>

                  <div className="mt-3 flex items-center justify-between">
                    <div className="text-[11px] text-slate-500 flex items-center gap-1">
                      <Edit3 className="w-3.5 h-3.5 text-slate-400" />
                      <span>Edit draft inline if adjustments are required</span>
                    </div>

                    <div className="flex items-center gap-2">
                      <Button
                        size="sm"
                        onClick={() => approveMutation.mutate()}
                        disabled={approveMutation.isPending || !editedDraft.trim()}
                        className="bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold flex items-center gap-1.5 shadow-xs"
                      >
                        <Send className="w-3.5 h-3.5" />
                        {approveMutation.isPending
                          ? 'Dispatching...'
                          : `Approve & Dispatch (${channelName})`}
                      </Button>
                    </div>
                  </div>
                </div>
              ) : null}
            </>
          )}
        </div>

        {/* ================================================================= */}
        {/* RIGHT PANEL: Customer Context & Agent Memory Drawer */}
        {/* ================================================================= */}
        <div className="w-80 bg-white border-l border-slate-200 flex flex-col shrink-0 overflow-y-auto p-4 space-y-4">
          <h2 className="text-xs font-bold uppercase tracking-wider text-slate-500">
            Lead Memory & Context
          </h2>

          {/* Account & Contact Card */}
          <div className="p-3.5 rounded-lg border border-slate-200 bg-slate-50/50 space-y-2">
            <div className="flex items-center gap-2">
              <Building2 className="w-4 h-4 text-indigo-600 shrink-0" />
              <div className="font-bold text-xs text-slate-900 truncate">
                {convDetail?.account?.name || 'Enterprise Prospect'}
              </div>
            </div>
            <div className="text-[11px] text-slate-500">
              Industry: {convDetail?.account?.industry || 'Technology / Operations'}
            </div>
            <div className="text-[11px] text-slate-500">
              Domain: {convDetail?.account?.domain || 'enterprise.com'}
            </div>
          </div>

          {/* Calendar Status Card */}
          <div className="p-3.5 rounded-lg border border-slate-200 bg-slate-50/50 space-y-2">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Calendar className="w-4 h-4 text-emerald-600 shrink-0" />
                <span className="font-bold text-xs text-slate-900">Calendar Status</span>
              </div>
            </div>

            {convDetail?.confirmed_meeting ? (
              <div className="space-y-1.5 mt-1">
                <div className="text-[11px] font-semibold text-emerald-700">
                  Confirmed: {convDetail.confirmed_meeting.start_time}
                </div>
                {convDetail.confirmed_meeting.teams_join_url && (
                  <a
                    href={convDetail.confirmed_meeting.teams_join_url}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1 text-[11px] text-indigo-600 hover:underline font-medium"
                  >
                    <Video className="w-3 h-3" />
                    Open Microsoft Teams link
                  </a>
                )}
              </div>
            ) : convDetail?.active_proposal && offeredSlots.length > 0 ? (
              <div className="space-y-1 mt-1">
                <span className="text-[11px] font-medium text-amber-700">
                  Proposed Alternative Slot Offered:
                </span>
                {offeredSlots.map((slot: any, idx: number) => (
                  <div key={idx} className="text-[11px] text-slate-700 font-semibold bg-white p-1.5 rounded border border-slate-200">
                    {slot.display || slot.time_str || slot.start || 'Proposed Slot'}
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-[11px] text-slate-400">No meeting scheduled yet.</p>
            )}
          </div>

          {/* Pipeline 2 Research Brief */}
          {convDetail?.research_brief && (
            <div className="p-3.5 rounded-lg border border-slate-200 bg-slate-50/50 space-y-2">
              <div className="flex items-center gap-2">
                <BookOpen className="w-4 h-4 text-violet-600 shrink-0" />
                <span className="font-bold text-xs text-slate-900">Research Brief (Pipeline 2)</span>
              </div>
              <p className="text-[11px] text-slate-600 leading-relaxed">
                {convDetail.research_brief.summary || convDetail.research_brief.company_overview}
              </p>
            </div>
          )}

          {/* Pipeline 3 Demo Link */}
          {convDetail?.marketplace_demos && convDetail.marketplace_demos.length > 0 && (
            <div className="p-3.5 rounded-lg border border-slate-200 bg-slate-50/50 space-y-2">
              <div className="flex items-center gap-2">
                <Video className="w-4 h-4 text-blue-600 shrink-0" />
                <span className="font-bold text-xs text-slate-900">Demo Walkthrough (Pipeline 3)</span>
              </div>
              {convDetail.marketplace_demos.map((d, i) => (
                <div key={i} className="space-y-1">
                  <div className="text-[11px] font-semibold text-slate-800">{d.name}</div>
                  {d.demo_video_url && (
                    <a
                      href={d.demo_video_url}
                      target="_blank"
                      rel="noreferrer"
                      className="text-[11px] text-indigo-600 hover:underline flex items-center gap-1"
                    >
                      <span>Interactive Demo Video</span>
                      <ExternalLink className="w-3 h-3" />
                    </a>
                  )}
                  {d.product_url && (
                    <a
                      href={d.product_url}
                      target="_blank"
                      rel="noreferrer"
                      className="text-[10px] text-slate-500 hover:underline flex items-center gap-1"
                    >
                      <span>Marketplace Profile</span>
                      <ExternalLink className="w-2.5 h-2.5" />
                    </a>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Ingest Inbound Reply Modal */}
      <Modal
        isOpen={isLogModalOpen}
        onClose={() => setIsLogModalOpen(false)}
        title="Ingest Prospect Inbound Reply"
        description="Process a real email or SMS reply from a prospect through the 5-node Agent 4 pipeline."
      >
        <div className="space-y-4 pt-2">
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">
              Communication Channel
            </label>
            <div className="flex gap-4">
              <label className="flex items-center gap-2 text-xs text-slate-700 cursor-pointer">
                <input
                  type="radio"
                  name="inboundChannel"
                  value="email"
                  checked={inboundChannel === 'email'}
                  onChange={() => setInboundChannel('email')}
                />
                <span>Email (Outlook / Mail)</span>
              </label>
              <label className="flex items-center gap-2 text-xs text-slate-700 cursor-pointer">
                <input
                  type="radio"
                  name="inboundChannel"
                  value="sms"
                  checked={inboundChannel === 'sms'}
                  onChange={() => setInboundChannel('sms')}
                />
                <span>SMS (+1 Phone)</span>
              </label>
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">
              Prospect Email or Phone Number
            </label>
            <input
              type="text"
              value={inboundSender}
              onChange={(e) => setInboundSender(e.target.value)}
              placeholder="e.g. prospect@company.com or +14155550199"
              className="w-full text-xs p-2 rounded-lg border border-slate-300 focus:outline-none focus:ring-1 focus:ring-indigo-500"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">
              Received Reply Content
            </label>
            <textarea
              rows={4}
              value={inboundBody}
              onChange={(e) => setInboundBody(e.target.value)}
              placeholder="Paste the prospect's reply message here..."
              className="w-full text-xs p-2.5 rounded-lg border border-slate-300 focus:outline-none focus:ring-1 focus:ring-indigo-500 font-sans"
            />
          </div>

          <div className="flex justify-end gap-2 pt-2 border-t border-slate-100">
            <Button
              size="sm"
              variant="outline"
              onClick={() => setIsLogModalOpen(false)}
            >
              Cancel
            </Button>
            <Button
              size="sm"
              onClick={() => inboundMutation.mutate()}
              disabled={inboundMutation.isPending || !inboundSender.trim() || !inboundBody.trim()}
              className="bg-indigo-600 hover:bg-indigo-700 text-white"
            >
              {inboundMutation.isPending ? 'Processing 5 Nodes...' : 'Ingest & Run Pipeline'}
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
};
