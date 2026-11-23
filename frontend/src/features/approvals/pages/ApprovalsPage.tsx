import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { PageHeader } from '@/components/layout/PageHeader';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { Modal } from '@/components/ui/Modal';
import { LoadingState, ErrorState, EmptyState } from '@/components/ui/FeedbackStates';
import { apiClient } from '@/lib/apiClient';
import { StandardResponse } from '@/types/api';
import { formatDate } from '@/lib/utils';
import {
  CheckSquare,
  ShieldCheck,
  AlertTriangle,
  FileText,
  ThumbsUp,
  ThumbsDown,
  Edit3,
  ExternalLink,
  Info,
} from 'lucide-react';

export interface ApprovalItem {
  id: string;
  organization_id: string;
  account_id: string;
  contact_id?: string;
  artifact_type: string;
  artifact_id: string;
  artifact_version: string;
  requested_action: string;
  draft_content: string;
  source_evidence: Record<string, any>;
  risk_flags: string[];
  status: string;
  reviewed_by_user_id?: string;
  review_feedback?: string;
  created_at: string;
  updated_at: string;
}

export const ApprovalsPage: React.FC = () => {
  const queryClient = useQueryClient();
  const [selectedItem, setSelectedItem] = useState<ApprovalItem | null>(null);
  const [editedContent, setEditedContent] = useState('');
  const [feedback, setFeedback] = useState('');
  const [activeTab, setActiveTab] = useState<'ALL' | 'OUTREACH' | 'PROPOSAL' | 'SECURITY'>('ALL');

  const { data: items = [], isLoading, isError, error, refetch } = useQuery({
    queryKey: ['approvals', 'pending'],
    queryFn: async () => {
      const res = await apiClient.get<StandardResponse<ApprovalItem[]>>('/approvals');
      return res.data.data;
    },
  });

  const decisionMutation = useMutation({
    mutationFn: async ({
      id,
      decision,
      edited,
      fb,
    }: {
      id: string;
      decision: string;
      edited?: string;
      fb?: string;
    }) => {
      const res = await apiClient.post<StandardResponse<ApprovalItem>>(
        `/approvals/${id}/decision`,
        {
          decision,
          edited_content: edited,
          feedback: fb,
        }
      );
      return res.data.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['approvals'] });
      setSelectedItem(null);
    },
  });

  const handleOpenReview = (item: ApprovalItem) => {
    setSelectedItem(item);
    setEditedContent(item.draft_content || '');
    setFeedback('');
  };

  const handleDecision = async (decision: string) => {
    if (!selectedItem) return;
    await decisionMutation.mutateAsync({
      id: selectedItem.id,
      decision,
      edited: decision === 'edited_approved' ? editedContent : undefined,
      fb: feedback,
    });
  };

  const filteredItems = items.filter((item) => {
    if (activeTab === 'ALL') return true;
    if (activeTab === 'OUTREACH') return item.artifact_type.includes('OUTREACH');
    if (activeTab === 'PROPOSAL') return item.artifact_type.includes('PROPOSAL');
    if (activeTab === 'SECURITY') return item.artifact_type.includes('SECURITY');
    return true;
  });

  return (
    <div className="space-y-6">
      <PageHeader
        title="Human Approval Center"
        description="All external emails, proposals, and security answers require authorized verification before dispatch."
      />

      {/* Tabs */}
      <div className="flex space-x-2 border-b border-slate-200 dark:border-slate-800 pb-2">
        {(['ALL', 'OUTREACH', 'PROPOSAL', 'SECURITY'] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`px-3.5 py-1.5 text-xs font-semibold rounded-lg transition-colors ${
              activeTab === tab
                ? 'bg-brand-600 text-white'
                : 'text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800'
            }`}
          >
            {tab === 'ALL' ? 'All Pending Items' : `${tab} Items`}
          </button>
        ))}
      </div>

      {isLoading ? (
        <LoadingState message="Fetching pending approvals..." />
      ) : isError ? (
        <ErrorState
          message={(error as Error)?.message || 'Failed to load approvals.'}
          onRetry={() => refetch()}
        />
      ) : filteredItems.length === 0 ? (
        <EmptyState
          title="Approval queue is clear"
          description="There are currently no drafts or artifacts waiting for human verification. Autonomous agent tasks are up to date."
        />
      ) : (
        <div className="grid grid-cols-1 gap-4">
          {filteredItems.map((item) => (
            <div
              key={item.id}
              className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 p-5 shadow-xs hover:border-brand-400 dark:hover:border-brand-600 transition-all space-y-4"
            >
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                <div className="flex items-center space-x-3">
                  <span className="w-8 h-8 rounded-lg bg-amber-50 dark:bg-amber-950/40 text-amber-600 flex items-center justify-center font-bold">
                    <CheckSquare className="w-4 h-4" />
                  </span>
                  <div>
                    <h4 className="text-sm font-bold text-slate-900 dark:text-slate-100">
                      {item.requested_action.replace(/_/g, ' ')}
                    </h4>
                    <p className="text-xs text-slate-500 font-mono">
                      Type: {item.artifact_type} | Account ID: {item.account_id}
                    </p>
                  </div>
                </div>

                <div className="flex items-center space-x-2">
                  <Badge variant={item.risk_flags.length > 0 ? 'warning' : 'info'}>
                    {item.risk_flags.length > 0
                      ? `${item.risk_flags.length} Risk Flag(s)`
                      : 'Low Risk'}
                  </Badge>
                  <Button size="sm" onClick={() => handleOpenReview(item)}>
                    Review & Decide
                  </Button>
                </div>
              </div>

              {/* Preview Content */}
              <div className="bg-slate-50 dark:bg-slate-950 p-3.5 rounded-lg border border-slate-200/80 dark:border-slate-800 font-mono text-xs text-slate-700 dark:text-slate-300 line-clamp-3">
                {item.draft_content || '(Empty content preview)'}
              </div>

              {/* Risk Flags summary */}
              {item.risk_flags.length > 0 && (
                <div className="flex flex-wrap gap-2 text-[11px] text-amber-700 dark:text-amber-300">
                  {item.risk_flags.map((flag, idx) => (
                    <span
                      key={idx}
                      className="inline-flex items-center space-x-1 px-2 py-0.5 rounded-md bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800"
                    >
                      <AlertTriangle className="w-3 h-3 text-amber-500" />
                      <span>{flag}</span>
                    </span>
                  ))}
                </div>
              )}

              <div className="text-[11px] text-slate-400 flex items-center justify-between pt-1">
                <span>Requested on {formatDate(item.created_at)}</span>
                <span className="font-semibold text-brand-600">Awaiting Human Approval</span>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Review & Decide Modal */}
      <Modal
        isOpen={Boolean(selectedItem)}
        onClose={() => setSelectedItem(null)}
        title={`Review Artifact: ${selectedItem?.requested_action || ''}`}
        maxWidth="2xl"
      >
        {selectedItem && (
          <div className="space-y-5">
            {/* Metadata & Risk Highlights */}
            <div className="p-3.5 bg-slate-50 dark:bg-slate-900 rounded-lg border border-slate-200 dark:border-slate-800 flex flex-wrap gap-4 text-xs">
              <div>
                <span className="text-slate-400 block mb-0.5">Artifact Type</span>
                <span className="font-semibold text-slate-800 dark:text-slate-200">
                  {selectedItem.artifact_type}
                </span>
              </div>
              <div>
                <span className="text-slate-400 block mb-0.5">Version</span>
                <span className="font-mono text-slate-800 dark:text-slate-200">
                  {selectedItem.artifact_version}
                </span>
              </div>
              <div>
                <span className="text-slate-400 block mb-0.5">Risk Assessment</span>
                <span className="font-semibold text-amber-600">
                  {selectedItem.risk_flags.length > 0
                    ? `${selectedItem.risk_flags.length} Attention Flags`
                    : 'Standard Clearance'}
                </span>
              </div>
            </div>

            {/* Editable Content */}
            <div>
              <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 uppercase tracking-wider mb-1.5">
                Draft Content (Inspect & Edit)
              </label>
              <textarea
                rows={8}
                value={editedContent}
                onChange={(e) => setEditedContent(e.target.value)}
                className="w-full p-3 font-mono text-xs bg-slate-50 dark:bg-slate-950 border border-slate-300 dark:border-slate-700 rounded-lg focus:ring-2 focus:ring-brand-500 focus:outline-hidden text-slate-900 dark:text-slate-100"
              />
            </div>

            {/* Source Evidence */}
            {selectedItem.source_evidence &&
              Object.keys(selectedItem.source_evidence).length > 0 && (
                <div>
                  <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 uppercase tracking-wider mb-1.5 flex items-center space-x-1">
                    <Info className="w-3.5 h-3.5 text-blue-500" />
                    <span>Sourced Evidence References</span>
                  </label>
                  <pre className="p-3 bg-slate-100 dark:bg-slate-950 rounded-lg text-[11px] font-mono text-slate-600 dark:text-slate-300 overflow-x-auto max-h-32">
                    {JSON.stringify(selectedItem.source_evidence, null, 2)}
                  </pre>
                </div>
              )}

            {/* Reviewer Feedback Notes */}
            <div>
              <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 uppercase tracking-wider mb-1.5">
                Feedback / Decision Notes (Optional)
              </label>
              <input
                type="text"
                placeholder="e.g. Tone adjusted for C-level executive; facts verified against CRM."
                value={feedback}
                onChange={(e) => setFeedback(e.target.value)}
                className="w-full px-3 py-2 text-xs bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg focus:ring-2 focus:ring-brand-500 focus:outline-hidden"
              />
            </div>

            {/* Action Buttons */}
            <div className="flex flex-wrap items-center justify-between gap-3 pt-4 border-t border-slate-200 dark:border-slate-800">
              <Button
                variant="danger"
                size="sm"
                onClick={() => handleDecision('rejected')}
                disabled={decisionMutation.isPending}
              >
                <ThumbsDown className="w-4 h-4 mr-1.5" />
                Reject Draft
              </Button>

              <div className="flex items-center space-x-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handleDecision('edited_approved')}
                  disabled={decisionMutation.isPending}
                >
                  <Edit3 className="w-4 h-4 mr-1.5 text-blue-600" />
                  Save Edits & Approve
                </Button>
                <Button
                  variant="primary"
                  size="sm"
                  onClick={() => handleDecision('approved')}
                  disabled={decisionMutation.isPending}
                >
                  <ThumbsUp className="w-4 h-4 mr-1.5" />
                  Approve Draft
                </Button>
              </div>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
};
