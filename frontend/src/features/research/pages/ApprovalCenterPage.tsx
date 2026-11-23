import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  CheckCircle2,
  XCircle,
  Clock,
  RotateCw,
  Search,
  Filter,
  Eye,
  Edit3,
  ShieldCheck,
  Building2,
  Users,
  Send,
  Sparkles,
  AlertCircle,
  ExternalLink,
  Trash2,
} from 'lucide-react';
import { apiClient } from '@/lib/apiClient';
import { StandardResponse } from '@/types/api';
import { Modal } from '@/components/ui/Modal';
import { LoadingState, EmptyState } from '@/components/ui/FeedbackStates';

interface ApprovalItemData {
  approval_id: string;
  account_id: string;
  company_name: string;
  contact_name: string;
  contact_title: string;
  contact_email: string;
  message_preview: string;
  draft_body: string;
  channel: string;
  demo_status: string;
  draft_version: string;
  submitted_date: string;
  status: string;
  raw_status: string;
  review_feedback?: string;
  evidence_facts?: Record<string, any>;
  sources?: string[];
}

export const ApprovalCenterPage: React.FC = () => {
  const queryClient = useQueryClient();

  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [selectedItem, setSelectedItem] = useState<ApprovalItemData | null>(null);
  const [isReviewModalOpen, setIsReviewModalOpen] = useState(false);
  const [editedBody, setEditedBody] = useState('');
  const [reviewerFeedback, setReviewerFeedback] = useState('');
  const [feedbackNotice, setFeedbackNotice] = useState<string | null>(null);

  const { data: approvalItems, isLoading } = useQuery({
    queryKey: ['research', 'approvals', statusFilter],
    queryFn: async () => {
      const param = statusFilter !== 'all' ? `?status_filter=${statusFilter}` : '';
      const res = await apiClient.get<StandardResponse<ApprovalItemData[]>>(`/research/approvals${param}`);
      return res.data.data;
    },
  });

  const decisionMutation = useMutation({
    mutationFn: async ({
      approvalId,
      decision,
      editedContent,
      feedback,
    }: {
      approvalId: string;
      decision: string;
      editedContent?: string;
      feedback?: string;
    }) => {
      const res = await apiClient.post<StandardResponse<any>>(
        `/research/approvals/${approvalId}/decision`,
        {
          decision,
          edited_content: editedContent,
          feedback,
        }
      );
      return res.data.data;
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['research', 'approvals'] });
      setIsReviewModalOpen(false);
      setFeedbackNotice(`Decision submitted: ${data.message || 'Draft marked as Ready for Outreach.'}`);
      setTimeout(() => setFeedbackNotice(null), 4000);
    },
  });

  const sendOutreachMutation = useMutation({
    mutationFn: async (approvalId: string) => {
      const res = await apiClient.post<StandardResponse<any>>(
        `/research/approvals/${approvalId}/send`
      );
      return res.data;
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['research', 'approvals'] });
      setIsReviewModalOpen(false);
      setFeedbackNotice(data.message || 'Outreach email dispatched successfully via Microsoft Outlook!');
      setTimeout(() => setFeedbackNotice(null), 5000);
    },
    onError: (err: any) => {
      const errorMsg =
        err?.response?.data?.detail ||
        err?.response?.data?.message ||
        err?.message ||
        'Failed to dispatch email via Microsoft Outlook.';
      setFeedbackNotice(`Error: ${errorMsg}`);
      setTimeout(() => setFeedbackNotice(null), 7000);
    },
  });

  const deleteApprovalMutation = useMutation({
    mutationFn: async (approvalId: string) => {
      const res = await apiClient.delete<StandardResponse<any>>(
        `/research/approvals/${approvalId}`
      );
      return res.data;
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['research', 'approvals'] });
      setIsReviewModalOpen(false);
      setFeedbackNotice(data.message || 'Outreach draft deleted.');
      setTimeout(() => setFeedbackNotice(null), 4000);
    },
  });

  const handleOpenReview = (item: ApprovalItemData) => {
    setSelectedItem(item);
    setEditedBody(item.draft_body);
    setReviewerFeedback(item.review_feedback || '');
    setIsReviewModalOpen(true);
  };

  const filteredItems = (approvalItems || []).filter((item) =>
    item.company_name.toLowerCase().includes(search.toLowerCase()) ||
    item.contact_name.toLowerCase().includes(search.toLowerCase()) ||
    item.draft_body.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="space-y-5">
      {/* 1. Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between pb-3 border-b border-slate-200 gap-3">
        <div>
          <div className="flex items-center space-x-2.5">
            <h1 className="text-xl font-bold tracking-tight text-slate-900">Approval Center</h1>
            <span className="bg-indigo-50 text-indigo-700 border border-indigo-200/80 rounded-full px-2.5 py-0.5 text-[10px] font-semibold">
              Pipeline 2 Governance
            </span>
          </div>
          <p className="text-xs text-slate-500 mt-1">
            Review, edit, and approve personalized initial outreach drafts. Approved drafts transition to &ldquo;Ready for Outreach&rdquo;.
          </p>
        </div>

        <div className="flex items-center space-x-2 text-xs">
          <span className="text-slate-500 font-medium">
            Pending Human Review: <strong className="text-rose-600">
              {(approvalItems || []).filter((i) => i.raw_status === 'pending').length}
            </strong>
          </span>
        </div>
      </div>

      {/* Success / Error Notification */}
      {feedbackNotice && (
        <div
          className={`p-3 rounded-lg text-xs font-medium flex items-center space-x-2 border ${
            feedbackNotice.toLowerCase().startsWith('error')
              ? 'bg-rose-50 border-rose-200 text-rose-800'
              : 'bg-emerald-50 border-emerald-200 text-emerald-800'
          }`}
        >
          {feedbackNotice.toLowerCase().startsWith('error') ? (
            <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
          ) : (
            <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
          )}
          <span>{feedbackNotice}</span>
        </div>
      )}

      {/* 2. Search & Filters Bar */}
      <div className="p-3.5 bg-white rounded-xl border border-slate-200/90 shadow-2xs flex flex-col md:flex-row md:items-center justify-between gap-3 text-xs">
        <div className="relative flex-1 max-w-sm">
          <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-2.5" />
          <input
            type="text"
            placeholder="Search approvals by company or contact..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-9 pr-3.5 py-1.5 bg-slate-50 border border-slate-200 rounded-lg text-xs text-slate-800 placeholder:text-slate-400 focus:outline-none focus:ring-1 focus:ring-indigo-500"
          />
        </div>

        <div className="flex items-center space-x-2">
          <span className="text-slate-400 text-[11px]">Status:</span>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="px-2.5 py-1 bg-slate-50 border border-slate-200 rounded-lg text-[11px] font-medium text-slate-700"
          >
            <option value="all">All Approvals</option>
            <option value="pending">Pending Review</option>
            <option value="ready for outreach">Ready for Outreach</option>
            <option value="rejected">Rejected</option>
            <option value="revision_requested">Revision Requested</option>
          </select>
        </div>
      </div>

      {/* 3. Approvals Data Table */}
      {isLoading ? (
        <LoadingState message="Loading approval requests..." />
      ) : filteredItems.length === 0 ? (
        <EmptyState
          title="No approval drafts found"
          description="Outreach drafts submitted from Outreach Studio will appear here for human governance review."
          actionLabel="Refresh List"
          onAction={() => queryClient.invalidateQueries({ queryKey: ['research', 'approvals'] })}
        />
      ) : (
        <div className="bg-white rounded-xl border border-slate-200/90 shadow-2xs overflow-hidden text-xs">
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse min-w-[1050px]">
              <thead>
                <tr className="border-b border-slate-100 bg-slate-50/60 text-[10px] font-bold text-slate-400 uppercase tracking-wider">
                  <th className="py-3 px-4 w-48">COMPANY</th>
                  <th className="py-3 px-4 w-44">CONTACT</th>
                  <th className="py-3 px-4 min-w-[280px]">MESSAGE PREVIEW</th>
                  <th className="py-3 px-3 w-24">CHANNEL</th>
                  <th className="py-3 px-3 w-28">DEMO</th>
                  <th className="py-3 px-3 w-24 text-center">VERSION</th>
                  <th className="py-3 px-3 w-32">SUBMITTED</th>
                  <th className="py-3 px-3 w-36">STATUS</th>
                  <th className="py-3 px-4 w-28 text-right">ACTION</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {filteredItems.map((item) => {
                  const isPending = item.raw_status === 'pending';
                  const isApproved = item.status === 'Ready for Outreach';
                  const isSent = item.status === 'Sent';
                  return (
                    <tr
                      key={item.approval_id}
                      className="hover:bg-slate-50/70 transition-colors cursor-pointer"
                      onClick={() => handleOpenReview(item)}
                    >
                      {/* Company */}
                      <td className="py-3.5 px-4 align-middle font-bold text-slate-900 text-xs">
                        {item.company_name}
                      </td>

                      {/* Contact */}
                      <td className="py-3.5 px-4 align-middle">
                        <div className="font-semibold text-slate-900 text-xs">{item.contact_name}</div>
                        <div className="text-[11px] text-slate-500 truncate">{item.contact_title}</div>
                      </td>

                      {/* Message Preview */}
                      <td className="py-3.5 px-4 align-middle">
                        <p className="text-slate-700 text-xs leading-snug line-clamp-2">
                          {item.message_preview}
                        </p>
                      </td>

                      {/* Channel */}
                      <td className="py-3.5 px-3 align-middle uppercase text-[10px] font-bold text-slate-600">
                        {item.channel}
                      </td>

                      {/* Demo Status */}
                      <td className="py-3.5 px-3 align-middle">
                        <span className="bg-slate-100 text-slate-700 px-2 py-0.5 rounded text-[10px] font-medium">
                          {item.demo_status}
                        </span>
                      </td>

                      {/* Version */}
                      <td className="py-3.5 px-3 text-center align-middle font-mono text-[11px] text-slate-500">
                        v{item.draft_version}
                      </td>

                      {/* Submitted Date */}
                      <td className="py-3.5 px-3 align-middle text-slate-400 text-[11px]">
                        {item.submitted_date}
                      </td>

                      {/* Status */}
                      <td className="py-3.5 px-3 align-middle">
                        {isSent ? (
                          <span className="bg-emerald-100 text-emerald-800 border border-emerald-300 rounded-full px-2.5 py-0.5 text-[10px] font-bold flex items-center space-x-1 w-max">
                            <CheckCircle2 className="w-2.5 h-2.5 text-emerald-600" />
                            <span>Sent (Dispatched)</span>
                          </span>
                        ) : isApproved ? (
                          <span className="bg-emerald-50 text-emerald-700 border border-emerald-200 rounded-full px-2.5 py-0.5 text-[10px] font-semibold flex items-center space-x-1 w-max">
                            <CheckCircle2 className="w-2.5 h-2.5" />
                            <span>Ready for Outreach</span>
                          </span>
                        ) : isPending ? (
                          <span className="bg-rose-50 text-rose-700 border border-rose-200 rounded-full px-2.5 py-0.5 text-[10px] font-semibold flex items-center space-x-1 w-max">
                            <Clock className="w-2.5 h-2.5" />
                            <span>Pending Review</span>
                          </span>
                        ) : (
                          <span className="bg-slate-100 text-slate-700 rounded-full px-2.5 py-0.5 text-[10px] font-medium capitalize">
                            {item.status}
                          </span>
                        )}
                      </td>

                      {/* Action */}
                      <td className="py-3.5 px-4 align-middle text-right" onClick={(e) => e.stopPropagation()}>
                        <div className="flex items-center justify-end space-x-1.5">
                          {isApproved && (
                            <button
                              onClick={() => sendOutreachMutation.mutate(item.approval_id)}
                              disabled={sendOutreachMutation.isPending}
                              className="px-2.5 py-1 text-xs font-semibold text-emerald-700 bg-emerald-50 hover:bg-emerald-100 border border-emerald-200 rounded transition-colors flex items-center space-x-1 shadow-2xs"
                              title="Send outreach email via Microsoft Outlook"
                            >
                              <Send className="w-3 h-3" />
                              <span>Send</span>
                            </button>
                          )}
                          <button
                            onClick={() => handleOpenReview(item)}
                            className="px-2.5 py-1 text-xs font-semibold text-white bg-[#201D6E] hover:bg-[#1a1758] rounded transition-colors"
                          >
                            Review
                          </button>
                          <button
                            onClick={() => {
                              if (confirm(`Delete outreach approval for ${item.contact_name}?`)) {
                                deleteApprovalMutation.mutate(item.approval_id);
                              }
                            }}
                            disabled={deleteApprovalMutation.isPending}
                            className="p-1.5 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded transition-colors"
                            title="Delete draft approval"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
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
            <div>Showing {filteredItems.length} draft approvals</div>
            <div className="text-slate-400">Human Sign-Off Required for Cold Outreach</div>
          </div>
        </div>
      )}

      {/* 4. Full Governance Review Drawer / Modal */}
      {selectedItem && (
        <Modal
          isOpen={isReviewModalOpen}
          onClose={() => setIsReviewModalOpen(false)}
          title={`Review Outreach Draft: ${selectedItem.company_name}`}
        >
          <div className="space-y-4 text-xs">
            {/* Context Dossier Side-by-Side */}
            <div className="p-3 bg-slate-50 rounded-lg border border-slate-200/80 grid grid-cols-2 gap-3 text-slate-700">
              <div>
                <span className="text-[10px] text-slate-400 uppercase font-bold block">Recipient:</span>
                <div className="font-bold text-slate-900">{selectedItem.contact_name}</div>
                <div className="text-[11px] text-slate-500">{selectedItem.contact_title}</div>
                <div className="text-[11px] font-mono text-slate-500">{selectedItem.contact_email}</div>
              </div>

              <div>
                <span className="text-[10px] text-slate-400 uppercase font-bold block">Governance Status:</span>
                <div className="font-semibold text-indigo-700 capitalize mt-0.5">{selectedItem.status}</div>
                <div className="text-[11px] text-slate-500 mt-1">
                  Channel: <strong className="uppercase">{selectedItem.channel}</strong> &bull; Demo: {selectedItem.demo_status}
                </div>
              </div>
            </div>

            {/* Editable Draft Area */}
            <div className="space-y-1.5">
              <label className="font-semibold text-slate-800 block">
                Outreach Copy (Review or Edit before sign-off)
              </label>
              <textarea
                rows={7}
                value={editedBody}
                onChange={(e) => setEditedBody(e.target.value)}
                className="w-full p-3 bg-white border border-slate-200 rounded-lg text-xs text-slate-800 leading-relaxed font-sans focus:outline-none focus:ring-1 focus:ring-indigo-500"
              />
            </div>

            {/* Reviewer Feedback Notes */}
            <div className="space-y-1">
              <label className="font-semibold text-slate-700 block">Reviewer Feedback / Comments</label>
              <input
                type="text"
                placeholder="Optional feedback for author or revision notes..."
                value={reviewerFeedback}
                onChange={(e) => setReviewerFeedback(e.target.value)}
                className="w-full px-3 py-1.5 bg-white border border-slate-200 rounded-lg text-xs text-slate-800 focus:outline-none focus:ring-1 focus:ring-indigo-500"
              />
            </div>

            {/* Notice regarding dispatch */}
            {selectedItem.status === 'Sent' ? (
              <div className="p-2.5 bg-emerald-50 border border-emerald-200 rounded-lg text-[11px] text-emerald-900 flex items-start space-x-2">
                <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
                <div>
                  This outreach message has already been <strong>Dispatched / Sent</strong> via Microsoft Outlook.
                </div>
              </div>
            ) : selectedItem.status === 'Ready for Outreach' ? (
              <div className="p-2.5 bg-blue-50 border border-blue-200 rounded-lg text-[11px] text-blue-900 flex items-start space-x-2">
                <ShieldCheck className="w-4 h-4 text-blue-600 shrink-0 mt-0.5" />
                <div>
                  This draft is approved and <strong>Ready for Outreach</strong>. You can click <strong>&ldquo;Send Email Now&rdquo;</strong> to dispatch it through Microsoft Outlook, or revise the copy if needed.
                </div>
              </div>
            ) : (
              <div className="p-2.5 bg-amber-50 border border-amber-200 rounded-lg text-[11px] text-amber-900 flex items-start space-x-2">
                <ShieldCheck className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
                <div>
                  Approving this draft marks it as <strong>Ready for Outreach</strong>. It will be held for human compliance until explicit dispatch.
                </div>
              </div>
            )}

            {/* Action Buttons */}
            <div className="pt-3 border-t border-slate-100 flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center space-x-2">
                <button
                  onClick={() =>
                    decisionMutation.mutate({
                      approvalId: selectedItem.approval_id,
                      decision: 'rejected',
                      feedback: reviewerFeedback || 'Draft does not meet outreach standards',
                    })
                  }
                  disabled={decisionMutation.isPending || selectedItem.status === 'Sent'}
                  className="px-3 py-1.5 bg-rose-50 text-rose-700 hover:bg-rose-100 border border-rose-200 rounded-md font-semibold text-xs transition-colors disabled:opacity-50"
                >
                  Reject Draft
                </button>

                <button
                  onClick={() => {
                    if (confirm(`Delete outreach approval for ${selectedItem.contact_name}?`)) {
                      deleteApprovalMutation.mutate(selectedItem.approval_id);
                    }
                  }}
                  disabled={deleteApprovalMutation.isPending}
                  className="px-3 py-1.5 bg-slate-100 hover:bg-rose-50 hover:text-rose-700 text-slate-600 rounded-md font-semibold text-xs transition-colors flex items-center space-x-1"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                  <span>Delete</span>
                </button>
              </div>

              <div className="flex items-center space-x-2">
                <button
                  onClick={() =>
                    decisionMutation.mutate({
                      approvalId: selectedItem.approval_id,
                      decision: 'revision_requested',
                      feedback: reviewerFeedback || 'Revision requested on personalized hook',
                    })
                  }
                  disabled={decisionMutation.isPending || selectedItem.status === 'Sent'}
                  className="px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-md font-semibold text-xs transition-colors disabled:opacity-50"
                >
                  Request Revision
                </button>

                {selectedItem.status === 'Ready for Outreach' ? (
                  <button
                    onClick={() => sendOutreachMutation.mutate(selectedItem.approval_id)}
                    disabled={sendOutreachMutation.isPending}
                    className="px-4 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-md font-semibold text-xs shadow-2xs transition-colors flex items-center space-x-1.5"
                  >
                    <Send className="w-3.5 h-3.5" />
                    <span>{sendOutreachMutation.isPending ? 'Dispatching...' : 'Send Email Now (Dispatch Outlook)'}</span>
                  </button>
                ) : selectedItem.status !== 'Sent' ? (
                  <button
                    onClick={() =>
                      decisionMutation.mutate({
                        approvalId: selectedItem.approval_id,
                        decision: editedBody !== selectedItem.draft_body ? 'edited_approved' : 'approved',
                        editedContent: editedBody,
                        feedback: reviewerFeedback,
                      })
                    }
                    disabled={decisionMutation.isPending}
                    className="px-4 py-1.5 bg-[#201D6E] hover:bg-[#1a1758] text-white rounded-md font-semibold text-xs shadow-2xs transition-colors"
                  >
                    {decisionMutation.isPending ? 'Processing...' : 'Approve Draft (Ready for Outreach)'}
                  </button>
                ) : null}
              </div>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
};
