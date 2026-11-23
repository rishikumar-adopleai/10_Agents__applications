import React, { useState, useEffect, useMemo } from 'react';
import { useParams, useNavigate, useSearchParams } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Send,
  Building2,
  Users,
  Sparkles,
  RotateCw,
  Save,
  CheckCircle2,
  AlertCircle,
  ExternalLink,
  Laptop,
  Check,
  ShieldCheck,
  Clock,
  Mail,
  Phone,
  Eye,
  Plus,
  ArrowLeft,
  Search,
  Filter,
  Copy,
  ChevronRight,
  Star,
  FileText,
  Trash2,
  UserPlus,
  Layers,
} from 'lucide-react';
import { apiClient } from '@/lib/apiClient';
import { StandardResponse } from '@/types/api';
import { LoadingState } from '@/components/ui/FeedbackStates';
import { Modal } from '@/components/ui/Modal';
import { OutreachCampaignSection } from '../components/OutreachCampaignSection';

interface CompanyItem {
  account_id: string;
  company_name: string;
  domain: string;
  industry: string;
  priority_score?: number;
  why_now?: string;
  buying_signal?: string;
  contacts_count?: number;
}

interface ContactItem {
  contact_id: string;
  account_id: string;
  company_name: string;
  company_domain: string;
  full_name: string;
  job_title: string;
  department: string;
  seniority: string;
  email: string;
  phone?: string | null;
  linkedin?: string | null;
  data_source: string;
  verification_status: string;
  contact_eligibility: string;
  is_primary: boolean;
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
  review_feedback?: string | null;
  evidence_facts?: Record<string, any>;
  sources?: string[];
}

interface LocalOutreachRecord {
  contact_id: string;
  subject: string;
  draft_body: string;
  channel: 'sms' | 'email';
  status: string;
  submitted_date: string;
  demo_status: string;
  demo_url?: string;
}

export const OutreachStudioPage: React.FC = () => {
  const { accountId } = useParams<{ accountId?: string }>();
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  // Search & Filter State
  const initialCompany = searchParams.get('company') || accountId || 'all';
  const initialContactId = searchParams.get('contact') || null;

  const [selectedCompany, setSelectedCompany] = useState<string>(initialCompany);
  const [selectedContactId, setSelectedContactId] = useState<string | null>(initialContactId);
  const [search, setSearch] = useState('');
  const [statusTab, setStatusTab] = useState<'all' | 'ready' | 'pending' | 'not_sent'>('all');

  // Workflow Mode: Single Contact Studio vs Outreach Campaigns
  const initialMode = (searchParams.get('mode') as 'single' | 'campaign') || 'single';
  const [viewMode, setViewMode] = useState<'single' | 'campaign'>(initialMode);

  // Active Composer / Detail State
  const [channel, setChannel] = useState<'sms' | 'email'>('email');
  const [recipientEmail, setRecipientEmail] = useState('');
  const [subject, setSubject] = useState('');
  const [draftMessage, setDraftMessage] = useState('');
  const [demoStatus, setDemoStatus] = useState<string>('Recommended');
  const [demoUrl, setDemoUrl] = useState<string | null>(null);
  const [isEditingExisting, setIsEditingExisting] = useState(false);
  const [copied, setCopied] = useState(false);
  const [toastMessage, setToastMessage] = useState<{ text: string; type: 'success' | 'info' | 'error' } | null>(null);

  // Marketplace Products Catalog State (from marketplace.adople.ai)
  const [selectedProductSlug, setSelectedProductSlug] = useState<string>('');
  const [isSyncModalOpen, setIsSyncModalOpen] = useState(false);
  const [syncUrlInput, setSyncUrlInput] = useState('https://marketplace.adople.ai/');

  // In-session local outreach store to track drafts submitted during the session
  const [sessionOutreaches, setSessionOutreaches] = useState<Record<string, LocalOutreachRecord>>({});

  // 1. Fetch all companies
  const { data: companies, isLoading: companiesLoading } = useQuery({
    queryKey: ['research', 'companies'],
    queryFn: async () => {
      const res = await apiClient.get<StandardResponse<CompanyItem[]>>('/research/companies');
      return res.data.data;
    },
  });

  // 2. Fetch all contacts
  const { data: allContacts, isLoading: contactsLoading } = useQuery({
    queryKey: ['research', 'contacts'],
    queryFn: async () => {
      const res = await apiClient.get<StandardResponse<ContactItem[]>>('/research/contacts');
      return res.data.data;
    },
  });

  // 3. Fetch all approvals (existing outreach items)
  const { data: approvals, isLoading: approvalsLoading } = useQuery({
    queryKey: ['research', 'approvals'],
    queryFn: async () => {
      const res = await apiClient.get<StandardResponse<ApprovalItemData[]>>('/research/approvals');
      return res.data.data;
    },
  });

  // 4. Fetch Marketplace Products (10 Products from marketplace.adople.ai stored in DB)
  const { data: marketplaceProducts } = useQuery({
    queryKey: ['research', 'products'],
    queryFn: async () => {
      const res = await apiClient.get<StandardResponse<MarketplaceProduct[]>>('/research/products');
      return res.data.data;
    },
  });

  // Mutation: Sync/Extract Product from Marketplace URL
  const syncProductMutation = useMutation({
    mutationFn: async (url: string) => {
      const res = await apiClient.post<StandardResponse<MarketplaceProduct>>('/research/products/sync', { url });
      return res.data.data;
    },
    onSuccess: (newProd) => {
      queryClient.invalidateQueries({ queryKey: ['research', 'products'] });
      setSelectedProductSlug(newProd.slug);
      setIsSyncModalOpen(false);
      setToastMessage({
        text: `Product '${newProd.name}' extracted and stored in database!`,
        type: 'success',
      });
      setTimeout(() => setToastMessage(null), 4000);
    },
    onError: (err: any) => {
      const msg = err?.response?.data?.detail || err?.message || 'Failed to extract product from URL.';
      setToastMessage({ text: msg, type: 'error' });
      setTimeout(() => setToastMessage(null), 6000);
    },
  });

  // Helper to find outreach details for a contact
  const getOutreachForContact = (contact: ContactItem) => {
    // Check in-session submissions first
    if (sessionOutreaches[contact.contact_id]) {
      const s = sessionOutreaches[contact.contact_id];
      return {
        hasOutreach: true,
        approval_id: `session-${contact.contact_id}`,
        status: s.status,
        channel: s.channel,
        subject: s.subject,
        draft_body: s.draft_body,
        submitted_date: s.submitted_date,
        demo_status: s.demo_status,
        demo_url: s.demo_url,
        review_feedback: null,
      };
    }

    // Check approvals from backend
    if (approvals) {
      const match = approvals.find(
        (a) =>
          (a.contact_email && contact.email && a.contact_email.toLowerCase() === contact.email.toLowerCase()) ||
          (a.contact_name && a.contact_name.toLowerCase() === contact.full_name.toLowerCase()) ||
          (a.account_id === contact.account_id && contact.is_primary)
      );

      if (match) {
        return {
          hasOutreach: true,
          approval_id: match.approval_id,
          status: match.status,
          channel: match.channel || 'email',
          subject: (match.evidence_facts as any)?.subject || `Following up on ${contact.company_name}'s initiative`,
          draft_body: match.draft_body,
          submitted_date: match.submitted_date,
          demo_status: match.demo_status,
          demo_url: 'https://marketplace.adople.ai/',
          review_feedback: match.review_feedback,
        };
      }
    }

    return {
      hasOutreach: false,
      approval_id: null,
      status: 'Not Sent',
      channel: 'email',
      subject: '',
      draft_body: '',
      submitted_date: 'Not initiated',
      demo_status: 'Not Attached',
      demo_url: null,
      review_feedback: null,
    };
  };

  // Selected contact object
  const activeContact = useMemo(() => {
    if (!selectedContactId || !allContacts) return null;
    return allContacts.find((c) => c.contact_id === selectedContactId) || null;
  }, [selectedContactId, allContacts]);

  // Selected contact company info
  const activeCompany = useMemo(() => {
    if (!activeContact || !companies) return null;
    return companies.find((comp) => comp.account_id === activeContact.account_id) || null;
  }, [activeContact, companies]);

  // 5. Intelligent Product Matching: Automatically matches the best product from the 10 marketplace products
  const activeProduct = useMemo(() => {
    if (!marketplaceProducts || marketplaceProducts.length === 0) return null;
    if (selectedProductSlug) {
      const found = marketplaceProducts.find((p) => p.slug === selectedProductSlug);
      if (found) return found;
    }
    const ind = (activeCompany?.industry || '').toLowerCase();
    const jt = (activeContact?.job_title || '').toLowerCase();
    if (ind.includes('health') || ind.includes('medic') || jt.includes('clinic') || jt.includes('radiolog')) {
      return (
        marketplaceProducts.find((p) => p.slug === 'radiology-ai') ||
        marketplaceProducts.find((p) => p.slug === 'document-extraction') ||
        marketplaceProducts[0]
      );
    }
    if (ind.includes('logistics') || ind.includes('supply') || ind.includes('fleet') || jt.includes('operat')) {
      return (
        marketplaceProducts.find((p) => p.slug === 'telecalling-agent') ||
        marketplaceProducts.find((p) => p.slug === 'voice-agent') ||
        marketplaceProducts[0]
      );
    }
    if (ind.includes('financ') || ind.includes('bank') || jt.includes('treasur') || jt.includes('cfo')) {
      return (
        marketplaceProducts.find((p) => p.slug === 'treasury-ask') ||
        marketplaceProducts.find((p) => p.slug === 'sec-analysis') ||
        marketplaceProducts[0]
      );
    }
    return marketplaceProducts.find((p) => p.slug === 'gtm-automation') || marketplaceProducts[0];
  }, [marketplaceProducts, selectedProductSlug, activeCompany, activeContact]);

  // When activeContact or activeProduct changes, initialize the composer or detail view
  useEffect(() => {
    if (activeContact) {
      const outreachInfo = getOutreachForContact(activeContact);
      const buyingSignal = activeCompany?.why_now || activeCompany?.buying_signal || 'operational expansion';
      const firstName = activeContact.full_name.split(' ')[0] || 'there';

      if (outreachInfo.hasOutreach) {
        // Preload existing outreach
        setChannel((outreachInfo.channel as any) || 'email');
        setRecipientEmail(activeContact.email);
        setSubject(outreachInfo.subject || `Following up on ${activeContact.company_name}'s initiative`);
        setDraftMessage(outreachInfo.draft_body);
        setDemoStatus(outreachInfo.demo_status || 'Ready');
        setDemoUrl(outreachInfo.demo_url || null);
        setIsEditingExisting(false);
      } else {
        // Step 4: Generate personalized draft based on Company Pain Points & Matched Product Solution (No ICP score)
        setChannel('email');
        setRecipientEmail(activeContact.email);
        setSubject(`Following up on ${activeContact.company_name}'s ${buyingSignal.slice(0, 32)}`);

        const prodName = activeProduct?.name || 'Adople Enterprise AI Platform';
        const prodOverview =
          activeProduct?.overview ||
          'We built an autonomous workflow engine that eliminates manual review cycles without replacing your existing toolchain.';
        const demoLink = activeProduct?.demo_video_url || 'https://marketplace.adople.ai/';
        setDemoUrl(demoLink);

        const painPoint =
          activeContact.aligned_pain_point ||
          (activeCompany?.industry === 'Logistics'
            ? 'manual dispatch coordination bottlenecks across expanding depots'
            : activeCompany?.industry === 'Healthcare'
            ? 'delayed clinical documentation and imaging review backlogs'
            : 'sales reps spending 70% of their workday on manual prospect research');

        const generatedDraft =
          `Hi ${firstName},\n\n` +
          `I noticed ${activeContact.company_name}'s recent initiative regarding ${buyingSignal}. ` +
          `Teams in your space often face challenges with ${painPoint.toLowerCase()}.\n\n` +
          `We built ${prodName} to solve this: ${prodOverview}\n\n` +
          `I prepared a tailored product demonstration for your team here: ${demoLink}\n\n` +
          `Would you be open to a quick 10-minute briefing next Tuesday to discuss how this fits your roadmap?\n\n` +
          `Best,\nAdople AI Outreach Team`;

        setDraftMessage(generatedDraft);
        setDemoStatus(`Product Attached: ${prodName}`);
        setIsEditingExisting(true);
      }
    }
  }, [activeContact, activeCompany, activeProduct]);

  // Submit for Approval Mutation
  const submitApprovalMutation = useMutation({
    mutationFn: async () => {
      if (!activeContact) return;
      const res = await apiClient.post<StandardResponse<any>>(
        `/research/company/${activeContact.account_id}/outreach/submit-approval`,
        {
          draft_body: draftMessage,
          subject,
          channel,
          contact_id: activeContact.contact_id,
          recipient_name: activeContact.full_name,
          recipient_email: recipientEmail || activeContact.email,
          demo_status: demoStatus,
        }
      );
      return res.data.data;
    },
    onSuccess: () => {
      if (activeContact) {
        // Record in session
        setSessionOutreaches((prev) => ({
          ...prev,
          [activeContact.contact_id]: {
            contact_id: activeContact.contact_id,
            subject,
            draft_body: draftMessage,
            channel,
            status: 'Pending',
            submitted_date: 'Just now',
            demo_status: demoStatus,
            demo_url: demoUrl || undefined,
          },
        }));

        setToastMessage({
          text: `Outreach draft for ${activeContact.full_name} submitted to Approval Center! (Never auto-sent)`,
          type: 'success',
        });
        setTimeout(() => setToastMessage(null), 4000);
        queryClient.invalidateQueries({ queryKey: ['research', 'approvals'] });
        setIsEditingExisting(false);
      }
    },
  });

  // Send / Dispatch Outreach Mutation
  const sendOutreachMutation = useMutation({
    mutationFn: async (approvalId: string) => {
      const res = await apiClient.post<StandardResponse<any>>(
        `/research/approvals/${approvalId}/send`
      );
      return res.data;
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['research', 'approvals'] });
      setToastMessage({
        text: data.message || 'Outreach email dispatched successfully via Microsoft Outlook!',
        type: 'success',
      });
      setTimeout(() => setToastMessage(null), 5000);
    },
    onError: (err: any) => {
      const errorMsg =
        err?.response?.data?.detail ||
        err?.response?.data?.message ||
        err?.message ||
        'Failed to dispatch outreach email via Microsoft Outlook.';
      setToastMessage({
        text: errorMsg,
        type: 'error',
      });
      setTimeout(() => setToastMessage(null), 6000);
    },
  });

  // Delete Outreach Mutation
  const deleteOutreachMutation = useMutation({
    mutationFn: async ({ approvalId, contactId }: { approvalId?: string; contactId: string }) => {
      const idToDelete = approvalId || contactId;
      const res = await apiClient.delete<StandardResponse<any>>(
        `/research/approvals/${idToDelete}`
      );
      return res.data;
    },
    onSuccess: (_data, variables) => {
      setSessionOutreaches((prev) => {
        const copy = { ...prev };
        delete copy[variables.contactId];
        return copy;
      });
      queryClient.invalidateQueries({ queryKey: ['research', 'approvals'] });
      setSelectedContactId(null);
      setToastMessage({
        text: 'Outreach record deleted successfully.',
        type: 'success',
      });
      setTimeout(() => setToastMessage(null), 4000);
    },
  });

  // Request Demo Mutation
  const requestDemoMutation = useMutation({
    mutationFn: async () => {
      if (!activeContact) return;
      const res = await apiClient.post<StandardResponse<any>>(
        `/research/company/${activeContact.account_id}/demo/request`,
        {
          template_name: 'enterprise_sales_automation_v1',
          relevant_use_case: activeCompany?.why_now || 'Enterprise Workflow Automation',
        }
      );
      return res.data.data;
    },
    onSuccess: (data) => {
      setDemoStatus('Ready');
      setDemoUrl(data.access_url);
      setToastMessage({
        text: 'Personalized interactive demo provisioned and attached to outreach!',
        type: 'success',
      });
      setTimeout(() => setToastMessage(null), 3500);
    },
  });

  // Add Contact Form State
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [newAccountId, setNewAccountId] = useState('');
  const [newCompanyName, setNewCompanyName] = useState('');
  const [newFullName, setNewFullName] = useState('');
  const [newEmail, setNewEmail] = useState('');
  const [newJobTitle, setNewJobTitle] = useState('');
  const [newDepartment, setNewDepartment] = useState('Leadership');
  const [newPhone, setNewPhone] = useState('');
  const [newLinkedin, setNewLinkedin] = useState('');
  const [formError, setFormError] = useState<string | null>(null);

  // Mutation: Create New Contact
  const createContactMutation = useMutation({
    mutationFn: async () => {
      if (!newFullName.trim()) throw new Error('Please enter a full name.');
      if (!newEmail.trim() || !newEmail.includes('@')) throw new Error('Please enter a valid email address.');
      const accountIdToUse = newAccountId || (companies && companies.length > 0 ? companies[0].account_id : 'ACC-001');

      const res = await apiClient.post<StandardResponse<ContactItem>>('/research/contacts', {
        account_id: accountIdToUse,
        company_name: newCompanyName.trim() || undefined,
        full_name: newFullName.trim(),
        email: newEmail.trim(),
        job_title: newJobTitle.trim() || 'Decision Maker',
        department: newDepartment.trim() || 'Leadership',
        phone: newPhone.trim() || undefined,
        linkedin_url: newLinkedin.trim() || undefined,
      });
      return res.data.data;
    },
    onSuccess: (createdContact) => {
      queryClient.invalidateQueries({ queryKey: ['research', 'contacts'] });
      queryClient.invalidateQueries({ queryKey: ['research', 'companies'] });
      setIsAddModalOpen(false);
      setNewFullName('');
      setNewEmail('');
      setNewJobTitle('');
      setNewPhone('');
      setNewLinkedin('');
      setFormError(null);

      // Immediately select the new contact and open composer
      setSelectedContactId(createdContact.contact_id);
      setIsEditingExisting(true);

      setToastMessage({
        text: `Contact ${createdContact.full_name} added! You can now compose and send outreach.`,
        type: 'success',
      });
      setTimeout(() => setToastMessage(null), 5000);
    },
    onError: (err: any) => {
      setFormError(err?.message || err?.response?.data?.detail || 'Failed to add contact.');
    },
  });

  if (companiesLoading || contactsLoading || approvalsLoading || !allContacts || !companies) {
    return <LoadingState message="Loading Outreach Studio across all enterprise companies..." />;
  }

  // Handle regenerating fresh draft
  const handleRegenerate = () => {
    if (!activeContact) return;
    const buyingSignal = activeCompany?.why_now || activeCompany?.buying_signal || 'operational expansion';
    const firstName = activeContact.full_name.split(' ')[0] || 'there';
    const icpScore = activeCompany?.priority_score ?? 75;
    const isHighIcp = icpScore >= 80;
    const demoLink = 'https://marketplace.adople.ai/';

    let freshDraft =
      `Hi ${firstName},\n\n` +
      `Following up on ${activeContact.company_name}'s recent developments regarding ${buyingSignal}. ` +
      `We help technical leaders deploy autonomous AI agents that handle repetitive document operations and exception routing with complete human oversight.\n\n` +
      `Would you be open to reviewing a custom 2-minute walkthrough tailored to ${activeContact.company_name}?\n\n`;

    if (isHighIcp) {
      freshDraft +=
        `Interactive Demo Preview: ${demoLink}\n\n` +
        `Best,\nAdople AI Outreach Team`;
      setDemoStatus(`Auto-Attached (ICP: ${icpScore}%)`);
    } else {
      freshDraft +=
        `Best,\nAdople AI Outreach Team`;
      setDemoStatus(`Manual Option (ICP: ${icpScore}%)`);
    }

    setDraftMessage(freshDraft);
    setToastMessage({
      text: 'Draft regenerated with updated observations and company context.',
      type: 'info',
    });
    setTimeout(() => setToastMessage(null), 3000);
  };

  // Copy outreach message to clipboard
  const handleCopy = () => {
    navigator.clipboard.writeText(draftMessage);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  // Filtered contacts list
  const filteredContacts = allContacts.filter((c) => {
    // 1. Company Filter
    const matchesCompany = selectedCompany === 'all' || c.account_id === selectedCompany;

    // 2. Search Filter
    const q = search.toLowerCase().trim();
    const matchesSearch =
      !q ||
      c.full_name.toLowerCase().includes(q) ||
      c.job_title.toLowerCase().includes(q) ||
      c.email.toLowerCase().includes(q) ||
      c.company_name.toLowerCase().includes(q);

    // 3. Status Tab Filter
    const outreach = getOutreachForContact(c);
    let matchesStatus = true;
    if (statusTab === 'ready') {
      matchesStatus =
        outreach.hasOutreach &&
        (outreach.status.toLowerCase().includes('ready') ||
          outreach.status.toLowerCase().includes('approved') ||
          outreach.status.toLowerCase().includes('sent'));
    } else if (statusTab === 'pending') {
      matchesStatus =
        outreach.hasOutreach &&
        outreach.status.toLowerCase().includes('pending');
    } else if (statusTab === 'not_sent') {
      matchesStatus = !outreach.hasOutreach;
    }

    return matchesCompany && matchesSearch && matchesStatus;
  });

  // Calculate high-level KPI counts
  const totalContactsCount = allContacts.length;
  const readyOutreachCount = allContacts.filter((c) => {
    const o = getOutreachForContact(c);
    return (
      o.hasOutreach &&
      (o.status.toLowerCase().includes('ready') ||
        o.status.toLowerCase().includes('approved') ||
        o.status.toLowerCase().includes('sent'))
    );
  }).length;

  const pendingApprovalCount = allContacts.filter((c) => {
    const o = getOutreachForContact(c);
    return o.hasOutreach && o.status.toLowerCase().includes('pending');
  }).length;

  const notSentCount = allContacts.filter((c) => !getOutreachForContact(c).hasOutreach).length;

  // Active contact outreach info
  const activeContactOutreach = activeContact ? getOutreachForContact(activeContact) : null;

  return (
    <div className="space-y-6">
      {/* 1. Page Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between pb-3 border-b border-slate-200 gap-3">
        <div>
          <div className="flex items-center space-x-2.5">
            <h1 className="text-xl font-bold tracking-tight text-slate-900">Outreach Studio</h1>
            <span className="bg-indigo-50 text-indigo-700 border border-indigo-200/80 rounded-full px-2.5 py-0.5 text-[10px] font-semibold flex items-center space-x-1">
              <Building2 className="w-3 h-3" />
              <span>
                {selectedCompany === 'all' ? 'All Companies' : companies.find((c) => c.account_id === selectedCompany)?.company_name}
              </span>
            </span>
          </div>
          <p className="text-xs text-slate-500 mt-1">
            Synthesize, review, and govern personalized outreach messages across all target companies and decision-makers.
          </p>
        </div>

        <div className="flex items-center space-x-2">
          <button
            onClick={() => {
              setNewAccountId(selectedCompany !== 'all' ? selectedCompany : (companies[0]?.account_id || 'ACC-001'));
              setFormError(null);
              setIsAddModalOpen(true);
            }}
            className="px-3 py-1.5 text-xs font-semibold text-white bg-[#201D6E] hover:bg-[#1a1758] rounded-lg shadow-2xs transition-colors flex items-center space-x-1.5"
          >
            <UserPlus className="w-3.5 h-3.5" />
            <span>Add Contact</span>
          </button>
          <button
            onClick={() => navigate('/research/company')}
            className="px-3 py-1.5 text-xs font-semibold text-slate-700 bg-white border border-slate-200 hover:bg-slate-50 rounded-lg shadow-2xs transition-colors flex items-center space-x-1"
          >
            <Building2 className="w-3.5 h-3.5" />
            <span>Company Intelligence</span>
          </button>
          <button
            onClick={() => navigate('/research/contacts')}
            className="px-3 py-1.5 text-xs font-semibold text-slate-700 bg-white border border-slate-200 hover:bg-slate-50 rounded-lg shadow-2xs transition-colors flex items-center space-x-1"
          >
            <Users className="w-3.5 h-3.5" />
            <span>Contact Discovery</span>
          </button>
          <button
            onClick={() => navigate('/research/approvals')}
            className="px-3 py-1.5 text-xs font-semibold text-indigo-700 bg-indigo-50 border border-indigo-200 hover:bg-indigo-100 rounded-lg transition-colors flex items-center space-x-1"
          >
            <CheckCircle2 className="w-3.5 h-3.5" />
            <span>Approval Center</span>
          </button>
        </div>
      </div>

      {/* Top-Level Section Switcher: Single Contact Studio vs Outreach Campaigns */}
      <div className="flex items-center space-x-2 bg-slate-100/90 p-1 rounded-xl w-fit border border-slate-200/80">
        <button
          onClick={() => {
            setViewMode('single');
            setSearchParams((prev) => {
              const p = new URLSearchParams(prev);
              p.set('mode', 'single');
              return p;
            });
          }}
          className={`flex items-center space-x-2 px-4 py-2 text-xs font-bold rounded-lg transition-all ${
            viewMode === 'single'
              ? 'bg-white text-[#201D6E] shadow-xs'
              : 'text-slate-600 hover:text-slate-900'
          }`}
        >
          <Mail className="w-3.5 h-3.5" />
          <span>Single Contact Studio</span>
          <span className="text-[10px] px-1.5 py-0.2 rounded-full font-semibold bg-slate-100 text-slate-600">
            Human Approval
          </span>
        </button>

        <button
          onClick={() => {
            setViewMode('campaign');
            setSearchParams((prev) => {
              const p = new URLSearchParams(prev);
              p.set('mode', 'campaign');
              return p;
            });
          }}
          className={`flex items-center space-x-2 px-4 py-2 text-xs font-bold rounded-lg transition-all ${
            viewMode === 'campaign'
              ? 'bg-[#201D6E] text-white shadow-xs'
              : 'text-slate-600 hover:text-slate-900'
          }`}
        >
          <Layers className="w-3.5 h-3.5" />
          <span>Outreach Campaigns</span>
          <span className="text-[10px] px-1.5 py-0.2 rounded-full font-semibold bg-indigo-500/30 text-indigo-100">
            Multi-Target & Replies
          </span>
        </button>
      </div>

      {viewMode === 'campaign' ? (
        <OutreachCampaignSection
          companies={companies}
          allContacts={allContacts}
          marketplaceProducts={marketplaceProducts}
        />
      ) : (
        <>
      {/* Toast Notification */}
      {toastMessage && (
        <div
          className={`p-3 rounded-lg text-xs font-medium flex items-center justify-between border ${
            toastMessage.type === 'success'
              ? 'bg-emerald-50 border-emerald-200 text-emerald-800'
              : toastMessage.type === 'error'
              ? 'bg-rose-50 border-rose-200 text-rose-800'
              : 'bg-indigo-50 border-indigo-200 text-indigo-800'
          }`}
        >
          <div className="flex items-center space-x-2">
            {toastMessage.type === 'error' ? (
              <AlertCircle className="w-4 h-4 text-rose-600" />
            ) : (
              <CheckCircle2 className="w-4 h-4 text-emerald-600" />
            )}
            <span>{toastMessage.text}</span>
          </div>
          <button onClick={() => setToastMessage(null)} className="text-xs text-slate-400 hover:text-slate-600 font-semibold">
            Dismiss
          </button>
        </div>
      )}

      {/* 2. KPI Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-white p-4 rounded-xl border border-slate-200/90 shadow-2xs">
          <div className="text-[10px] font-semibold uppercase tracking-wider text-slate-400">Total Decision-Makers</div>
          <div className="text-2xl font-bold text-slate-900 mt-1">{totalContactsCount}</div>
          <div className="text-[11px] text-slate-500 mt-0.5">Across {companies.length} target companies</div>
        </div>

        <div className="bg-white p-4 rounded-xl border border-slate-200/90 shadow-2xs">
          <div className="text-[10px] font-semibold uppercase tracking-wider text-slate-400">Outreach Ready / Sent</div>
          <div className="text-2xl font-bold text-emerald-600 mt-1">{readyOutreachCount}</div>
          <div className="text-[11px] text-slate-500 mt-0.5">Approved &amp; ready for dispatch</div>
        </div>

        <div className="bg-white p-4 rounded-xl border border-slate-200/90 shadow-2xs">
          <div className="text-[10px] font-semibold uppercase tracking-wider text-slate-400">Pending Review</div>
          <div className="text-2xl font-bold text-amber-600 mt-1">{pendingApprovalCount}</div>
          <div className="text-[11px] text-slate-500 mt-0.5">Awaiting human sales rep sign-off</div>
        </div>

        <div className="bg-white p-4 rounded-xl border border-slate-200/90 shadow-2xs">
          <div className="text-[10px] font-semibold uppercase tracking-wider text-slate-400">Pending Outreach</div>
          <div className="text-2xl font-bold text-[#201D6E] mt-1">{notSentCount}</div>
          <div className="text-[11px] text-slate-500 mt-0.5">Ready for personalized messaging</div>
        </div>
      </div>

      {/* 3. Main Workspace: Either Detail/Composer View OR Centralized Directory Table */}
      {activeContact ? (
        /* Detailed Outreach View / Message Composer for Selected Contact */
        <div className="space-y-4">
          {/* Back Navigation Bar */}
          <div className="flex items-center justify-between bg-white px-4 py-2.5 rounded-xl border border-slate-200/90 shadow-2xs text-xs">
            <div className="flex items-center space-x-3">
              <button
                onClick={() => setSelectedContactId(null)}
                className="px-3 py-1.5 text-xs font-semibold text-slate-700 bg-white border border-slate-200 hover:bg-slate-50 rounded-lg shadow-2xs transition-colors flex items-center space-x-1.5"
              >
                <ArrowLeft className="w-3.5 h-3.5" />
                <span>Back to All Outreaches</span>
              </button>

              <span className="text-slate-300">|</span>

              <div className="flex items-center space-x-2">
                <span className="font-bold text-slate-900 text-xs">{activeContact.full_name}</span>
                <span className="text-slate-400">&bull;</span>
                <span className="text-slate-600 font-medium">{activeContact.company_name}</span>
                <span className="text-slate-400 font-mono text-[11px]">({activeContact.account_id})</span>
              </div>
            </div>

            <div className="flex items-center space-x-2">
              <span
                className={`px-2.5 py-1 rounded-full text-[10px] font-bold ${
                  activeContactOutreach?.hasOutreach && activeContactOutreach.status.toLowerCase().includes('ready')
                    ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                    : activeContactOutreach?.hasOutreach && activeContactOutreach.status.toLowerCase().includes('pending')
                    ? 'bg-amber-50 text-amber-800 border border-amber-200'
                    : 'bg-slate-100 text-slate-700 border border-slate-200'
                }`}
              >
                {activeContactOutreach?.hasOutreach
                  ? `STATUS: ${activeContactOutreach.status.toUpperCase()}`
                  : 'STATUS: NEW OUTREACH DRAFT'}
              </span>

              {activeContactOutreach?.hasOutreach && !isEditingExisting && (
                <button
                  onClick={() => setIsEditingExisting(true)}
                  className="px-3 py-1 text-xs font-semibold text-indigo-700 bg-indigo-50 hover:bg-indigo-100 border border-indigo-200 rounded-lg transition-colors"
                >
                  Edit / Revise
                </button>
              )}
            </div>
          </div>

          {/* Two-Panel Layout */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
            {/* Left Panel: Prospect Context & Demo (5 Cols) */}
            <div className="lg:col-span-5 space-y-4">
              {/* Account & Contact Card */}
              <div className="bg-white p-4 rounded-xl border border-slate-200/90 shadow-2xs space-y-3 text-xs">
                <div className="flex items-center justify-between pb-2 border-b border-slate-100">
                  <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Prospect Context</span>
                  <span className="text-[10px] text-slate-500 font-mono">{activeContact.account_id}</span>
                </div>

                <div>
                  <div className="font-bold text-slate-900 text-sm">{activeContact.company_name}</div>
                  <a
                    href={`https://${activeContact.company_domain}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-indigo-600 hover:underline text-[11px] flex items-center space-x-1 mt-0.5"
                  >
                    <span>{activeContact.company_domain}</span>
                    <ExternalLink className="w-3 h-3" />
                  </a>
                </div>

                {/* Selected Contact Card */}
                <div className="p-3 bg-slate-50 rounded-lg border border-slate-200/70 space-y-1">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-slate-900 text-xs">{activeContact.full_name}</span>
                    <span className="bg-indigo-50 text-indigo-700 px-1.5 py-0.2 rounded text-[9px] font-bold border border-indigo-200/60">
                      Target Decision-Maker
                    </span>
                  </div>
                  <div className="text-[11px] text-slate-600">{activeContact.job_title}</div>
                  <div className="text-[11px] text-slate-500 font-mono flex items-center space-x-1">
                    <Mail className="w-3 h-3 text-slate-400" />
                    <span>{activeContact.email}</span>
                  </div>
                </div>

                {/* Buying Signal Evidence */}
                <div className="space-y-1 pt-1">
                  <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">
                    Observed Buying Signal
                  </span>
                  <p className="text-slate-800 font-medium leading-snug bg-amber-50/60 border border-amber-200/70 p-2.5 rounded-lg text-[11px]">
                    {activeCompany?.why_now || activeCompany?.buying_signal || 'Technical expansion and scaling initiatives'}
                  </p>
                </div>

                {/* Agent 1 Intelligence: Company Pain Points */}
                <div className="space-y-1.5 pt-1">
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">
                      Agent 1: Diagnosed Pain Points
                    </span>
                    <span className="text-[10px] bg-rose-50 text-rose-700 px-1.5 py-0.2 rounded font-semibold border border-rose-100">
                      Pain Point Aligned
                    </span>
                  </div>
                  <div className="p-2.5 bg-rose-50/50 border border-rose-200/60 rounded-lg text-[11px] text-slate-800 space-y-1">
                    <div className="font-semibold text-rose-900 flex items-center space-x-1">
                      <AlertCircle className="w-3 h-3 text-rose-600 shrink-0" />
                      <span>{activeContact.aligned_pain_point || 'Operational bottlenecks & manual workflow overhead'}</span>
                    </div>
                    <p className="text-[10px] text-slate-500">
                      Agent 2 mapped contact <strong>{activeContact.full_name}</strong> ({activeContact.job_title}) as the decision-maker directly responsible for resolving this challenge.
                    </p>
                  </div>
                </div>

                {/* Verified Source URL */}
                <div className="pt-2 border-t border-slate-100 flex items-center justify-between text-[11px] text-slate-500">
                  <span>Verified Source URL:</span>
                  <a
                    href={`https://jobs.${activeContact.company_domain}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-indigo-600 hover:underline truncate max-w-[180px]"
                  >
                    https://jobs.{activeContact.company_domain}
                  </a>
                </div>
              </div>

              {/* Matched Product Solution & Demo (marketplace.adople.ai) */}
              <div className="bg-white p-4 rounded-xl border border-slate-200/90 shadow-2xs space-y-3.5 text-xs">
                <div className="flex items-center justify-between pb-2 border-b border-slate-100">
                  <div className="flex items-center space-x-1.5">
                    <Laptop className="w-3.5 h-3.5 text-indigo-600" />
                    <span className="text-[10px] font-bold text-slate-900 uppercase tracking-wider">
                      Matched Marketplace Product
                    </span>
                  </div>
                  <button
                    onClick={() => setIsSyncModalOpen(true)}
                    className="text-[10px] text-indigo-600 hover:text-indigo-800 font-bold flex items-center space-x-1 bg-indigo-50 px-2 py-0.5 rounded border border-indigo-200/80 transition-colors"
                    title="Extract new product from marketplace.adople.ai URL"
                  >
                    <Plus className="w-2.5 h-2.5" />
                    <span>Sync Product Link</span>
                  </button>
                </div>

                {/* Product Selector Dropdown */}
                <div className="space-y-1">
                  <label className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">
                    Product Solution (from marketplace.adople.ai)
                  </label>
                  <select
                    value={activeProduct?.slug || ''}
                    onChange={(e) => setSelectedProductSlug(e.target.value)}
                    className="w-full px-2.5 py-1.5 bg-slate-50 border border-slate-200 rounded-lg text-xs font-semibold text-slate-800 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                  >
                    {(marketplaceProducts || []).map((p) => (
                      <option key={p.slug} value={p.slug}>
                        {p.name} ({p.category})
                      </option>
                    ))}
                  </select>
                </div>

                {/* Product Details Card */}
                {activeProduct && (
                  <div className="p-3 bg-indigo-50/50 rounded-lg border border-indigo-100 space-y-2 text-slate-700">
                    <div className="flex items-center justify-between">
                      <span className="font-bold text-slate-900 text-xs">{activeProduct.name}</span>
                      <span className="bg-white text-indigo-700 px-2 py-0.5 rounded text-[9px] font-bold border border-indigo-200 shadow-2xs">
                        {activeProduct.category}
                      </span>
                    </div>

                    <p className="text-[11px] text-slate-600 leading-relaxed">
                      {activeProduct.overview}
                    </p>

                    {activeProduct.key_features && activeProduct.key_features.length > 0 && (
                      <div className="pt-1 border-t border-indigo-100/80 space-y-1">
                        <span className="text-[9px] font-bold text-slate-400 uppercase tracking-wider block">
                          Key Capabilities:
                        </span>
                        <ul className="space-y-0.5">
                          {activeProduct.key_features.slice(0, 3).map((feat, fIdx) => (
                            <li key={fIdx} className="text-[10px] text-slate-600 flex items-start space-x-1.5">
                              <Check className="w-3 h-3 text-emerald-600 shrink-0 mt-0.5" />
                              <span>{feat}</span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                )}

                {/* Active Demo Video Link */}
                <div className="p-2.5 bg-slate-50 rounded-lg border border-slate-200 space-y-1">
                  <div className="text-[10px] text-slate-500 font-medium flex items-center justify-between">
                    <span>Product Demo Video / Workspace Link:</span>
                    <span className="text-[9px] bg-emerald-50 text-emerald-700 border border-emerald-200 px-1.5 py-0.2 rounded font-bold">
                      Verified
                    </span>
                  </div>
                  <div className="flex items-center justify-between gap-2">
                    <a
                      href={demoUrl || activeProduct?.demo_video_url || 'https://marketplace.adople.ai/'}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-indigo-600 font-mono text-[11px] hover:underline truncate max-w-[220px]"
                    >
                      {demoUrl || activeProduct?.demo_video_url || 'https://marketplace.adople.ai/'}
                    </a>
                    <a
                      href={demoUrl || activeProduct?.demo_video_url || 'https://marketplace.adople.ai/'}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="px-2 py-1 bg-white border border-slate-200 text-slate-700 hover:text-indigo-600 rounded text-[10px] font-bold shrink-0 flex items-center space-x-1 shadow-2xs"
                    >
                      <ExternalLink className="w-2.5 h-2.5" />
                      <span>Preview</span>
                    </a>
                  </div>
                </div>

                {/* Embed into Message Action */}
                <div className="pt-1">
                  <button
                    onClick={() => {
                      const linkToEmbed = demoUrl || activeProduct?.demo_video_url || 'https://marketplace.adople.ai/';
                      if (draftMessage.includes(linkToEmbed)) {
                        setToastMessage({ text: 'Demo link is already in this message draft.', type: 'info' });
                        setTimeout(() => setToastMessage(null), 3000);
                        return;
                      }
                      setDraftMessage((prev) => `${prev.trim()}\n\nInteractive Demo Preview: ${linkToEmbed}`);
                      setDemoStatus('Attached');
                      setToastMessage({ text: 'Product demo link embedded into outreach draft.', type: 'success' });
                      setTimeout(() => setToastMessage(null), 3000);
                    }}
                    className="w-full py-1.5 bg-emerald-50 text-emerald-700 hover:bg-emerald-100 border border-emerald-200 text-xs font-semibold rounded-lg transition-colors flex items-center justify-center space-x-1.5"
                  >
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                    <span>Embed Demo Video Link into Draft</span>
                  </button>
                </div>
              </div>
            </div>

            {/* Right Panel: Outreach Details (Read View OR Composer View) (7 Cols) */}
            <div className="lg:col-span-7 space-y-4">
              <div className="bg-white p-5 rounded-xl border border-slate-200/90 shadow-2xs space-y-4 text-xs">
                {/* Mode A: Contact has already received outreach and user is NOT actively editing */}
                {activeContactOutreach?.hasOutreach && !isEditingExisting ? (
                  <div className="space-y-4">
                    {/* Status & Review Header */}
                    <div className="p-3 bg-slate-50 border border-slate-200 rounded-lg flex items-start justify-between">
                      <div className="space-y-1">
                        <div className="flex items-center space-x-2">
                          <span
                            className={`font-bold text-xs uppercase px-2 py-0.5 rounded-full ${
                              activeContactOutreach.status.toLowerCase().includes('ready') ||
                              activeContactOutreach.status.toLowerCase().includes('approved')
                                ? 'bg-emerald-100 text-emerald-800'
                                : 'bg-amber-100 text-amber-800'
                            }`}
                          >
                            {activeContactOutreach.status}
                          </span>
                          <span className="text-[11px] text-slate-500">
                            Channel: <strong>{activeContactOutreach.channel.toUpperCase()}</strong>
                          </span>
                        </div>
                        <div className="text-[11px] text-slate-600">
                          <strong>Timestamp:</strong> {activeContactOutreach.submitted_date}
                        </div>
                        {activeContactOutreach.review_feedback && (
                          <div className="text-[11px] text-indigo-900 font-medium bg-indigo-50/70 p-2 rounded mt-1">
                            <strong>Reviewer Note:</strong> {activeContactOutreach.review_feedback}
                          </div>
                        )}
                      </div>

                      <button
                        onClick={handleCopy}
                        className="px-2.5 py-1 text-xs font-semibold text-slate-700 bg-white border border-slate-200 hover:bg-slate-50 rounded shadow-2xs flex items-center space-x-1"
                      >
                        {copied ? <Check className="w-3.5 h-3.5 text-emerald-600" /> : <Copy className="w-3.5 h-3.5" />}
                        <span>{copied ? 'Copied!' : 'Copy Content'}</span>
                      </button>
                    </div>

                    {/* Recipient Email Info */}
                    {activeContactOutreach.channel === 'email' && (
                      <div className="space-y-1">
                        <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">Recipient Email</div>
                        <div className="p-2.5 bg-slate-50 rounded-lg border border-slate-200 font-medium text-slate-900 text-xs font-mono">
                          {activeContact.email}
                        </div>
                      </div>
                    )}

                    {/* Email Subject Line */}
                    {activeContactOutreach.channel === 'email' && (
                      <div className="space-y-1">
                        <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">Subject</div>
                        <div className="p-2.5 bg-slate-50 rounded-lg border border-slate-200 font-medium text-slate-900 text-xs">
                          {subject || activeContactOutreach.subject}
                        </div>
                      </div>
                    )}

                    {/* Email Content Box */}
                    <div className="space-y-1.5">
                      <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
                        Outreach Message Content
                      </div>
                      <div className="p-4 bg-slate-50 rounded-lg border border-slate-200 font-sans text-xs text-slate-800 leading-relaxed whitespace-pre-wrap">
                        {activeContactOutreach.draft_body}
                      </div>
                    </div>

                    {/* Safety Governance Note */}
                    <div className="p-3 bg-emerald-50/60 rounded-lg border border-emerald-200/80 flex items-start space-x-2 text-[11px] text-emerald-900">
                      <ShieldCheck className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
                      <div>
                        <strong>Safety Governance Enforced:</strong> This message has been verified against observed buying signals and placed under strict approval review before external transmission.
                      </div>
                    </div>

                    {/* Action Bar */}
                    <div className="pt-2 flex items-center justify-between border-t border-slate-100">
                      <div className="flex items-center space-x-2">
                        <button
                          onClick={() => navigate('/research/approvals')}
                          className="px-3 py-1.5 text-xs font-semibold text-indigo-700 bg-indigo-50 hover:bg-indigo-100 rounded-lg transition-colors flex items-center space-x-1"
                        >
                          <CheckCircle2 className="w-3.5 h-3.5" />
                          <span>View in Approval Center</span>
                        </button>

                        <button
                          onClick={() => {
                            if (confirm(`Delete outreach record for ${activeContact.full_name}?`)) {
                              deleteOutreachMutation.mutate({
                                approvalId: activeContactOutreach.approval_id || undefined,
                                contactId: activeContact.contact_id,
                              });
                            }
                          }}
                          disabled={deleteOutreachMutation.isPending}
                          className="px-3 py-1.5 text-xs font-semibold text-rose-700 bg-rose-50 hover:bg-rose-100 border border-rose-200 rounded-lg transition-colors flex items-center space-x-1"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                          <span>Delete Outreach</span>
                        </button>
                      </div>

                      <div className="flex items-center space-x-2">
                        {activeContactOutreach.status.toLowerCase().includes('ready') && activeContactOutreach.approval_id && (
                          <button
                            onClick={() => sendOutreachMutation.mutate(activeContactOutreach.approval_id!)}
                            disabled={sendOutreachMutation.isPending}
                            className="px-3.5 py-1.5 text-xs font-semibold text-white bg-emerald-600 hover:bg-emerald-700 rounded-lg shadow-2xs transition-colors flex items-center space-x-1.5"
                          >
                            <Send className="w-3.5 h-3.5" />
                            <span>{sendOutreachMutation.isPending ? 'Sending...' : 'Send Email Now (Outlook)'}</span>
                          </button>
                        )}

                        <button
                          onClick={() => setIsEditingExisting(true)}
                          className="px-3.5 py-1.5 text-xs font-semibold text-white bg-[#201D6E] hover:bg-[#1a1758] rounded-lg transition-colors flex items-center space-x-1"
                        >
                          <span>Revise / Edit Draft</span>
                          <ChevronRight className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </div>
                  </div>
                ) : (
                  /* Mode B: Composer View (for creating new outreach OR editing existing) */
                  <div className="space-y-4">
                    {/* Channel Selector + Status */}
                    <div className="flex items-center justify-between pb-3 border-b border-slate-100">
                      <div className="flex items-center space-x-2">
                        <span className="font-semibold text-slate-700">Outreach Channel:</span>
                        <div className="flex items-center space-x-1 bg-slate-100 p-0.5 rounded-lg border border-slate-200">
                          <button
                            onClick={() => setChannel('email')}
                            className={`px-3 py-1 rounded text-[11px] font-semibold transition-colors ${
                              channel === 'email' ? 'bg-white text-slate-900 shadow-2xs' : 'text-slate-500'
                            }`}
                          >
                            Email (Outlook)
                          </button>
                          <button
                            onClick={() => setChannel('sms')}
                            className={`px-3 py-1 rounded text-[11px] font-semibold transition-colors ${
                              channel === 'sms' ? 'bg-white text-slate-900 shadow-2xs' : 'text-slate-500'
                            }`}
                          >
                            SMS (Short Message)
                          </button>
                        </div>
                      </div>

                      <span className="bg-amber-50 text-amber-800 border border-amber-200 rounded-full px-2.5 py-0.5 text-[10px] font-semibold">
                        Mode: {activeContactOutreach?.hasOutreach ? 'EDITING OUTREACH' : 'NEW COMPOSER'}
                      </span>
                    </div>

                    {/* Recipient Email Address (Editable) */}
                    {channel === 'email' && (
                      <div className="space-y-1">
                        <label className="text-[11px] font-semibold text-slate-600 block">
                          Recipient Email Address (Outlook Destination)
                        </label>
                        <input
                          type="email"
                          value={recipientEmail}
                          onChange={(e) => setRecipientEmail(e.target.value)}
                          placeholder="e.g. name@company.com"
                          className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg text-xs font-medium text-slate-800 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                        />
                      </div>
                    )}

                    {/* Email Subject Line */}
                    {channel === 'email' && (
                      <div className="space-y-1">
                        <label className="text-[11px] font-semibold text-slate-600 block">Email Subject</label>
                        <input
                          type="text"
                          value={subject}
                          onChange={(e) => setSubject(e.target.value)}
                          className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg text-xs font-medium text-slate-800 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                        />
                      </div>
                    )}

                    {/* Message Content Textarea */}
                    <div className="space-y-1.5">
                      <div className="flex items-center justify-between">
                        <label className="text-[11px] font-semibold text-slate-700">
                          Personalized Message Content (Editable)
                        </label>
                        <span className="text-[11px] text-slate-400 font-mono">
                          {draftMessage.length} characters {channel === 'sms' ? '(SMS Limit: 320)' : ''}
                        </span>
                      </div>
                      <textarea
                        rows={9}
                        value={draftMessage}
                        onChange={(e) => setDraftMessage(e.target.value)}
                        className="w-full p-3.5 bg-slate-50 border border-slate-200 rounded-lg text-xs text-slate-800 leading-relaxed font-sans focus:outline-none focus:ring-1 focus:ring-indigo-500 focus:bg-white transition-colors"
                        placeholder="Compose or review outreach message..."
                      />
                    </div>

                    {/* Quality & Safety Governance Warning */}
                    <div className="p-3 bg-slate-50 rounded-lg border border-slate-200/80 flex items-start space-x-2 text-[11px] text-slate-600">
                      <ShieldCheck className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
                      <div>
                        <strong>Safety Governance:</strong> This message uses verified buying signal facts. Submitting places the message into the <strong>Approval Center</strong> for sales rep review before any dispatch.
                      </div>
                    </div>

                    {/* Action Buttons */}
                    <div className="pt-2 flex flex-col sm:flex-row items-center justify-between gap-3 border-t border-slate-100">
                      <button
                        onClick={handleRegenerate}
                        className="px-3 py-2 text-xs font-semibold text-slate-700 bg-white border border-slate-200 hover:bg-slate-50 rounded-lg shadow-2xs transition-colors flex items-center space-x-1.5"
                      >
                        <RotateCw className="w-3.5 h-3.5 text-slate-500" />
                        <span>Regenerate Draft with AI</span>
                      </button>

                      <div className="flex items-center space-x-2.5 w-full sm:w-auto">
                        <button
                          onClick={() => {
                            setToastMessage({ text: 'Draft saved locally.', type: 'info' });
                            setTimeout(() => setToastMessage(null), 2500);
                          }}
                          className="px-3.5 py-2 text-xs font-semibold text-slate-700 bg-slate-100 hover:bg-slate-200 rounded-lg transition-colors flex items-center space-x-1.5"
                        >
                          <Save className="w-3.5 h-3.5" />
                          <span>Save Draft</span>
                        </button>

                        <button
                          onClick={() => submitApprovalMutation.mutate()}
                          disabled={submitApprovalMutation.isPending}
                          className="px-4 py-2 text-xs font-semibold text-white bg-[#201D6E] hover:bg-[#1a1758] rounded-lg shadow-2xs transition-colors disabled:opacity-60 flex items-center space-x-1.5"
                        >
                          <Send className="w-3.5 h-3.5" />
                          <span>{submitApprovalMutation.isPending ? 'Submitting...' : 'Submit for Approval'}</span>
                        </button>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      ) : (
        /* Centralized Outreach Directory Table (All Companies & Contacts) */
        <div className="space-y-4">
          {/* Status Filter Tabs & Company Dropdown */}
          <div className="p-3.5 bg-white rounded-xl border border-slate-200/90 shadow-2xs flex flex-col lg:flex-row lg:items-center justify-between gap-3 text-xs">
            {/* Status Tabs */}
            <div className="flex flex-wrap items-center gap-1.5">
              {[
                { key: 'all', label: `All Decision-Makers (${totalContactsCount})` },
                { key: 'ready', label: `Ready for Outreach (${readyOutreachCount})` },
                { key: 'pending', label: `Pending Approval (${pendingApprovalCount})` },
                { key: 'not_sent', label: `No Outreach Yet (${notSentCount})` },
              ].map((tab) => (
                <button
                  key={tab.key}
                  onClick={() => setStatusTab(tab.key as any)}
                  className={`px-3 py-1.5 rounded-lg font-semibold text-xs transition-colors ${
                    statusTab === tab.key
                      ? 'bg-[#201D6E] text-white shadow-2xs'
                      : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                  }`}
                >
                  {tab.label}
                </button>
              ))}
            </div>

            {/* Search & Company Filter */}
            <div className="flex flex-wrap items-center gap-2.5">
              {/* Company Filter Dropdown */}
              <div className="flex items-center space-x-1.5">
                <span className="text-slate-400 font-medium">Company:</span>
                <select
                  value={selectedCompany}
                  onChange={(e) => setSelectedCompany(e.target.value)}
                  className="px-2.5 py-1.5 bg-slate-50 border border-slate-200 rounded-lg text-xs font-bold text-slate-800 focus:outline-none focus:ring-1 focus:ring-indigo-500 cursor-pointer max-w-[190px] truncate"
                >
                  <option value="all">All Companies ({companies.length})</option>
                  {companies.map((comp) => (
                    <option key={comp.account_id} value={comp.account_id}>
                      {comp.company_name}
                    </option>
                  ))}
                </select>
              </div>

              {/* Search Bar */}
              <div className="relative">
                <Search className="w-3.5 h-3.5 text-slate-400 absolute left-2.5 top-2.5" />
                <input
                  type="text"
                  placeholder="Search contacts or company..."
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  className="pl-8 pr-3 py-1.5 bg-slate-50 border border-slate-200 rounded-lg text-xs text-slate-800 placeholder:text-slate-400 focus:outline-none focus:ring-1 focus:ring-indigo-500 w-48 sm:w-56"
                />
              </div>

              {(selectedCompany !== 'all' || search) && (
                <button
                  onClick={() => {
                    setSelectedCompany('all');
                    setSearch('');
                  }}
                  className="text-xs text-indigo-600 hover:text-indigo-800 font-semibold"
                >
                  Reset
                </button>
              )}
            </div>
          </div>

          {/* Centralized Outreach Table */}
          <div className="bg-white rounded-xl border border-slate-200/90 shadow-2xs overflow-hidden text-xs">
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse min-w-[1000px]">
                <thead>
                  <tr className="border-b border-slate-100 bg-slate-50/60 text-[10px] font-bold text-slate-400 uppercase tracking-wider">
                    <th className="py-3 px-4 w-52">TARGET DECISION-MAKER</th>
                    <th className="py-3 px-4 w-48">COMPANY</th>
                    <th className="py-3 px-3 w-40">OUTREACH STATUS</th>
                    <th className="py-3 px-3 w-32">CHANNEL</th>
                    <th className="py-3 px-3 w-36">TIMESTAMP</th>
                    <th className="py-3 px-3 w-36">DEMO PREVIEW</th>
                    <th className="py-3 px-4 w-40 text-right">ACTION</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {filteredContacts.map((contact) => {
                    const outreach = getOutreachForContact(contact);
                    const isSent =
                      outreach.hasOutreach &&
                      outreach.status.toLowerCase().includes('sent');
                    const isReady =
                      outreach.hasOutreach &&
                      (outreach.status.toLowerCase().includes('ready') || outreach.status.toLowerCase().includes('approved'));
                    const isPending =
                      outreach.hasOutreach && outreach.status.toLowerCase().includes('pending');

                    return (
                      <tr key={contact.contact_id} className="hover:bg-slate-50/70 transition-colors">
                        {/* Target Contact */}
                        <td className="py-3.5 px-4 align-middle">
                          <div className="flex items-center space-x-2">
                            <span className="font-bold text-slate-900 text-xs">{contact.full_name}</span>
                            {contact.is_primary && (
                              <span className="bg-[#201D6E] text-white rounded px-1.5 py-0.2 text-[9px] font-bold flex items-center space-x-0.5">
                                <Star className="w-2.5 h-2.5 fill-current" />
                                <span>Primary</span>
                              </span>
                            )}
                          </div>
                          <div className="text-[11px] text-slate-500">{contact.job_title}</div>
                          <div className="text-[10px] text-slate-400 font-mono mt-0.5">{contact.email}</div>
                        </td>

                        {/* Company */}
                        <td className="py-3.5 px-4 align-middle">
                          <div className="font-semibold text-slate-900 text-xs">{contact.company_name}</div>
                          <div className="text-[10px] text-slate-400 font-mono">{contact.company_domain}</div>
                        </td>

                        {/* Outreach Status */}
                        <td className="py-3.5 px-3 align-middle">
                          {isSent ? (
                            <span className="bg-emerald-50 text-emerald-700 border border-emerald-200 rounded-full px-2.5 py-0.5 text-[10px] font-semibold flex items-center space-x-1 w-fit">
                              <CheckCircle2 className="w-3 h-3 text-emerald-600" />
                              <span>Sent (Dispatched)</span>
                            </span>
                          ) : isReady ? (
                            <span className="bg-emerald-50 text-emerald-700 border border-emerald-200 rounded-full px-2.5 py-0.5 text-[10px] font-semibold flex items-center space-x-1 w-fit">
                              <CheckCircle2 className="w-3 h-3" />
                              <span>Ready for Outreach</span>
                            </span>
                          ) : isPending ? (
                            <span className="bg-amber-50 text-amber-800 border border-amber-200 rounded-full px-2.5 py-0.5 text-[10px] font-semibold flex items-center space-x-1 w-fit">
                              <Clock className="w-3 h-3" />
                              <span>Pending Review</span>
                            </span>
                          ) : (
                            <span className="bg-slate-100 text-slate-600 border border-slate-200 rounded-full px-2.5 py-0.5 text-[10px] font-medium flex items-center space-x-1 w-fit">
                              <AlertCircle className="w-3 h-3 text-slate-400" />
                              <span>Not Sent (Pending)</span>
                            </span>
                          )}
                        </td>

                        {/* Channel */}
                        <td className="py-3.5 px-3 align-middle">
                          {outreach.hasOutreach ? (
                            <span className="bg-slate-100 text-slate-700 font-semibold px-2 py-0.5 rounded text-[10px] uppercase">
                              {outreach.channel}
                            </span>
                          ) : (
                            <span className="text-slate-400 text-[11px] italic">Not selected</span>
                          )}
                        </td>

                        {/* Timestamp */}
                        <td className="py-3.5 px-3 align-middle text-slate-500 text-[11px]">
                          {outreach.submitted_date}
                        </td>

                        {/* Demo Status */}
                        <td className="py-3.5 px-3 align-middle">
                          <span
                            className={`px-2 py-0.5 rounded text-[10px] font-medium ${
                              outreach.demo_status.toLowerCase() === 'ready'
                                ? 'bg-emerald-50 text-emerald-700 border border-emerald-100'
                                : 'bg-slate-50 text-slate-500'
                            }`}
                          >
                            {outreach.demo_status}
                          </span>
                        </td>

                        {/* Action */}
                        <td className="py-3.5 px-4 align-middle text-right">
                          {outreach.hasOutreach ? (
                            <div className="flex items-center justify-end space-x-1.5">
                              <button
                                onClick={() => {
                                  setSelectedContactId(contact.contact_id);
                                  setIsEditingExisting(false);
                                }}
                                className="px-2.5 py-1.5 text-xs font-semibold text-indigo-700 bg-indigo-50 hover:bg-indigo-100 rounded-lg transition-colors inline-flex items-center space-x-1"
                              >
                                <Eye className="w-3.5 h-3.5" />
                                <span>View Outreach</span>
                              </button>
                              <button
                                onClick={() => {
                                  if (confirm(`Delete outreach record for ${contact.full_name}?`)) {
                                    deleteOutreachMutation.mutate({
                                      approvalId: outreach.approval_id || undefined,
                                      contactId: contact.contact_id,
                                    });
                                  }
                                }}
                                disabled={deleteOutreachMutation.isPending}
                                title="Delete Outreach Record"
                                className="p-1.5 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded-lg border border-transparent hover:border-rose-200 transition-colors"
                              >
                                <Trash2 className="w-3.5 h-3.5" />
                              </button>
                            </div>
                          ) : (
                            <button
                              onClick={() => {
                                setSelectedContactId(contact.contact_id);
                                setIsEditingExisting(true);
                              }}
                              className="px-3 py-1.5 text-xs font-semibold text-white bg-[#201D6E] hover:bg-[#1a1758] rounded-lg shadow-2xs transition-colors inline-flex items-center space-x-1"
                            >
                              <Plus className="w-3.5 h-3.5" />
                              <span>Create Outreach</span>
                            </button>
                          )}
                        </td>
                      </tr>
                    );
                  })}

                  {filteredContacts.length === 0 && (
                    <tr>
                      <td colSpan={7} className="py-12 text-center text-slate-500 text-xs">
                        No contacts found matching the selected filters.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>

            {/* Table Footer */}
            <div className="p-3 border-t border-slate-100 flex items-center justify-between text-xs text-slate-500 bg-white">
              <div>
                Showing {filteredContacts.length} of {totalContactsCount} decision-makers across all companies
              </div>
              <div className="text-slate-400">Strict Human-in-the-Loop Governance Enforced</div>
            </div>
          </div>
        </div>
      )}
        </>
      )}

      {/* Add Contact Modal */}
      <Modal
        isOpen={isAddModalOpen}
        onClose={() => {
          setIsAddModalOpen(false);
          setFormError(null);
        }}
        title="Add Decision-Maker Contact"
        description="Manually record a new decision-maker and compose an outreach draft immediately."
        maxWidth="lg"
      >
        <div className="p-6 space-y-4 text-xs">
          {formError && (
            <div className="p-3 bg-rose-50 border border-rose-200 text-rose-700 rounded-lg flex items-center space-x-2">
              <AlertCircle className="w-4 h-4 shrink-0 text-rose-600" />
              <span>{formError}</span>
            </div>
          )}

          {/* Company Selection */}
          <div className="space-y-1.5">
            <label className="font-semibold text-slate-700 block">Target Company *</label>
            <select
              value={newAccountId || (companies && companies.length > 0 ? companies[0].account_id : '')}
              onChange={(e) => setNewAccountId(e.target.value)}
              className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg font-medium text-slate-800 focus:outline-none focus:ring-1 focus:ring-indigo-500"
            >
              {companies?.map((comp) => (
                <option key={comp.account_id} value={comp.account_id}>
                  {comp.company_name} ({comp.domain})
                </option>
              ))}
              <option value="new">+ Add to New Company</option>
            </select>
          </div>

          {newAccountId === 'new' && (
            <div className="space-y-1.5">
              <label className="font-semibold text-slate-700 block">Company Name *</label>
              <input
                type="text"
                value={newCompanyName}
                onChange={(e) => setNewCompanyName(e.target.value)}
                placeholder="e.g. Acme Corporation"
                className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg text-slate-800 focus:outline-none focus:ring-1 focus:ring-indigo-500"
              />
            </div>
          )}

          {/* Full Name & Job Title */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <label className="font-semibold text-slate-700 block">Full Name *</label>
              <input
                type="text"
                value={newFullName}
                onChange={(e) => setNewFullName(e.target.value)}
                placeholder="e.g. Sarah Connor"
                className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg text-slate-800 focus:outline-none focus:ring-1 focus:ring-indigo-500"
              />
            </div>

            <div className="space-y-1.5">
              <label className="font-semibold text-slate-700 block">Job Title</label>
              <input
                type="text"
                value={newJobTitle}
                onChange={(e) => setNewJobTitle(e.target.value)}
                placeholder="e.g. VP of Engineering"
                className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg text-slate-800 focus:outline-none focus:ring-1 focus:ring-indigo-500"
              />
            </div>
          </div>

          {/* Email Address & Department */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <label className="font-semibold text-slate-700 block">Email Address (for Live Outreach) *</label>
              <input
                type="email"
                value={newEmail}
                onChange={(e) => setNewEmail(e.target.value)}
                placeholder="e.g. sarah.connor@acme.com"
                className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg text-slate-800 focus:outline-none focus:ring-1 focus:ring-indigo-500"
              />
              <span className="text-[10px] text-slate-400 block">
                Enter a real email to dispatch via Microsoft Outlook.
              </span>
            </div>

            <div className="space-y-1.5">
              <label className="font-semibold text-slate-700 block">Department</label>
              <input
                type="text"
                value={newDepartment}
                onChange={(e) => setNewDepartment(e.target.value)}
                placeholder="e.g. Engineering, AI, Operations"
                className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg text-slate-800 focus:outline-none focus:ring-1 focus:ring-indigo-500"
              />
            </div>
          </div>

          {/* Phone & LinkedIn */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <label className="font-semibold text-slate-700 block">Phone (Optional)</label>
              <input
                type="text"
                value={newPhone}
                onChange={(e) => setNewPhone(e.target.value)}
                placeholder="e.g. +1 555-0199"
                className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg text-slate-800 focus:outline-none focus:ring-1 focus:ring-indigo-500"
              />
            </div>

            <div className="space-y-1.5">
              <label className="font-semibold text-slate-700 block">LinkedIn URL (Optional)</label>
              <input
                type="text"
                value={newLinkedin}
                onChange={(e) => setNewLinkedin(e.target.value)}
                placeholder="e.g. https://linkedin.com/in/sarahconnor"
                className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg text-slate-800 focus:outline-none focus:ring-1 focus:ring-indigo-500"
              />
            </div>
          </div>

          {/* Modal Actions */}
          <div className="pt-3 border-t border-slate-100 flex items-center justify-between">
            <button
              type="button"
              onClick={() => setIsAddModalOpen(false)}
              className="px-3.5 py-2 text-xs font-semibold text-slate-600 hover:text-slate-800 hover:bg-slate-100 rounded-lg transition-colors"
            >
              Cancel
            </button>

            <button
              type="button"
              onClick={() => createContactMutation.mutate()}
              disabled={createContactMutation.isPending}
              className="px-4 py-2 text-xs font-semibold text-white bg-[#201D6E] hover:bg-[#1a1758] rounded-lg shadow-2xs transition-colors flex items-center space-x-1.5"
            >
              <Send className="w-3.5 h-3.5" />
              <span>{createContactMutation.isPending ? 'Saving...' : 'Save & Set Outreach'}</span>
            </button>
          </div>
        </div>
      </Modal>

      {/* 5. Sync Marketplace Product Modal */}
      <Modal
        isOpen={isSyncModalOpen}
        onClose={() => setIsSyncModalOpen(false)}
        title="Sync Product from marketplace.adople.ai"
      >
        <div className="space-y-4 text-xs">
          <p className="text-slate-600 leading-relaxed text-[11px]">
            Enter a product URL from <strong>https://marketplace.adople.ai/</strong> to extract the product name,
            overview, key features, and demo video link directly into the database.
          </p>

          <div className="space-y-1.5">
            <label className="font-semibold text-slate-700 block">Marketplace Product URL</label>
            <input
              type="text"
              value={syncUrlInput}
              onChange={(e) => setSyncUrlInput(e.target.value)}
              placeholder="e.g. https://marketplace.adople.ai/products/voice-agent"
              className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg text-slate-800 font-mono text-xs focus:outline-none focus:ring-1 focus:ring-indigo-500"
            />
          </div>

          <div className="pt-3 border-t border-slate-100 flex items-center justify-between">
            <button
              type="button"
              onClick={() => setIsSyncModalOpen(false)}
              className="px-3.5 py-2 text-xs font-semibold text-slate-600 hover:text-slate-800 hover:bg-slate-100 rounded-lg transition-colors"
            >
              Cancel
            </button>

            <button
              type="button"
              onClick={() => syncProductMutation.mutate(syncUrlInput)}
              disabled={syncProductMutation.isPending || !syncUrlInput.trim()}
              className="px-4 py-2 text-xs font-semibold text-white bg-[#201D6E] hover:bg-[#1a1758] rounded-lg shadow-2xs transition-colors flex items-center space-x-1.5 disabled:opacity-60"
            >
              <RotateCw className={`w-3.5 h-3.5 ${syncProductMutation.isPending ? 'animate-spin' : ''}`} />
              <span>{syncProductMutation.isPending ? 'Extracting & Saving...' : 'Extract & Save to Database'}</span>
            </button>
          </div>
        </div>
      </Modal>
    </div>
  );
};
