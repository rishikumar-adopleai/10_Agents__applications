import React, { useState, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Layers,
  Send,
  Building2,
  Users,
  Sparkles,
  RotateCw,
  CheckCircle2,
  AlertCircle,
  ExternalLink,
  Mail,
  Search,
  Filter,
  Plus,
  ArrowLeft,
  ChevronRight,
  Eye,
  Trash2,
  Check,
  Clock,
  MessageSquare,
  ThumbsUp,
  ThumbsDown,
  HelpCircle,
  Play,
  CheckSquare,
  Square,
  RefreshCw,
  X,
  ShieldCheck,
  FileText,
} from 'lucide-react';
import { apiClient } from '@/lib/apiClient';
import { StandardResponse } from '@/types/api';
import { LoadingState } from '@/components/ui/FeedbackStates';
import { Modal } from '@/components/ui/Modal';

export interface CampaignItem {
  id: string;
  name: string;
  channel: string;
  status: string;
  product_slug?: string;
  product_name?: string;
  demo_url?: string;
  subject?: string;
  template_body?: string;
  created_at: string;
  target_companies_count: number;
  target_contacts_count: number;
  emails_sent_count: number;
  pending_count: number;
  failed_count: number;
  replies_count: number;
  positive_replies_count: number;
  positive_rate: number;
}

export interface CampaignRecipientItem {
  id: string;
  account_id: string;
  contact_id: string;
  company_name: string;
  contact_name: string;
  contact_email: string;
  job_title?: string;
  personalized_subject: string;
  personalized_body: string;
  status: string; // pending, approved, sent, failed, suppressed
  sent_at?: string;
  outlook_message_id?: string;
  error_message?: string;
  reply_status: string; // no_reply, received, positive, negative, neutral
  reply_snippet?: string;
  reply_received_at?: string;
}

export interface CampaignDetailData extends CampaignItem {
  recipients: CampaignRecipientItem[];
}

interface CompanyItem {
  account_id: string;
  company_name: string;
  domain: string;
  industry: string;
}

interface ContactItem {
  contact_id: string;
  account_id: string;
  company_name: string;
  company_domain: string;
  full_name: string;
  job_title: string;
  email: string;
  aligned_pain_point?: string;
}

interface MarketplaceProduct {
  product_id: string;
  name: string;
  slug: string;
  product_url: string;
  category: string;
  overview: string;
  key_features: string[];
  demo_video_url: string;
  target_pain_points: string[];
  target_roles: string[];
}

interface OutreachCampaignSectionProps {
  companies?: CompanyItem[];
  allContacts?: ContactItem[];
  marketplaceProducts?: MarketplaceProduct[];
}

export const OutreachCampaignSection: React.FC<OutreachCampaignSectionProps> = ({
  companies = [],
  allContacts = [],
  marketplaceProducts = [],
}) => {
  const queryClient = useQueryClient();

  // Navigation & Selection State
  const [selectedCampaignId, setSelectedCampaignId] = useState<string | null>(null);
  const [campaignTab, setCampaignTab] = useState<'roster' | 'replies' | 'template'>('roster');
  const [searchFilter, setSearchFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');

  // Modals State
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [isPreviewModalOpen, setIsPreviewModalOpen] = useState(false);
  const [previewRecipient, setPreviewRecipient] = useState<CampaignRecipientItem | null>(null);
  const [isReplyModalOpen, setIsReplyModalOpen] = useState(false);
  const [replyRecipient, setReplyRecipient] = useState<CampaignRecipientItem | null>(null);
  const [replySnippetInput, setReplySnippetInput] = useState('');
  const [replySentimentInput, setReplySentimentInput] = useState<'positive' | 'neutral' | 'negative'>('positive');

  // Notification Toast
  const [toast, setToast] = useState<{ text: string; type: 'success' | 'error' | 'info' } | null>(null);
  const showToast = (text: string, type: 'success' | 'error' | 'info' = 'info') => {
    setToast({ text, type });
    setTimeout(() => setToast(null), 5000);
  };

  // 1. Fetch all campaigns
  const {
    data: campaigns = [],
    isLoading: campaignsLoading,
    refetch: refetchCampaigns,
  } = useQuery({
    queryKey: ['research', 'campaigns'],
    queryFn: async () => {
      const res = await apiClient.get<StandardResponse<CampaignItem[]>>('/research/campaigns');
      return res.data.data;
    },
  });

  // 2. Fetch active campaign details
  const {
    data: activeCampaign,
    isLoading: activeCampaignLoading,
    refetch: refetchActiveCampaign,
  } = useQuery({
    queryKey: ['research', 'campaigns', selectedCampaignId],
    queryFn: async () => {
      if (!selectedCampaignId) return null;
      const res = await apiClient.get<StandardResponse<CampaignDetailData>>(`/research/campaigns/${selectedCampaignId}`);
      return res.data.data;
    },
    enabled: !!selectedCampaignId,
  });

  // ---------------------------------------------------------------------------
  // Create Campaign Form State
  // ---------------------------------------------------------------------------
  const [formCampaignName, setFormCampaignName] = useState('');
  const [formProductSlug, setFormProductSlug] = useState('');
  const [formSelectedCompanyIds, setFormSelectedCompanyIds] = useState<string[]>([]);
  const [formSelectedContactIds, setFormSelectedContactIds] = useState<string[]>([]);
  const [formSubjectTemplate, setFormSubjectTemplate] = useState('Streamlining operational workflows for {{company_name}}');
  const [formBodyTemplate, setFormBodyTemplate] = useState(
    'Hi {{first_name}},\n\n' +
    'Noticed {{company_name}} is navigating {{pain_point}}.\n\n' +
    'Our solution, {{product_name}}, is designed to address this: {{product_overview}}.\n\n' +
    'You can explore an interactive walkthrough and demo video here: {{demo_link}}\n\n' +
    'Would you be open to a 10-minute briefing next week?\n\n' +
    'Best regards,\nAdople Solutions Team'
  );
  const [formPreviewContactId, setFormPreviewContactId] = useState<string>('');

  // Set default product when marketplaceProducts loaded
  React.useEffect(() => {
    if (marketplaceProducts.length > 0 && !formProductSlug) {
      setFormProductSlug(marketplaceProducts[0].slug);
    }
  }, [marketplaceProducts, formProductSlug]);

  // Selected product object for creator
  const formSelectedProduct = useMemo(() => {
    return marketplaceProducts.find((p) => p.slug === formProductSlug) || marketplaceProducts[0] || null;
  }, [marketplaceProducts, formProductSlug]);

  // Filter contacts available for the selected companies in form
  const formAvailableContacts = useMemo(() => {
    if (formSelectedCompanyIds.length === 0) return allContacts;
    return allContacts.filter((c) => formSelectedCompanyIds.includes(c.account_id));
  }, [allContacts, formSelectedCompanyIds]);

  // Handle Select All Companies
  const toggleAllCompanies = () => {
    if (formSelectedCompanyIds.length === companies.length) {
      setFormSelectedCompanyIds([]);
      setFormSelectedContactIds([]);
    } else {
      const allCompIds = companies.map((c) => c.account_id);
      setFormSelectedCompanyIds(allCompIds);
      const allContIds = allContacts.map((c) => c.contact_id);
      setFormSelectedContactIds(allContIds);
    }
  };

  // Handle Individual Company Toggle
  const toggleCompany = (accId: string) => {
    setFormSelectedCompanyIds((prev) => {
      const next = prev.includes(accId) ? prev.filter((id) => id !== accId) : [...prev, accId];
      // Automatically update contact selections to match available
      const matchingContacts = allContacts.filter((c) => next.includes(c.account_id)).map((c) => c.contact_id);
      setFormSelectedContactIds(matchingContacts);
      return next;
    });
  };

  // Handle Select All Contacts
  const toggleAllContacts = () => {
    if (formSelectedContactIds.length === formAvailableContacts.length) {
      setFormSelectedContactIds([]);
    } else {
      setFormSelectedContactIds(formAvailableContacts.map((c) => c.contact_id));
    }
  };

  // Handle Individual Contact Toggle
  const toggleContact = (cid: string) => {
    setFormSelectedContactIds((prev) =>
      prev.includes(cid) ? prev.filter((id) => id !== cid) : [...prev, cid]
    );
  };

  // Insert merge tag into template
  const insertMergeTag = (tag: string, field: 'subject' | 'body') => {
    if (field === 'subject') {
      setFormSubjectTemplate((prev) => prev + ` {{${tag}}}`);
    } else {
      setFormBodyTemplate((prev) => prev + ` {{${tag}}}`);
    }
  };

  // Live preview resolved draft in form
  const formPreviewContact = useMemo(() => {
    if (!formPreviewContactId && formSelectedContactIds.length > 0) {
      return allContacts.find((c) => c.contact_id === formSelectedContactIds[0]) || null;
    }
    return allContacts.find((c) => c.contact_id === formPreviewContactId) || null;
  }, [allContacts, formPreviewContactId, formSelectedContactIds]);

  const resolvedFormPreview = useMemo(() => {
    if (!formPreviewContact || !formSelectedProduct) return null;
    const firstName = formPreviewContact.full_name.split(' ')[0] || 'there';
    const company = companies.find((c) => c.account_id === formPreviewContact.account_id);
    const companyName = company?.company_name || formPreviewContact.company_name || 'Enterprise Prospect';
    const painPoint = formPreviewContact.aligned_pain_point || 'manual operational bottlenecks and workflow scaling';

    const tags: Record<string, string> = {
      first_name: firstName,
      contact_name: formPreviewContact.full_name,
      company_name: companyName,
      pain_point: painPoint,
      product_name: formSelectedProduct.name,
      product_overview: formSelectedProduct.overview,
      demo_link: formSelectedProduct.demo_video_url || 'https://marketplace.adople.ai/',
    };

    let subj = formSubjectTemplate;
    let bdy = formBodyTemplate;
    Object.entries(tags).forEach(([k, v]) => {
      subj = subj.replace(new RegExp(`{{${k}}}`, 'g'), v);
      bdy = bdy.replace(new RegExp(`{{${k}}}`, 'g'), v);
    });

    return { subject: subj, body: bdy };
  }, [formPreviewContact, formSelectedProduct, formSubjectTemplate, formBodyTemplate, companies]);

  // ---------------------------------------------------------------------------
  // Mutations
  // ---------------------------------------------------------------------------
  // 1. Create Campaign Mutation
  const createCampaignMutation = useMutation({
    mutationFn: async () => {
      if (!formCampaignName.trim()) {
        throw new Error('Please enter a campaign name');
      }
      if (formSelectedContactIds.length === 0) {
        throw new Error('Please select at least one contact for the campaign');
      }
      const res = await apiClient.post<StandardResponse<any>>('/research/campaigns', {
        name: formCampaignName.trim(),
        product_slug: formProductSlug,
        subject_template: formSubjectTemplate,
        body_template: formBodyTemplate,
        contact_ids: formSelectedContactIds,
        company_ids: formSelectedCompanyIds,
      });
      return res.data.data;
    },
    onSuccess: (data) => {
      showToast(`Campaign '${data.name}' created successfully!`, 'success');
      setIsCreateModalOpen(false);
      queryClient.invalidateQueries({ queryKey: ['research', 'campaigns'] });
      setSelectedCampaignId(data.id);
    },
    onError: (err: any) => {
      showToast(err?.response?.data?.detail || err?.message || 'Failed to create campaign', 'error');
    },
  });

  // 2. Dispatch Campaign Emails Mutation (Live Outlook or Simulated)
  const dispatchMutation = useMutation({
    mutationFn: async ({ campaignId, simulate }: { campaignId: string; simulate: boolean }) => {
      const res = await apiClient.post<StandardResponse<any>>(`/research/campaigns/${campaignId}/dispatch`, {
        simulate,
      });
      return res.data;
    },
    onSuccess: (res) => {
      showToast(res.message || 'Campaign dispatch completed!', 'success');
      queryClient.invalidateQueries({ queryKey: ['research', 'campaigns'] });
      if (selectedCampaignId) {
        queryClient.invalidateQueries({ queryKey: ['research', 'campaigns', selectedCampaignId] });
      }
    },
    onError: (err: any) => {
      showToast(err?.response?.data?.detail || 'Dispatch failed', 'error');
    },
  });

  // 3. Record Reply Mutation
  const recordReplyMutation = useMutation({
    mutationFn: async ({
      campaignId,
      recipientId,
      sentiment,
      replySnippet,
    }: {
      campaignId: string;
      recipientId: string;
      sentiment: string;
      replySnippet: string;
    }) => {
      const res = await apiClient.post<StandardResponse<any>>(
        `/research/campaigns/${campaignId}/recipients/${recipientId}/reply`,
        { sentiment, reply_snippet: replySnippet }
      );
      return res.data;
    },
    onSuccess: (res) => {
      showToast(res.message || 'Reply recorded successfully', 'success');
      setIsReplyModalOpen(false);
      setReplyRecipient(null);
      setReplySnippetInput('');
      queryClient.invalidateQueries({ queryKey: ['research', 'campaigns'] });
      if (selectedCampaignId) {
        queryClient.invalidateQueries({ queryKey: ['research', 'campaigns', selectedCampaignId] });
      }
    },
    onError: (err: any) => {
      showToast(err?.response?.data?.detail || 'Failed to record reply', 'error');
    },
  });

  // 4. Delete Campaign Mutation
  const deleteCampaignMutation = useMutation({
    mutationFn: async (campaignId: string) => {
      const res = await apiClient.delete<StandardResponse<any>>(`/research/campaigns/${campaignId}`);
      return res.data;
    },
    onSuccess: () => {
      showToast('Campaign deleted successfully', 'info');
      setSelectedCampaignId(null);
      queryClient.invalidateQueries({ queryKey: ['research', 'campaigns'] });
    },
  });

  // Filtered recipients in active campaign
  const filteredRecipients = useMemo(() => {
    if (!activeCampaign?.recipients) return [];
    return activeCampaign.recipients.filter((r) => {
      const matchSearch =
        searchFilter === '' ||
        r.contact_name.toLowerCase().includes(searchFilter.toLowerCase()) ||
        r.company_name.toLowerCase().includes(searchFilter.toLowerCase()) ||
        r.contact_email.toLowerCase().includes(searchFilter.toLowerCase());

      const matchStatus =
        statusFilter === 'all' ||
        (statusFilter === 'sent' && r.status === 'sent') ||
        (statusFilter === 'pending' && r.status === 'pending') ||
        (statusFilter === 'replied' && ['positive', 'neutral', 'negative'].includes(r.reply_status)) ||
        (statusFilter === 'positive' && r.reply_status === 'positive');

      return matchSearch && matchStatus;
    });
  }, [activeCampaign, searchFilter, statusFilter]);

  // Aggregated Totals Across All Campaigns
  const aggregatedStats = useMemo(() => {
    const totalCampaigns = campaigns.length;
    const totalContacts = campaigns.reduce((acc, c) => acc + (c.target_contacts_count || 0), 0);
    const totalSent = campaigns.reduce((acc, c) => acc + (c.emails_sent_count || 0), 0);
    const totalReplies = campaigns.reduce((acc, c) => acc + (c.replies_count || 0), 0);
    const totalPosReplies = campaigns.reduce((acc, c) => acc + (c.positive_replies_count || 0), 0);
    const totalFailed = campaigns.reduce((acc, c) => acc + (c.failed_count || 0), 0);
    const avgPosRate = totalReplies > 0 ? Math.round((totalPosReplies / totalReplies) * 100) : 0;

    return { totalCampaigns, totalContacts, totalSent, totalReplies, totalPosReplies, totalFailed, avgPosRate };
  }, [campaigns]);

  // Open Create Modal & reset form
  const handleOpenCreateModal = () => {
    setFormCampaignName(`Enterprise Campaign - ${new Date().toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}`);
    const allCompIds = companies.map((c) => c.account_id);
    setFormSelectedCompanyIds(allCompIds);
    const allContIds = allContacts.map((c) => c.contact_id);
    setFormSelectedContactIds(allContIds);
    if (allContIds.length > 0) {
      setFormPreviewContactId(allContIds[0]);
    }
    setIsCreateModalOpen(true);
  };

  return (
    <div className="space-y-6">
      {/* Toast Alert */}
      {toast && (
        <div
          className={`fixed top-4 right-4 z-50 flex items-center space-x-2 px-4 py-2.5 rounded-lg text-xs font-semibold shadow-lg transition-all border ${toast.type === 'success'
            ? 'bg-emerald-50 text-emerald-800 border-emerald-200'
            : toast.type === 'error'
              ? 'bg-rose-50 text-rose-800 border-rose-200'
              : 'bg-indigo-50 text-indigo-800 border-indigo-200'
            }`}
        >
          {toast.type === 'success' ? <CheckCircle2 className="w-4 h-4 text-emerald-600" /> : <AlertCircle className="w-4 h-4" />}
          <span>{toast.text}</span>
          <button onClick={() => setToast(null)} className="ml-2 hover:opacity-75">
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      )}

      {/* 1. Header & Actions Bar */}
      <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center space-x-2.5">
            <div className="p-2 bg-indigo-50 text-[#201D6E] rounded-lg">
              <Layers className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-slate-900 tracking-tight">Outreach Campaign Studio</h2>
              <p className="text-xs text-slate-500 mt-0.5">
                Multi-company campaign management, product solution templates, live Outlook dispatch, and inbound reply monitoring.
              </p>
            </div>
          </div>
        </div>

        <div className="flex items-center space-x-2.5">
          <button
            onClick={() => {
              refetchCampaigns();
              if (selectedCampaignId) refetchActiveCampaign();
            }}
            className="px-3 py-1.5 text-xs font-semibold text-slate-700 bg-slate-50 hover:bg-slate-100 border border-slate-200 rounded-lg transition-colors flex items-center space-x-1.5"
            title="Refresh Campaign Data"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            <span>Refresh</span>
          </button>
          <button
            onClick={handleOpenCreateModal}
            className="px-3.5 py-1.5 text-xs font-semibold text-white bg-[#201D6E] hover:bg-[#191656] rounded-lg shadow-2xs transition-colors flex items-center space-x-1.5"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>Create New Campaign</span>
          </button>
        </div>
      </div>

      {/* 2. Global Campaign Performance KPIs */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        <div className="bg-white rounded-xl border border-slate-200/80 p-3.5 shadow-2xs">
          <div className="text-[11px] font-medium text-slate-500 flex items-center justify-between">
            <span>Total Campaigns</span>
            <Layers className="w-3.5 h-3.5 text-indigo-500" />
          </div>
          <div className="text-xl font-bold text-slate-900 mt-1">{aggregatedStats.totalCampaigns}</div>
          <div className="text-[10px] text-slate-400 mt-0.5">Configured pipelines</div>
        </div>

        <div className="bg-white rounded-xl border border-slate-200/80 p-3.5 shadow-2xs">
          <div className="text-[11px] font-medium text-slate-500 flex items-center justify-between">
            <span>Target Contacts</span>
            <Users className="w-3.5 h-3.5 text-blue-500" />
          </div>
          <div className="text-xl font-bold text-slate-900 mt-1">{aggregatedStats.totalContacts}</div>
          <div className="text-[10px] text-slate-400 mt-0.5">Across target companies</div>
        </div>

        <div className="bg-white rounded-xl border border-slate-200/80 p-3.5 shadow-2xs">
          <div className="text-[11px] font-medium text-slate-500 flex items-center justify-between">
            <span>Emails Sent</span>
            <Send className="w-3.5 h-3.5 text-emerald-500" />
          </div>
          <div className="text-xl font-bold text-emerald-700 mt-1">{aggregatedStats.totalSent}</div>
          <div className="text-[10px] text-emerald-600 mt-0.5">Via Microsoft Outlook</div>
        </div>

        <div className="bg-white rounded-xl border border-slate-200/80 p-3.5 shadow-2xs">
          <div className="text-[11px] font-medium text-slate-500 flex items-center justify-between">
            <span>Replies Received</span>
            <MessageSquare className="w-3.5 h-3.5 text-purple-500" />
          </div>
          <div className="text-xl font-bold text-purple-700 mt-1">{aggregatedStats.totalReplies}</div>
          <div className="text-[10px] text-purple-600 mt-0.5">Inbound prospect replies</div>
        </div>

        <div className="bg-white rounded-xl border border-slate-200/80 p-3.5 shadow-2xs">
          <div className="text-[11px] font-medium text-slate-500 flex items-center justify-between">
            <span>Positive Sentiment</span>
            <ThumbsUp className="w-3.5 h-3.5 text-emerald-500" />
          </div>
          <div className="text-xl font-bold text-slate-900 mt-1">{aggregatedStats.avgPosRate}%</div>
          <div className="text-[10px] text-emerald-600 mt-0.5">{aggregatedStats.totalPosReplies} positive leads</div>
        </div>

        <div className="bg-white rounded-xl border border-slate-200/80 p-3.5 shadow-2xs">
          <div className="text-[11px] font-medium text-slate-500 flex items-center justify-between">
            <span>Failed / Bounced</span>
            <AlertCircle className="w-3.5 h-3.5 text-rose-500" />
          </div>
          <div className="text-xl font-bold text-rose-600 mt-1">{aggregatedStats.totalFailed}</div>
          <div className="text-[10px] text-slate-400 mt-0.5">Suppressed or invalid</div>
        </div>
      </div>

      {/* 3. Main Body: Campaign List vs Selected Campaign Detail */}
      {!selectedCampaignId ? (
        /* View A: Campaigns Roster Table */
        <div className="bg-white rounded-xl border border-slate-200 shadow-2xs overflow-hidden">
          <div className="p-4 border-b border-slate-200 flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-slate-50/50">
            <div>
              <h3 className="text-sm font-bold text-slate-900">Configured Outreach Campaigns</h3>
              <p className="text-xs text-slate-500 mt-0.5">
                Select a campaign to review personalized contact drafts, trigger Outlook dispatches, or track incoming replies.
              </p>
            </div>
            <div className="text-xs text-slate-500 font-medium">
              Showing {campaigns.length} Campaign{campaigns.length !== 1 ? 's' : ''}
            </div>
          </div>

          {campaignsLoading ? (
            <div className="py-12">
              <LoadingState message="Loading outreach campaigns..." />
            </div>
          ) : campaigns.length === 0 ? (
            <div className="py-16 text-center px-4">
              <div className="w-12 h-12 rounded-full bg-indigo-50 text-[#201D6E] flex items-center justify-center mx-auto mb-3">
                <Layers className="w-6 h-6" />
              </div>
              <h4 className="text-sm font-bold text-slate-900">No Outreach Campaigns Yet</h4>
              <p className="text-xs text-slate-500 max-w-md mx-auto mt-1 mb-4">
                Launch a campaign across multiple companies and contacts with a solution template from marketplace.adople.ai.
              </p>
              <button
                onClick={handleOpenCreateModal}
                className="px-4 py-2 text-xs font-semibold text-white bg-[#201D6E] hover:bg-[#1a1758] rounded-lg shadow-xs transition-colors inline-flex items-center space-x-1.5"
              >
                <Plus className="w-4 h-4" />
                <span>Create Your First Campaign</span>
              </button>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="bg-slate-50/80 border-b border-slate-200 text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
                    <th className="py-3 px-4">Campaign Name & Product</th>
                    <th className="py-3 px-4">Status</th>
                    <th className="py-3 px-4 text-center">Companies</th>
                    <th className="py-3 px-4 text-center">Contacts</th>
                    <th className="py-3 px-4 text-center">Sent</th>
                    <th className="py-3 px-4 text-center">Replies</th>
                    <th className="py-3 px-4 text-center">Positive Rate</th>
                    <th className="py-3 px-4 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 text-xs">
                  {campaigns.map((camp) => (
                    <tr
                      key={camp.id}
                      onClick={() => setSelectedCampaignId(camp.id)}
                      className="hover:bg-indigo-50/40 transition-colors cursor-pointer group"
                    >
                      <td className="py-3.5 px-4 align-middle">
                        <div className="font-bold text-slate-900 group-hover:text-[#201D6E] transition-colors">
                          {camp.name}
                        </div>
                        <div className="flex items-center space-x-1.5 mt-1">
                          <span className="bg-indigo-50 text-indigo-700 border border-indigo-200/60 rounded px-1.5 py-0.2 text-[10px] font-semibold flex items-center space-x-1">
                            <Sparkles className="w-2.5 h-2.5" />
                            <span>{camp.product_name || 'Marketplace Solution'}</span>
                          </span>
                          <span className="text-[10px] text-slate-400">Created {new Date(camp.created_at).toLocaleDateString()}</span>
                        </div>
                      </td>

                      <td className="py-3.5 px-4 align-middle">
                        <span
                          className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold ${camp.status === 'active'
                            ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                            : camp.status === 'completed'
                              ? 'bg-blue-50 text-blue-700 border border-blue-200'
                              : camp.status === 'failed'
                                ? 'bg-rose-50 text-rose-700 border border-rose-200'
                                : 'bg-amber-50 text-amber-700 border border-amber-200'
                            }`}
                        >
                          {camp.status === 'draft' ? 'Review & Draft' : camp.status.toUpperCase()}
                        </span>
                      </td>

                      <td className="py-3.5 px-4 align-middle text-center font-semibold text-slate-700">
                        {camp.target_companies_count}
                      </td>

                      <td className="py-3.5 px-4 align-middle text-center font-semibold text-slate-700">
                        {camp.target_contacts_count}
                      </td>

                      <td className="py-3.5 px-4 align-middle text-center">
                        <span className="font-bold text-emerald-700">{camp.emails_sent_count}</span>
                        <span className="text-[10px] text-slate-400">/{camp.target_contacts_count}</span>
                      </td>

                      <td className="py-3.5 px-4 align-middle text-center font-bold text-purple-700">
                        {camp.replies_count}
                      </td>

                      <td className="py-3.5 px-4 align-middle text-center">
                        {camp.replies_count > 0 ? (
                          <span className="inline-flex items-center space-x-1 bg-emerald-50 text-emerald-700 px-2 py-0.5 rounded text-[11px] font-bold">
                            <ThumbsUp className="w-3 h-3" />
                            <span>{camp.positive_rate}%</span>
                          </span>
                        ) : (
                          <span className="text-[11px] text-slate-400">—</span>
                        )}
                      </td>

                      <td className="py-3.5 px-4 align-middle text-right" onClick={(e) => e.stopPropagation()}>
                        <div className="flex items-center justify-end space-x-2">
                          <button
                            onClick={() => setSelectedCampaignId(camp.id)}
                            className="px-2.5 py-1 text-xs font-semibold text-[#201D6E] bg-indigo-50 hover:bg-indigo-100 rounded-md transition-colors flex items-center space-x-1"
                          >
                            <span>Open</span>
                            <ChevronRight className="w-3.5 h-3.5" />
                          </button>
                          <button
                            onClick={() => {
                              if (window.confirm(`Are you sure you want to delete campaign '${camp.name}'?`)) {
                                deleteCampaignMutation.mutate(camp.id);
                              }
                            }}
                            className="p-1 text-slate-400 hover:text-rose-600 rounded hover:bg-rose-50 transition-colors"
                            title="Delete Campaign"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      ) : (
        /* View B: Campaign Detail View */
        <div className="space-y-4">
          {activeCampaignLoading || !activeCampaign ? (
            <div className="bg-white rounded-xl border border-slate-200 p-12">
              <LoadingState message="Loading campaign details & roster..." />
            </div>
          ) : (
            <>
              {/* Campaign Header & Management Card */}
              <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs">
                <div className="flex flex-col md:flex-row md:items-center justify-between pb-4 border-b border-slate-200 gap-4">
                  <div>
                    <button
                      onClick={() => setSelectedCampaignId(null)}
                      className="text-xs font-semibold text-slate-500 hover:text-[#201D6E] flex items-center space-x-1 mb-1.5 transition-colors"
                    >
                      <ArrowLeft className="w-3.5 h-3.5" />
                      <span>Back to All Campaigns</span>
                    </button>
                    <div className="flex items-center space-x-2.5">
                      <h2 className="text-xl font-bold text-slate-900 tracking-tight">{activeCampaign.name}</h2>
                      <span
                        className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-[10px] font-bold ${activeCampaign.status === 'active'
                          ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                          : activeCampaign.status === 'completed'
                            ? 'bg-blue-50 text-blue-700 border border-blue-200'
                            : 'bg-amber-50 text-amber-700 border border-amber-200'
                          }`}
                      >
                        {activeCampaign.status === 'draft' ? 'Draft Review' : activeCampaign.status.toUpperCase()}
                      </span>
                    </div>

                    <div className="flex flex-wrap items-center gap-3 mt-2 text-xs text-slate-500">
                      <div className="flex items-center space-x-1">
                        <Sparkles className="w-3.5 h-3.5 text-indigo-600" />
                        <span className="font-semibold text-slate-700">{activeCampaign.product_name}</span>
                      </div>
                      <span>•</span>
                      <a
                        href={activeCampaign.demo_url || 'https://marketplace.adople.ai/'}
                        target="_blank"
                        rel="noreferrer"
                        className="text-indigo-600 hover:underline flex items-center space-x-1"
                      >
                        <span>Demo Video Link</span>
                        <ExternalLink className="w-3 h-3" />
                      </a>
                      <span>•</span>
                      <span>Targeting {activeCampaign.target_companies_count} Companies, {activeCampaign.target_contacts_count} Contacts</span>
                    </div>
                  </div>

                  {/* Campaign Action Buttons */}
                  <div className="flex flex-wrap items-center gap-2">
                    <button
                      onClick={() => dispatchMutation.mutate({ campaignId: activeCampaign.id, simulate: false })}
                      disabled={dispatchMutation.isPending || activeCampaign.pending_count === 0}
                      className="px-4 py-2 text-xs font-bold text-white bg-[#201D6E] hover:bg-[#1a1758] disabled:bg-slate-300 rounded-lg shadow-xs transition-colors flex items-center space-x-1.5"
                    >
                      <Send className="w-3.5 h-3.5" />
                      <span>{dispatchMutation.isPending ? 'Dispatching...' : `Dispatch Live Outlook (${activeCampaign.pending_count} Pending)`}</span>
                    </button>

                    <button
                      onClick={() => dispatchMutation.mutate({ campaignId: activeCampaign.id, simulate: true })}
                      disabled={dispatchMutation.isPending || activeCampaign.pending_count === 0}
                      className="px-3 py-2 text-xs font-semibold text-slate-700 bg-slate-100 hover:bg-slate-200 rounded-lg transition-colors flex items-center space-x-1"
                      title="Test send in sandbox mode"
                    >
                      <Play className="w-3.5 h-3.5 text-slate-500" />
                      <span>Simulate Dispatch</span>
                    </button>

                    <button
                      onClick={() => {
                        if (window.confirm(`Delete campaign '${activeCampaign.name}'?`)) {
                          deleteCampaignMutation.mutate(activeCampaign.id);
                        }
                      }}
                      className="p-2 text-slate-400 hover:text-rose-600 rounded-lg hover:bg-rose-50 transition-colors"
                      title="Delete Campaign"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>

                {/* Sub-tab navigation within campaign */}
                <div className="flex items-center space-x-4 pt-3 text-xs font-semibold border-b border-slate-100">
                  <button
                    onClick={() => setCampaignTab('roster')}
                    className={`pb-2 flex items-center space-x-1.5 transition-colors border-b-2 ${campaignTab === 'roster'
                      ? 'border-[#201D6E] text-[#201D6E]'
                      : 'border-transparent text-slate-500 hover:text-slate-800'
                      }`}
                  >
                    <Users className="w-3.5 h-3.5" />
                    <span>Recipients Roster ({activeCampaign.recipients?.length || 0})</span>
                  </button>

                  <button
                    onClick={() => setCampaignTab('replies')}
                    className={`pb-2 flex items-center space-x-1.5 transition-colors border-b-2 ${campaignTab === 'replies'
                      ? 'border-[#201D6E] text-[#201D6E]'
                      : 'border-transparent text-slate-500 hover:text-slate-800'
                      }`}
                  >
                    <MessageSquare className="w-3.5 h-3.5" />
                    <span>Reply Monitoring & Sentiment ({activeCampaign.replies_count})</span>
                    {activeCampaign.positive_replies_count > 0 && (
                      <span className="bg-emerald-100 text-emerald-800 text-[10px] px-1.5 py-0.2 rounded-full font-bold">
                        {activeCampaign.positive_replies_count} Positive
                      </span>
                    )}
                  </button>

                  <button
                    onClick={() => setCampaignTab('template')}
                    className={`pb-2 flex items-center space-x-1.5 transition-colors border-b-2 ${campaignTab === 'template'
                      ? 'border-[#201D6E] text-[#201D6E]'
                      : 'border-transparent text-slate-500 hover:text-slate-800'
                      }`}
                  >
                    <FileText className="w-3.5 h-3.5" />
                    <span>Campaign Template & Personalization</span>
                  </button>
                </div>
              </div>

              {/* Sub-Tab 1: Recipients Roster */}
              {campaignTab === 'roster' && (
                <div className="bg-white rounded-xl border border-slate-200 shadow-2xs overflow-hidden">
                  <div className="p-4 border-b border-slate-200 flex flex-col md:flex-row md:items-center justify-between gap-3 bg-slate-50/50">
                    <div className="flex items-center space-x-2">
                      <div className="relative">
                        <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
                        <input
                          type="text"
                          placeholder="Search contact, company, email..."
                          value={searchFilter}
                          onChange={(e) => setSearchFilter(e.target.value)}
                          className="pl-8 pr-3 py-1.5 text-xs border border-slate-200 rounded-lg bg-white w-64 focus:outline-none focus:ring-1 focus:ring-[#201D6E]"
                        />
                      </div>
                      <select
                        value={statusFilter}
                        onChange={(e) => setStatusFilter(e.target.value)}
                        className="px-2.5 py-1.5 text-xs border border-slate-200 rounded-lg bg-white font-medium text-slate-700 focus:outline-none"
                      >
                        <option value="all">All Statuses</option>
                        <option value="pending">Pending</option>
                        <option value="sent">Sent</option>
                        <option value="replied">Replies Received</option>
                        <option value="positive">Positive Sentiment</option>
                      </select>
                    </div>

                    <div className="text-xs text-slate-500 font-medium">
                      Showing {filteredRecipients.length} of {activeCampaign.recipients?.length || 0} Target Contacts
                    </div>
                  </div>

                  <div className="overflow-x-auto">
                    <table className="w-full text-left border-collapse">
                      <thead>
                        <tr className="bg-slate-50/80 border-b border-slate-200 text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
                          <th className="py-3 px-4">Contact</th>
                          <th className="py-3 px-4">Company</th>
                          <th className="py-3 px-4">Outreach Status</th>
                          <th className="py-3 px-4">Personalized Email Preview</th>
                          <th className="py-3 px-4">Inbound Reply</th>
                          <th className="py-3 px-4 text-right">Actions</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100 text-xs">
                        {filteredRecipients.map((rec) => (
                          <tr key={rec.id} className="hover:bg-slate-50/60 transition-colors">
                            {/* Contact Details */}
                            <td className="py-3 px-4 align-middle">
                              <div className="font-bold text-slate-900">{rec.contact_name}</div>
                              <div className="text-[11px] text-slate-500">{rec.job_title || 'Decision Maker'}</div>
                              <div className="text-[10px] text-slate-400 font-mono mt-0.5">{rec.contact_email}</div>
                            </td>

                            {/* Company Details */}
                            <td className="py-3 px-4 align-middle">
                              <div className="font-semibold text-slate-800">{rec.company_name}</div>
                            </td>

                            {/* Outreach Status */}
                            <td className="py-3 px-4 align-middle">
                              {rec.status === 'sent' ? (
                                <div>
                                  <span className="inline-flex items-center space-x-1 bg-emerald-50 text-emerald-700 border border-emerald-200 px-2 py-0.5 rounded-full text-[10px] font-bold">
                                    <CheckCircle2 className="w-3 h-3 text-emerald-600" />
                                    <span>Sent via Outlook</span>
                                  </span>
                                  {rec.sent_at && (
                                    <div className="text-[10px] text-slate-400 mt-1">
                                      {new Date(rec.sent_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                                    </div>
                                  )}
                                </div>
                              ) : rec.status === 'failed' ? (
                                <span className="inline-flex items-center space-x-1 bg-rose-50 text-rose-700 border border-rose-200 px-2 py-0.5 rounded-full text-[10px] font-bold" title={rec.error_message || ''}>
                                  <AlertCircle className="w-3 h-3 text-rose-600" />
                                  <span>Failed</span>
                                </span>
                              ) : (
                                <span className="inline-flex items-center space-x-1 bg-amber-50 text-amber-700 border border-amber-200 px-2 py-0.5 rounded-full text-[10px] font-bold">
                                  <Clock className="w-3 h-3 text-amber-600" />
                                  <span>Pending Dispatch</span>
                                </span>
                              )}
                            </td>

                            {/* Personalized Preview */}
                            <td className="py-3 px-4 align-middle max-w-xs">
                              <div className="font-medium text-slate-900 truncate" title={rec.personalized_subject}>
                                {rec.personalized_subject}
                              </div>
                              <div className="text-[11px] text-slate-500 line-clamp-1 mt-0.5">
                                {rec.personalized_body.replace(/\n/g, ' ')}
                              </div>
                            </td>

                            {/* Inbound Reply Status */}
                            <td className="py-3 px-4 align-middle">
                              {rec.reply_status === 'positive' ? (
                                <span className="inline-flex items-center space-x-1 bg-emerald-100 text-emerald-800 px-2 py-0.5 rounded-full text-[10px] font-bold">
                                  <ThumbsUp className="w-3 h-3" />
                                  <span>Positive Interest</span>
                                </span>
                              ) : rec.reply_status === 'neutral' ? (
                                <span className="inline-flex items-center space-x-1 bg-slate-100 text-slate-700 px-2 py-0.5 rounded-full text-[10px] font-bold">
                                  <HelpCircle className="w-3 h-3" />
                                  <span>Neutral / Inquiry</span>
                                </span>
                              ) : rec.reply_status === 'negative' ? (
                                <span className="inline-flex items-center space-x-1 bg-rose-100 text-rose-800 px-2 py-0.5 rounded-full text-[10px] font-bold">
                                  <ThumbsDown className="w-3 h-3" />
                                  <span>Not Interested</span>
                                </span>
                              ) : (
                                <span className="text-[10px] text-slate-400 font-medium">Awaiting reply</span>
                              )}
                              {rec.reply_snippet && (
                                <div className="text-[10px] text-slate-600 italic mt-1 line-clamp-1" title={rec.reply_snippet}>
                                  &quot;{rec.reply_snippet}&quot;
                                </div>
                              )}
                            </td>

                            {/* Action Buttons */}
                            <td className="py-3 px-4 align-middle text-right">
                              <div className="flex items-center justify-end space-x-1.5">
                                <button
                                  onClick={() => {
                                    setPreviewRecipient(rec);
                                    setIsPreviewModalOpen(true);
                                  }}
                                  className="p-1.5 text-slate-600 hover:text-[#201D6E] hover:bg-indigo-50 rounded-md transition-colors"
                                  title="View Personalized Email"
                                >
                                  <Eye className="w-3.5 h-3.5" />
                                </button>
                                <button
                                  onClick={() => {
                                    setReplyRecipient(rec);
                                    setReplySnippetInput(rec.reply_snippet || '');
                                    setReplySentimentInput(
                                      (rec.reply_status === 'positive' || rec.reply_status === 'negative' || rec.reply_status === 'neutral')
                                        ? rec.reply_status
                                        : 'positive'
                                    );
                                    setIsReplyModalOpen(true);
                                  }}
                                  className="p-1.5 text-purple-600 hover:text-purple-800 hover:bg-purple-50 rounded-md transition-colors"
                                  title="Record Inbound Reply"
                                >
                                  <MessageSquare className="w-3.5 h-3.5" />
                                </button>
                              </div>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* Sub-Tab 2: Reply Monitoring & Sentiment Stream */}
              {campaignTab === 'replies' && (
                <div className="space-y-4">
                  <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs">
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-slate-200">
                      <div>
                        <h3 className="text-sm font-bold text-slate-900">Inbound Conversation & Sentiment Tracking</h3>
                        <p className="text-xs text-slate-500 mt-0.5">
                          Prospect replies received across this campaign with sentiment analysis and conversation snippets.
                        </p>
                      </div>
                      <div className="flex items-center space-x-2">
                        <span className="text-xs font-semibold text-slate-600">
                          {activeCampaign.replies_count} Total Replies ({activeCampaign.positive_replies_count} Positive)
                        </span>
                      </div>
                    </div>

                    {activeCampaign.recipients.filter((r) => r.reply_status !== 'no_reply').length === 0 ? (
                      <div className="py-12 text-center">
                        <div className="w-10 h-10 rounded-full bg-purple-50 text-purple-600 flex items-center justify-center mx-auto mb-2">
                          <MessageSquare className="w-5 h-5" />
                        </div>
                        <h4 className="text-xs font-bold text-slate-800">No Replies Recorded Yet</h4>
                        <p className="text-[11px] text-slate-500 mt-0.5 mb-3 max-w-sm mx-auto">
                          Incoming replies from Outlook will appear here. You can also simulate or record an inbound reply directly.
                        </p>
                        <button
                          onClick={() => {
                            if (activeCampaign.recipients.length > 0) {
                              setReplyRecipient(activeCampaign.recipients[0]);
                              setReplySnippetInput("Hi, thanks for reaching out. We'd love to schedule a demo of your solution next Tuesday.");
                              setReplySentimentInput('positive');
                              setIsReplyModalOpen(true);
                            }
                          }}
                          className="px-3 py-1.5 text-xs font-semibold text-purple-700 bg-purple-50 hover:bg-purple-100 rounded-lg transition-colors inline-flex items-center space-x-1"
                        >
                          <Plus className="w-3.5 h-3.5" />
                          <span>Simulate Inbound Reply</span>
                        </button>
                      </div>
                    ) : (
                      <div className="divide-y divide-slate-100 mt-3">
                        {activeCampaign.recipients
                          .filter((r) => r.reply_status !== 'no_reply')
                          .map((r) => (
                            <div key={r.id} className="py-3.5 flex flex-col md:flex-row md:items-start justify-between gap-3">
                              <div className="space-y-1">
                                <div className="flex items-center space-x-2">
                                  <span className="font-bold text-xs text-slate-900">{r.contact_name}</span>
                                  <span className="text-xs text-slate-400">•</span>
                                  <span className="text-xs font-semibold text-slate-700">{r.company_name}</span>
                                  <span
                                    className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${r.reply_status === 'positive'
                                      ? 'bg-emerald-100 text-emerald-800'
                                      : r.reply_status === 'negative'
                                        ? 'bg-rose-100 text-rose-800'
                                        : 'bg-slate-100 text-slate-700'
                                      }`}
                                  >
                                    {r.reply_status === 'positive' ? 'Positive (Interested)' : r.reply_status === 'negative' ? 'Negative (Declined)' : 'Neutral Inquiry'}
                                  </span>
                                </div>
                                <div className="text-[11px] text-slate-500 font-mono">{r.contact_email}</div>
                                <div className="bg-slate-50 border border-slate-200/80 rounded-lg p-2.5 text-xs text-slate-700 mt-2 font-sans">
                                  &quot;{r.reply_snippet}&quot;
                                </div>
                              </div>

                              <div className="flex items-center space-x-2">
                                <button
                                  onClick={() => {
                                    setReplyRecipient(r);
                                    setReplySnippetInput(r.reply_snippet || '');
                                    setReplySentimentInput(
                                      (r.reply_status === 'positive' || r.reply_status === 'negative' || r.reply_status === 'neutral')
                                        ? r.reply_status
                                        : 'positive'
                                    );
                                    setIsReplyModalOpen(true);
                                  }}
                                  className="px-2.5 py-1 text-xs font-semibold text-slate-600 bg-slate-100 hover:bg-slate-200 rounded-md transition-colors"
                                >
                                  Update Reply
                                </button>
                              </div>
                            </div>
                          ))}
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Sub-Tab 3: Campaign Template & Personalization */}
              {campaignTab === 'template' && (
                <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs space-y-4">
                  <div>
                    <h3 className="text-sm font-bold text-slate-900">Campaign Base Email Template</h3>
                    <p className="text-xs text-slate-500 mt-0.5">
                      This template was used to automatically synthesize personalized messages for every recipient based on their company pain points.
                    </p>
                  </div>

                  <div>
                    <label className="block text-xs font-bold text-slate-700 mb-1">Subject Line Template</label>
                    <div className="p-2.5 bg-slate-50 border border-slate-200 rounded-lg text-xs font-mono text-slate-800">
                      {activeCampaign.subject}
                    </div>
                  </div>

                  <div>
                    <label className="block text-xs font-bold text-slate-700 mb-1">Body Template</label>
                    <div className="p-3 bg-slate-50 border border-slate-200 rounded-lg text-xs font-mono text-slate-800 whitespace-pre-wrap leading-relaxed">
                      {activeCampaign.template_body}
                    </div>
                  </div>

                  <div>
                    <h4 className="text-xs font-bold text-slate-700 mb-1.5">Integrated Marketplace Solution Details</h4>
                    <div className="p-3.5 bg-indigo-50/50 border border-indigo-100 rounded-lg text-xs space-y-1.5">
                      <div className="flex items-center justify-between">
                        <span className="font-bold text-[#201D6E]">{activeCampaign.product_name}</span>
                        <a
                          href={activeCampaign.demo_url || 'https://marketplace.adople.ai/'}
                          target="_blank"
                          rel="noreferrer"
                          className="text-xs text-indigo-600 hover:underline flex items-center space-x-1"
                        >
                          <span>{activeCampaign.demo_url}</span>
                          <ExternalLink className="w-3 h-3" />
                        </a>
                      </div>
                      <p className="text-slate-600 text-[11px]">
                        Dynamic personalization replaces {'{{pain_point}}'} and {'{{demo_link}}'} with verified product walkthrough links.
                      </p>
                    </div>
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      )}

      {/* ---------------------------------------------------------------------- */}
      {/* MODAL 1: Create Campaign Wizard */}
      {/* ---------------------------------------------------------------------- */}
      {isCreateModalOpen && (
        <Modal
          isOpen={isCreateModalOpen}
          onClose={() => setIsCreateModalOpen(false)}
          title="Create New Outreach Campaign"
        >
          <div className="space-y-4 max-h-[75vh] overflow-y-auto pr-1">
            {/* Step 1: Campaign Details */}
            <div className="space-y-3 pb-3 border-b border-slate-200">
              <h4 className="text-xs font-bold text-[#201D6E] uppercase tracking-wider flex items-center space-x-1">
                <span>1. Campaign Information & Product Solution</span>
              </h4>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Campaign Name</label>
                <input
                  type="text"
                  value={formCampaignName}
                  onChange={(e) => setFormCampaignName(e.target.value)}
                  placeholder="e.g. Q4 Healthcare IDP Automation"
                  className="w-full px-3 py-1.5 text-xs border border-slate-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-[#201D6E]"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Product Solution (from marketplace.adople.ai)
                </label>
                <select
                  value={formProductSlug}
                  onChange={(e) => setFormProductSlug(e.target.value)}
                  className="w-full px-3 py-1.5 text-xs border border-slate-200 rounded-lg bg-white focus:outline-none focus:ring-1 focus:ring-[#201D6E]"
                >
                  {marketplaceProducts.map((p) => (
                    <option key={p.slug} value={p.slug}>
                      {p.name} ({p.category})
                    </option>
                  ))}
                </select>
                {formSelectedProduct && (
                  <div className="mt-1.5 p-2 bg-indigo-50/60 border border-indigo-100 rounded text-[11px] text-slate-600">
                    <span className="font-semibold text-indigo-900">{formSelectedProduct.name}: </span>
                    {formSelectedProduct.overview}
                  </div>
                )}
              </div>
            </div>

            {/* Step 2: Multi-Company & Contact Selection */}
            <div className="space-y-3 pb-3 border-b border-slate-200">
              <div className="flex items-center justify-between">
                <h4 className="text-xs font-bold text-[#201D6E] uppercase tracking-wider">
                  2. Select Target Companies & Contacts
                </h4>
                <div className="flex items-center space-x-2 text-xs">
                  <button
                    type="button"
                    onClick={toggleAllCompanies}
                    className="text-xs font-semibold text-indigo-600 hover:underline"
                  >
                    {formSelectedCompanyIds.length === companies.length ? 'Deselect All Companies' : 'Select All Companies'}
                  </button>
                  <span>•</span>
                  <button
                    type="button"
                    onClick={toggleAllContacts}
                    className="text-xs font-semibold text-indigo-600 hover:underline"
                  >
                    {formSelectedContactIds.length === formAvailableContacts.length ? 'Deselect All Contacts' : 'Select All Contacts'}
                  </button>
                </div>
              </div>

              {/* Company Badges */}
              <div>
                <div className="text-[11px] font-semibold text-slate-500 mb-1.5">Target Companies ({formSelectedCompanyIds.length} Selected)</div>
                <div className="flex flex-wrap gap-1.5 max-h-28 overflow-y-auto p-1 bg-slate-50 rounded border border-slate-200">
                  {companies.map((comp) => {
                    const isChecked = formSelectedCompanyIds.includes(comp.account_id);
                    return (
                      <button
                        key={comp.account_id}
                        type="button"
                        onClick={() => toggleCompany(comp.account_id)}
                        className={`px-2 py-1 rounded text-xs font-medium flex items-center space-x-1 transition-colors ${isChecked
                          ? 'bg-[#201D6E] text-white'
                          : 'bg-white text-slate-700 border border-slate-200 hover:bg-slate-100'
                          }`}
                      >
                        {isChecked ? <Check className="w-3 h-3" /> : null}
                        <span>{comp.company_name}</span>
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Contacts Checklist */}
              <div>
                <div className="text-[11px] font-semibold text-slate-500 mb-1.5">
                  Target Decision-Makers ({formSelectedContactIds.length} Selected)
                </div>
                <div className="max-h-40 overflow-y-auto divide-y divide-slate-100 border border-slate-200 rounded-lg bg-white">
                  {formAvailableContacts.length === 0 ? (
                    <div className="p-3 text-center text-xs text-slate-400">No contacts available for selected companies</div>
                  ) : (
                    formAvailableContacts.map((c) => {
                      const isChecked = formSelectedContactIds.includes(c.contact_id);
                      return (
                        <div
                          key={c.contact_id}
                          onClick={() => toggleContact(c.contact_id)}
                          className="p-2 px-3 flex items-center justify-between hover:bg-slate-50 cursor-pointer text-xs"
                        >
                          <div className="flex items-center space-x-2">
                            {isChecked ? (
                              <CheckSquare className="w-4 h-4 text-[#201D6E]" />
                            ) : (
                              <Square className="w-4 h-4 text-slate-300" />
                            )}
                            <div>
                              <span className="font-bold text-slate-800">{c.full_name}</span>
                              <span className="text-slate-400 text-[10px] ml-1.5">({c.job_title})</span>
                              <div className="text-[10px] text-slate-500">{c.company_name} • {c.email}</div>
                            </div>
                          </div>
                          {c.aligned_pain_point && (
                            <span className="text-[9px] bg-slate-100 text-slate-600 px-1.5 py-0.5 rounded truncate max-w-xs" title={c.aligned_pain_point}>
                              {c.aligned_pain_point}
                            </span>
                          )}
                        </div>
                      );
                    })
                  )}
                </div>
              </div>
            </div>

            {/* Step 3: Dynamic Template & Merge Tags */}
            <div className="space-y-3 pb-3 border-b border-slate-200">
              <div className="flex items-center justify-between">
                <h4 className="text-xs font-bold text-[#201D6E] uppercase tracking-wider">
                  3. Dynamic Email Template & Personalization
                </h4>
              </div>

              {/* Clickable Merge Tags */}
              <div className="bg-slate-50 p-2.5 rounded-lg border border-slate-200 text-xs">
                <div className="text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-1.5">Click to Insert Dynamic Merge Tags:</div>
                <div className="flex flex-wrap gap-1.5">
                  {[
                    { tag: 'first_name', label: 'First Name' },
                    { tag: 'contact_name', label: 'Contact Name' },
                    { tag: 'company_name', label: 'Company Name' },
                    { tag: 'pain_point', label: 'Pain Point' },
                    { tag: 'product_name', label: 'Product Name' },
                    { tag: 'product_overview', label: 'Product Overview' },
                    { tag: 'demo_link', label: 'Demo Video Link' },
                  ].map((m) => (
                    <button
                      key={m.tag}
                      type="button"
                      onClick={() => insertMergeTag(m.tag, 'body')}
                      className="px-2 py-0.5 bg-white border border-slate-200 hover:border-indigo-400 text-[11px] font-mono text-indigo-700 rounded transition-colors"
                    >
                      {`{{${m.tag}}}`}
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Subject Line Template</label>
                <input
                  type="text"
                  value={formSubjectTemplate}
                  onChange={(e) => setFormSubjectTemplate(e.target.value)}
                  className="w-full px-3 py-1.5 text-xs font-mono border border-slate-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-[#201D6E]"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Email Body Template</label>
                <textarea
                  rows={6}
                  value={formBodyTemplate}
                  onChange={(e) => setFormBodyTemplate(e.target.value)}
                  className="w-full p-3 text-xs font-mono border border-slate-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-[#201D6E] leading-relaxed"
                />
              </div>
            </div>

            {/* Step 4: Real-time Live Preview */}
            {resolvedFormPreview && (
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <h4 className="text-xs font-bold text-[#201D6E] uppercase tracking-wider flex items-center space-x-1">
                    <Sparkles className="w-3.5 h-3.5 text-indigo-600" />
                    <span>4. Live Resolved Preview Per Contact</span>
                  </h4>
                  {formSelectedContactIds.length > 0 && (
                    <select
                      value={formPreviewContact?.contact_id || ''}
                      onChange={(e) => setFormPreviewContactId(e.target.value)}
                      className="text-xs border border-slate-200 rounded px-2 py-0.5 bg-white font-medium text-slate-700"
                    >
                      {formAvailableContacts
                        .filter((c) => formSelectedContactIds.includes(c.contact_id))
                        .map((c) => (
                          <option key={c.contact_id} value={c.contact_id}>
                            Preview: {c.full_name} ({c.company_name})
                          </option>
                        ))}
                    </select>
                  )}
                </div>

                <div className="bg-slate-50 border border-slate-200 rounded-lg p-3 text-xs space-y-2 font-sans">
                  <div className="font-bold text-slate-900 border-b border-slate-200 pb-1.5">
                    Subject: {resolvedFormPreview.subject}
                  </div>
                  <div className="text-slate-700 whitespace-pre-wrap leading-relaxed">
                    {resolvedFormPreview.body}
                  </div>
                </div>
              </div>
            )}

            {/* Modal Actions */}
            <div className="flex items-center justify-end space-x-2 pt-3 border-t border-slate-200">
              <button
                type="button"
                onClick={() => setIsCreateModalOpen(false)}
                className="px-3.5 py-1.5 text-xs font-semibold text-slate-600 hover:bg-slate-100 rounded-lg transition-colors"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={() => createCampaignMutation.mutate()}
                disabled={createCampaignMutation.isPending || formSelectedContactIds.length === 0}
                className="px-4 py-2 text-xs font-bold text-white bg-[#201D6E] hover:bg-[#1a1758] disabled:bg-slate-300 rounded-lg shadow-xs transition-colors flex items-center space-x-1.5"
              >
                <Plus className="w-3.5 h-3.5" />
                <span>
                  {createCampaignMutation.isPending
                    ? 'Creating Campaign...'
                    : `Create Campaign (${formSelectedContactIds.length} Contacts)`}
                </span>
              </button>
            </div>
          </div>
        </Modal>
      )}

      {/* ---------------------------------------------------------------------- */}
      {/* MODAL 2: View Personalized Email Draft */}
      {/* ---------------------------------------------------------------------- */}
      {isPreviewModalOpen && previewRecipient && (
        <Modal
          isOpen={isPreviewModalOpen}
          onClose={() => {
            setIsPreviewModalOpen(false);
            setPreviewRecipient(null);
          }}
          title={`Personalized Email: ${previewRecipient.contact_name}`}
        >
          <div className="space-y-3 text-xs">
            <div className="bg-slate-50 p-3 rounded-lg border border-slate-200 space-y-1">
              <div><span className="font-bold text-slate-600">To:</span> {previewRecipient.contact_name} &lt;{previewRecipient.contact_email}&gt;</div>
              <div><span className="font-bold text-slate-600">Company:</span> {previewRecipient.company_name}</div>
              <div><span className="font-bold text-slate-600">Title:</span> {previewRecipient.job_title}</div>
              <div><span className="font-bold text-slate-600">Status:</span> {previewRecipient.status.toUpperCase()}</div>
              {previewRecipient.outlook_message_id && (
                <div><span className="font-bold text-slate-600">Message ID:</span> {previewRecipient.outlook_message_id}</div>
              )}
            </div>

            <div>
              <label className="block text-xs font-bold text-slate-700 mb-1">Subject</label>
              <div className="p-2.5 bg-slate-50 border border-slate-200 rounded-lg font-medium text-slate-900">
                {previewRecipient.personalized_subject}
              </div>
            </div>

            <div>
              <label className="block text-xs font-bold text-slate-700 mb-1">Personalized Body</label>
              <div className="p-3 bg-slate-50 border border-slate-200 rounded-lg whitespace-pre-wrap leading-relaxed text-slate-800">
                {previewRecipient.personalized_body}
              </div>
            </div>

            <div className="flex justify-end pt-2">
              <button
                onClick={() => {
                  setIsPreviewModalOpen(false);
                  setPreviewRecipient(null);
                }}
                className="px-3.5 py-1.5 text-xs font-semibold text-slate-700 bg-slate-100 hover:bg-slate-200 rounded-lg transition-colors"
              >
                Close
              </button>
            </div>
          </div>
        </Modal>
      )}

      {/* ---------------------------------------------------------------------- */}
      {/* MODAL 3: Record Inbound Prospect Reply */}
      {/* ---------------------------------------------------------------------- */}
      {isReplyModalOpen && replyRecipient && (
        <Modal
          isOpen={isReplyModalOpen}
          onClose={() => {
            setIsReplyModalOpen(false);
            setReplyRecipient(null);
          }}
          title={`Record Reply from ${replyRecipient.contact_name}`}
        >
          <div className="space-y-4 text-xs">
            <div className="p-2.5 bg-purple-50 border border-purple-100 rounded-lg text-purple-900">
              Record or simulate an inbound prospect email reply. Sentiment analysis updates campaign response KPIs in real-time.
            </div>

            <div>
              <label className="block text-xs font-bold text-slate-700 mb-1">Reply Sentiment</label>
              <div className="grid grid-cols-3 gap-2">
                <button
                  type="button"
                  onClick={() => setReplySentimentInput('positive')}
                  className={`py-2 px-3 rounded-lg text-xs font-bold flex items-center justify-center space-x-1.5 transition-colors border ${replySentimentInput === 'positive'
                    ? 'bg-emerald-50 text-emerald-800 border-emerald-300 ring-2 ring-emerald-500/20'
                    : 'bg-white text-slate-600 border-slate-200 hover:bg-slate-50'
                    }`}
                >
                  <ThumbsUp className="w-3.5 h-3.5 text-emerald-600" />
                  <span>Positive</span>
                </button>

                <button
                  type="button"
                  onClick={() => setReplySentimentInput('neutral')}
                  className={`py-2 px-3 rounded-lg text-xs font-bold flex items-center justify-center space-x-1.5 transition-colors border ${replySentimentInput === 'neutral'
                    ? 'bg-slate-100 text-slate-800 border-slate-300 ring-2 ring-slate-400/20'
                    : 'bg-white text-slate-600 border-slate-200 hover:bg-slate-50'
                    }`}
                >
                  <HelpCircle className="w-3.5 h-3.5 text-slate-600" />
                  <span>Neutral</span>
                </button>

                <button
                  type="button"
                  onClick={() => setReplySentimentInput('negative')}
                  className={`py-2 px-3 rounded-lg text-xs font-bold flex items-center justify-center space-x-1.5 transition-colors border ${replySentimentInput === 'negative'
                    ? 'bg-rose-50 text-rose-800 border-rose-300 ring-2 ring-rose-500/20'
                    : 'bg-white text-slate-600 border-slate-200 hover:bg-slate-50'
                    }`}
                >
                  <ThumbsDown className="w-3.5 h-3.5 text-rose-600" />
                  <span>Negative</span>
                </button>
              </div>
            </div>

            <div>
              <label className="block text-xs font-bold text-slate-700 mb-1">Inbound Reply Snippet / Content</label>
              <textarea
                rows={4}
                value={replySnippetInput}
                onChange={(e) => setReplySnippetInput(e.target.value)}
                placeholder="Paste or write the prospect's reply..."
                className="w-full p-2.5 text-xs border border-slate-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-[#201D6E]"
              />
            </div>

            <div className="flex items-center justify-end space-x-2 pt-2 border-t border-slate-100">
              <button
                type="button"
                onClick={() => {
                  setIsReplyModalOpen(false);
                  setReplyRecipient(null);
                }}
                className="px-3 py-1.5 text-xs font-semibold text-slate-600 hover:bg-slate-100 rounded-lg transition-colors"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={recordReplyMutation.isPending || !replySnippetInput.trim()}
                onClick={() => {
                  if (activeCampaign && replyRecipient) {
                    recordReplyMutation.mutate({
                      campaignId: activeCampaign.id,
                      recipientId: replyRecipient.id,
                      sentiment: replySentimentInput,
                      replySnippet: replySnippetInput.trim(),
                    });
                  }
                }}
                className="px-4 py-2 text-xs font-bold text-white bg-purple-700 hover:bg-purple-800 disabled:bg-slate-300 rounded-lg transition-colors flex items-center space-x-1.5"
              >
                <Check className="w-3.5 h-3.5" />
                <span>{recordReplyMutation.isPending ? 'Saving...' : 'Record Reply'}</span>
              </button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
};
