import React, { useState } from 'react';
import { useParams, useNavigate, useSearchParams } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Users,
  Search,
  CheckCircle2,
  AlertCircle,
  ExternalLink,
  ShieldAlert,
  ShieldCheck,
  Star,
  Sparkles,
  Send,
  Linkedin,
  Mail,
  Phone,
  Building2,
  ChevronDown,
  Filter,
  Check,
  UserPlus,
} from 'lucide-react';
import { apiClient } from '@/lib/apiClient';
import { StandardResponse } from '@/types/api';
import { LoadingState } from '@/components/ui/FeedbackStates';
import { Modal } from '@/components/ui/Modal';

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

export const ContactDiscoveryPage: React.FC = () => {
  const { accountId } = useParams<{ accountId?: string }>();
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  // Initial company filter from query param ?company=... or route param /:accountId
  const initialCompany = searchParams.get('company') || accountId || 'all';
  const [selectedCompany, setSelectedCompany] = useState<string>(initialCompany);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [primaryContactId, setPrimaryContactId] = useState<string | null>(null);
  const [toastMessage, setToastMessage] = useState<{ text: string; type: 'success' | 'info' } | null>(null);

  // 1. Fetch All Contacts across all companies
  const { data: allContacts, isLoading: contactsLoading } = useQuery({
    queryKey: ['research', 'contacts'],
    queryFn: async () => {
      const res = await apiClient.get<StandardResponse<ContactItem[]>>('/research/contacts');
      return res.data.data;
    },
  });

  // 2. Fetch Companies list for company-wise filter dropdown
  const { data: companies, isLoading: companiesLoading } = useQuery({
    queryKey: ['research', 'companies'],
    queryFn: async () => {
      const res = await apiClient.get<StandardResponse<CompanyItem[]>>('/research/companies');
      return res.data.data;
    },
  });

  // 3. Mutation: Update Contact Status Directly
  const updateStatusMutation = useMutation({
    mutationFn: async ({ contactId, newStatus }: { contactId: string; newStatus: string }) => {
      const isSuppressed = newStatus === 'suppressed';
      const isVerified = newStatus === 'verified' || newStatus === 'eligible';
      const res = await apiClient.patch<StandardResponse<any>>(`/research/contacts/${contactId}/status`, {
        contact_eligibility: newStatus,
        verification_status: isVerified ? 'verified' : isSuppressed ? 'suppressed' : 'unverified',
      });
      return res.data.data;
    },
    onMutate: async ({ contactId, newStatus }) => {
      // Optimistic cache update
      await queryClient.cancelQueries({ queryKey: ['research', 'contacts'] });
      const previousContacts = queryClient.getQueryData<ContactItem[]>(['research', 'contacts']);

      queryClient.setQueryData<ContactItem[]>(['research', 'contacts'], (old) => {
        if (!old) return old;
        return old.map((c) =>
          c.contact_id === contactId
            ? {
                ...c,
                contact_eligibility: newStatus,
                verification_status:
                  newStatus === 'verified' || newStatus === 'eligible'
                    ? 'verified'
                    : newStatus === 'suppressed'
                    ? 'suppressed'
                    : c.verification_status,
              }
            : c
        );
      });

      return { previousContacts };
    },
    onError: (_err, _vars, context) => {
      if (context?.previousContacts) {
        queryClient.setQueryData(['research', 'contacts'], context.previousContacts);
      }
    },
    onSuccess: (_data, variables) => {
      const contactObj = allContacts?.find((c) => c.contact_id === variables.contactId);
      const name = contactObj ? contactObj.full_name : 'Contact';
      const formatted =
        variables.newStatus === 'suppressed'
          ? 'Suppressed (Do Not Contact)'
          : variables.newStatus === 'verified'
          ? 'Verified'
          : variables.newStatus === 'needs_review'
          ? 'Needs Review'
          : 'Eligible';

      setToastMessage({
        text: `Status for ${name} updated directly to "${formatted}".`,
        type: 'success',
      });
      setTimeout(() => setToastMessage(null), 3500);

      // Invalidate to synchronize
      queryClient.invalidateQueries({ queryKey: ['research', 'contacts'] });
      queryClient.invalidateQueries({ queryKey: ['research', 'company'] });
    },
  });

  // 4. Mutation: Set Primary Decision-Maker
  const setPrimaryMutation = useMutation({
    mutationFn: async (contact: ContactItem) => {
      setPrimaryContactId(contact.contact_id);
      setToastMessage({
        text: `${contact.full_name} designated as primary decision-maker for ${contact.company_name}.`,
        type: 'info',
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
    mutationFn: async ({ openOutreach }: { openOutreach: boolean }) => {
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
      return { contact: res.data.data, openOutreach };
    },
    onSuccess: ({ contact, openOutreach }) => {
      queryClient.invalidateQueries({ queryKey: ['research', 'contacts'] });
      queryClient.invalidateQueries({ queryKey: ['research', 'companies'] });
      setIsAddModalOpen(false);
      setNewFullName('');
      setNewEmail('');
      setNewJobTitle('');
      setNewPhone('');
      setNewLinkedin('');
      setFormError(null);

      if (openOutreach) {
        navigate(`/research/outreach/${contact.account_id}?contact=${contact.contact_id}`);
      } else {
        setToastMessage({
          text: `Contact ${contact.full_name} added successfully!`,
          type: 'success',
        });
        setTimeout(() => setToastMessage(null), 4000);
      }
    },
    onError: (err: any) => {
      setFormError(err?.message || err?.response?.data?.detail || 'Failed to add contact.');
    },
  });

  if (contactsLoading || companiesLoading || !allContacts || !companies) {
    return <LoadingState message="Loading contacts directory across enterprise accounts..." />;
  }

  // Handle company filter change
  const handleCompanyChange = (companyId: string) => {
    setSelectedCompany(companyId);
    if (companyId === 'all') {
      searchParams.delete('company');
      setSearchParams(searchParams);
    } else {
      setSearchParams({ company: companyId });
    }
  };

  // Filter contacts
  const filteredContacts = allContacts.filter((c) => {
    // 1. Company Filter
    const matchesCompany =
      selectedCompany === 'all' ||
      c.account_id === selectedCompany ||
      c.company_name.toLowerCase() === selectedCompany.toLowerCase();

    // 2. Search Filter
    const query = search.toLowerCase().trim();
    const matchesSearch =
      !query ||
      c.full_name.toLowerCase().includes(query) ||
      c.job_title.toLowerCase().includes(query) ||
      c.email.toLowerCase().includes(query) ||
      c.company_name.toLowerCase().includes(query) ||
      c.company_domain.toLowerCase().includes(query) ||
      c.department.toLowerCase().includes(query);

    // 3. Status Filter
    let matchesStatus = true;
    if (statusFilter !== 'all') {
      if (statusFilter === 'eligible') {
        matchesStatus = c.contact_eligibility === 'eligible';
      } else if (statusFilter === 'verified') {
        matchesStatus = c.verification_status === 'verified';
      } else if (statusFilter === 'suppressed') {
        matchesStatus = c.contact_eligibility === 'suppressed';
      } else if (statusFilter === 'needs_review') {
        matchesStatus =
          c.contact_eligibility === 'needs_review' ||
          c.contact_eligibility === 'test_only_not_authorized' ||
          c.verification_status === 'missing_contact_method';
      }
    }

    return matchesCompany && matchesSearch && matchesStatus;
  });

  // Selected company object (if a specific company is chosen)
  const currentCompanyObj =
    selectedCompany !== 'all' ? companies.find((comp) => comp.account_id === selectedCompany) : null;

  // Counts for KPIs
  const totalContacts = allContacts.length;
  const eligibleCount = allContacts.filter((c) => c.contact_eligibility === 'eligible').length;
  const suppressedCount = allContacts.filter((c) => c.contact_eligibility === 'suppressed').length;
  const uniqueCompaniesCount = new Set(allContacts.map((c) => c.account_id)).size;

  return (
    <div className="space-y-5">
      {/* 1. Header Bar */}
      <div className="flex flex-col md:flex-row md:items-center justify-between pb-3 border-b border-slate-200 gap-3">
        <div>
          <div className="flex items-center space-x-2.5">
            <h1 className="text-xl font-bold tracking-tight text-slate-900">Contact Discovery</h1>
            <span className="bg-indigo-50 text-indigo-700 border border-indigo-200/80 rounded-full px-2.5 py-0.5 text-[10px] font-semibold flex items-center space-x-1">
              <Users className="w-3 h-3" />
              <span>
                {selectedCompany === 'all'
                  ? `All Companies (${totalContacts} Contacts)`
                  : `${currentCompanyObj?.company_name || selectedCompany}`}
              </span>
            </span>
          </div>
          <p className="text-xs text-slate-500 mt-1">
            Identify, verify, and manage decision-makers across all accounts based on buying signal relevance and role hierarchy.
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
            onClick={() => navigate('/research/outreach')}
            className="px-3.5 py-1.5 text-xs font-semibold text-white bg-[#201D6E] hover:bg-[#1a1758] rounded-lg shadow-2xs transition-colors flex items-center space-x-1"
          >
            <Send className="w-3.5 h-3.5" />
            <span>Open Outreach Studio</span>
          </button>
        </div>
      </div>

      {/* Toast Notification */}
      {toastMessage && (
        <div
          className={`p-3 rounded-lg text-xs font-medium flex items-center justify-between border ${
            toastMessage.type === 'success'
              ? 'bg-emerald-50 border-emerald-200 text-emerald-800'
              : 'bg-indigo-50 border-indigo-200 text-indigo-800'
          }`}
        >
          <div className="flex items-center space-x-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-600" />
            <span>{toastMessage.text}</span>
          </div>
          <button
            onClick={() => setToastMessage(null)}
            className="text-xs text-slate-400 hover:text-slate-600 font-semibold"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* 2. KPI Metrics Bar */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-white p-3.5 rounded-xl border border-slate-200/90 shadow-2xs">
          <div className="text-[10px] font-semibold uppercase tracking-wider text-slate-400">Total Contacts</div>
          <div className="text-xl font-bold text-slate-900 mt-0.5">{totalContacts}</div>
          <div className="text-[10px] text-slate-500">Across {uniqueCompaniesCount} companies</div>
        </div>

        <div className="bg-white p-3.5 rounded-xl border border-slate-200/90 shadow-2xs">
          <div className="text-[10px] font-semibold uppercase tracking-wider text-slate-400">Eligible Contacts</div>
          <div className="text-xl font-bold text-emerald-600 mt-0.5">{eligibleCount}</div>
          <div className="text-[10px] text-slate-500">Ready for outreach</div>
        </div>

        <div className="bg-white p-3.5 rounded-xl border border-slate-200/90 shadow-2xs">
          <div className="text-[10px] font-semibold uppercase tracking-wider text-slate-400">Suppressed</div>
          <div className="text-xl font-bold text-rose-600 mt-0.5">{suppressedCount}</div>
          <div className="text-[10px] text-slate-500">Rule of 3 / Opt-out enforced</div>
        </div>

        <div className="bg-white p-3.5 rounded-xl border border-slate-200/90 shadow-2xs">
          <div className="text-[10px] font-semibold uppercase tracking-wider text-slate-400">Active Filter</div>
          <div className="text-sm font-bold text-[#201D6E] mt-1 truncate">
            {selectedCompany === 'all' ? 'All Companies' : currentCompanyObj?.company_name || selectedCompany}
          </div>
          <div className="text-[10px] text-slate-500">
            {filteredContacts.length} contacts displayed
          </div>
        </div>
      </div>

      {/* 3. Recommended Role Matching Guidance Banner */}
      <div className="p-4 bg-indigo-50/50 border border-indigo-100 rounded-xl space-y-1.5 text-xs text-indigo-950">
        <div className="flex items-center space-x-1.5 font-bold text-xs">
          <Sparkles className="w-3.5 h-3.5 text-indigo-600" />
          <span>
            {currentCompanyObj
              ? `Recommended Role Matching for ${currentCompanyObj.company_name}: "${currentCompanyObj.why_now || currentCompanyObj.buying_signal || 'Strategic Technical Scaling'}"`
              : 'Enterprise Role Hierarchy & Decision-Maker Matching'}
          </span>
        </div>
        <p className="text-indigo-800 text-[11px] leading-relaxed">
          Executive targets include: <strong>CTO, VP of Engineering, Director of AI, VP Operations, Head of Document Operations</strong>.
          Suppression rules strictly prevent contact if marked suppressed, unverified, or opted out. You can update any contact&apos;s eligibility directly below.
        </p>
      </div>

      {/* 4. Search and Company-Wise Filter Bar */}
      <div className="p-3 bg-white rounded-xl border border-slate-200/90 shadow-2xs flex flex-col md:flex-row md:items-center justify-between gap-3">
        {/* Search */}
        <div className="relative flex-1 max-w-sm">
          <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-2.5" />
          <input
            type="text"
            placeholder="Search contacts by name, role, email, or company..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-9 pr-3.5 py-1.5 bg-slate-50 border border-slate-200 rounded-lg text-xs text-slate-800 placeholder:text-slate-400 focus:outline-none focus:ring-1 focus:ring-indigo-500"
          />
        </div>

        {/* Company & Status Filters */}
        <div className="flex flex-wrap items-center gap-2.5 text-xs">
          {/* Company Filter Dropdown */}
          <div className="flex items-center space-x-1.5">
            <span className="text-slate-500 font-semibold text-xs whitespace-nowrap flex items-center space-x-1">
              <Building2 className="w-3 h-3 text-slate-400" />
              <span>Company:</span>
            </span>
            <select
              value={selectedCompany}
              onChange={(e) => handleCompanyChange(e.target.value)}
              className="px-2.5 py-1.5 bg-slate-50 border border-slate-200 rounded-lg text-xs font-bold text-slate-800 focus:outline-none focus:ring-1 focus:ring-indigo-500 cursor-pointer max-w-[200px] truncate"
            >
              <option value="all">All Companies ({allContacts.length})</option>
              {companies.map((comp) => {
                const count = allContacts.filter((c) => c.account_id === comp.account_id).length;
                return (
                  <option key={comp.account_id} value={comp.account_id}>
                    {comp.company_name} ({count})
                  </option>
                );
              })}
            </select>
          </div>

          {/* Status Filter */}
          <div className="flex items-center space-x-1.5">
            <span className="text-slate-400 font-medium text-xs whitespace-nowrap">Status:</span>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="px-2.5 py-1.5 bg-slate-50 border border-slate-200 rounded-lg text-xs font-semibold text-slate-700 focus:outline-none focus:ring-1 focus:ring-indigo-500 cursor-pointer"
            >
              <option value="all">All Statuses</option>
              <option value="eligible">Eligible Only</option>
              <option value="verified">Verified Only</option>
              <option value="needs_review">Needs Review / Mock</option>
              <option value="suppressed">Suppressed Only</option>
            </select>
          </div>

          {/* Reset button if filtered */}
          {(selectedCompany !== 'all' || statusFilter !== 'all' || search) && (
            <button
              onClick={() => {
                handleCompanyChange('all');
                setStatusFilter('all');
                setSearch('');
              }}
              className="px-2.5 py-1 text-[11px] font-semibold text-indigo-600 hover:text-indigo-800 hover:bg-indigo-50 rounded transition-colors"
            >
              Reset Filters
            </button>
          )}
        </div>
      </div>

      {/* 5. Centralized Contacts Data Table */}
      <div className="bg-white rounded-xl border border-slate-200/90 shadow-2xs overflow-hidden text-xs">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse min-w-[1050px]">
            <thead>
              <tr className="border-b border-slate-100 bg-slate-50/60 text-[10px] font-bold text-slate-400 uppercase tracking-wider">
                <th className="py-3 px-4 w-48">CONTACT NAME</th>
                <th className="py-3 px-3 w-44">COMPANY</th>
                <th className="py-3 px-3 w-40">JOB TITLE</th>
                <th className="py-3 px-3 w-28">DEPARTMENT</th>
                <th className="py-3 px-2 w-20">SENIORITY</th>
                <th className="py-3 px-4 min-w-[200px]">BUSINESS EMAIL</th>
                <th className="py-3 px-3 w-24">SOURCE</th>
                <th className="py-3 px-3 w-44">STATUS / ELIGIBILITY</th>
                <th className="py-3 px-4 w-32 text-right">ACTIONS</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {filteredContacts.map((c, idx) => {
                const isPrimary =
                  primaryContactId === c.contact_id || (c.is_primary && !primaryContactId);

                // Direct status styling
                const isSuppressed = c.contact_eligibility === 'suppressed';
                const isVerified = c.contact_eligibility === 'verified' || c.verification_status === 'verified';
                const isNeedsReview =
                  c.contact_eligibility === 'needs_review' ||
                  c.contact_eligibility === 'test_only_not_authorized' ||
                  c.contact_eligibility === 'blocked_missing_address';

                return (
                  <tr key={c.contact_id} className="hover:bg-slate-50/70 transition-colors">
                    {/* Contact Name */}
                    <td className="py-3.5 px-4 align-middle">
                      <div className="flex items-center space-x-2">
                        <span className="font-bold text-slate-900 text-xs">{c.full_name}</span>
                        {isPrimary && (
                          <span className="bg-[#201D6E] text-white rounded px-1.5 py-0.2 text-[9px] font-bold flex items-center space-x-0.5">
                            <Star className="w-2.5 h-2.5 fill-current" />
                            <span>Primary</span>
                          </span>
                        )}
                      </div>
                      {c.linkedin && (
                        <a
                          href={c.linkedin}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-[10px] text-indigo-600 hover:text-indigo-800 flex items-center space-x-0.5 mt-0.5"
                        >
                          <Linkedin className="w-2.5 h-2.5" />
                          <span>LinkedIn Profile</span>
                        </a>
                      )}
                    </td>

                    {/* Company */}
                    <td className="py-3.5 px-3 align-middle">
                      <button
                        onClick={() => navigate(`/research/company/${c.account_id}`)}
                        className="text-left group"
                      >
                        <div className="font-semibold text-slate-800 group-hover:text-indigo-600 transition-colors text-xs flex items-center space-x-1">
                          <span>{c.company_name}</span>
                          <ExternalLink className="w-2.5 h-2.5 opacity-0 group-hover:opacity-100 text-indigo-500 transition-opacity" />
                        </div>
                        <div className="text-[10px] text-slate-400 font-mono">{c.company_domain}</div>
                      </button>
                    </td>

                    {/* Job Title & Aligned Pain Point (Agent 2 Role-to-Pain Mapping) */}
                    <td className="py-3.5 px-3 align-middle">
                      <div className="font-medium text-slate-800 text-xs">{c.job_title}</div>
                      {c.aligned_pain_point && (
                        <div
                          className="text-[10px] text-indigo-700 bg-indigo-50/90 rounded px-1.5 py-0.5 mt-1 border border-indigo-100/80 flex items-center space-x-1 max-w-xs"
                          title={`Agent 2 Aligned Responsibility: ${c.aligned_pain_point}`}
                        >
                          <Sparkles className="w-2.5 h-2.5 text-indigo-500 shrink-0" />
                          <span className="truncate">{c.aligned_pain_point}</span>
                        </div>
                      )}
                    </td>

                    {/* Department */}
                    <td className="py-3.5 px-3 align-middle text-slate-500">
                      <span className="bg-slate-100 text-slate-700 px-2 py-0.5 rounded text-[10px] font-medium">
                        {c.department}
                      </span>
                    </td>

                    {/* Seniority */}
                    <td className="py-3.5 px-2 align-middle">
                      <span className="text-slate-600 font-semibold text-[10px]">
                        {c.seniority}
                      </span>
                    </td>

                    {/* Email & Phone */}
                    <td className="py-3.5 px-4 align-middle">
                      {c.email ? (
                        <div className="flex items-center space-x-1.5 text-slate-700 font-mono text-[11px]">
                          <Mail className="w-3 h-3 text-slate-400 shrink-0" />
                          <span className="truncate">{c.email}</span>
                        </div>
                      ) : (
                        <span className="text-[10px] text-amber-700 italic">No email provided</span>
                      )}
                      {c.phone && (
                        <div className="flex items-center space-x-1.5 text-slate-500 font-mono text-[10px] mt-0.5">
                          <Phone className="w-2.5 h-2.5 text-slate-400" />
                          <span>{c.phone}</span>
                        </div>
                      )}
                    </td>

                    {/* Source */}
                    <td className="py-3.5 px-3 align-middle text-slate-500 capitalize text-[11px]">
                      {c.data_source.replace('_', ' ')}
                    </td>

                    {/* STATUS / ELIGIBILITY (Directly Editable Selector) */}
                    <td className="py-3.5 px-3 align-middle">
                      <div className="relative inline-block w-full max-w-[170px]">
                        <select
                          value={
                            isSuppressed
                              ? 'suppressed'
                              : isNeedsReview
                              ? 'needs_review'
                              : isVerified
                              ? 'verified'
                              : 'eligible'
                          }
                          onChange={(e) =>
                            updateStatusMutation.mutate({
                              contactId: c.contact_id,
                              newStatus: e.target.value,
                            })
                          }
                          className={`w-full text-[11px] font-semibold py-1 pl-2 pr-6 rounded-lg border appearance-none cursor-pointer focus:outline-none focus:ring-1 transition-all ${
                            isSuppressed
                              ? 'bg-rose-50 text-rose-700 border-rose-200 focus:ring-rose-400'
                              : isNeedsReview
                              ? 'bg-amber-50 text-amber-800 border-amber-200 focus:ring-amber-400'
                              : isVerified
                              ? 'bg-blue-50 text-blue-700 border-blue-200 focus:ring-blue-400'
                              : 'bg-emerald-50 text-emerald-700 border-emerald-200 focus:ring-emerald-400'
                          }`}
                        >
                          <option value="eligible">Eligible (Active)</option>
                          <option value="verified">Verified Decision-Maker</option>
                          <option value="needs_review">Needs Review / Test Only</option>
                          <option value="suppressed">Suppressed (Do Not Contact)</option>
                        </select>
                        <ChevronDown className="w-3 h-3 absolute right-2 top-2 pointer-events-none text-current opacity-70" />
                      </div>
                    </td>

                    {/* Actions */}
                    <td className="py-3.5 px-4 align-middle text-right">
                      <div className="flex items-center justify-end space-x-1.5">
                        {!isPrimary ? (
                          <button
                            onClick={() => setPrimaryMutation.mutate(c)}
                            className="px-2 py-1 text-[11px] font-semibold text-slate-700 bg-white border border-slate-200 hover:bg-slate-50 rounded shadow-2xs transition-colors"
                          >
                            Set Primary
                          </button>
                        ) : (
                          <span className="text-[11px] text-emerald-600 font-semibold px-1">Active</span>
                        )}
                        <button
                          onClick={() => navigate(`/research/outreach/${c.account_id}?contact=${c.contact_id}`)}
                          className="px-2.5 py-1 text-[11px] font-semibold text-white bg-[#201D6E] hover:bg-[#1a1758] rounded transition-colors"
                        >
                          Draft
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}

              {filteredContacts.length === 0 && (
                <tr>
                  <td colSpan={9} className="py-12 text-center text-slate-500 text-xs">
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
            Showing {filteredContacts.length} of {totalContacts} contacts{' '}
            {selectedCompany !== 'all' ? `for ${currentCompanyObj?.company_name || selectedCompany}` : 'across all companies'}
          </div>
          <div className="text-slate-400">Rule of 3 Compliance Enforced &bull; Status updates apply immediately</div>
        </div>
      </div>

      {/* Add Contact Modal */}
      <Modal
        isOpen={isAddModalOpen}
        onClose={() => {
          setIsAddModalOpen(false);
          setFormError(null);
        }}
        title="Add Decision-Maker Contact"
        description="Manually record a new decision-maker and optionally set up an outreach draft immediately."
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

            <div className="flex items-center space-x-2">
              <button
                type="button"
                onClick={() => createContactMutation.mutate({ openOutreach: false })}
                disabled={createContactMutation.isPending}
                className="px-3.5 py-2 text-xs font-semibold text-slate-700 bg-white border border-slate-200 hover:bg-slate-50 rounded-lg shadow-2xs transition-colors"
              >
                {createContactMutation.isPending ? 'Saving...' : 'Save Contact'}
              </button>

              <button
                type="button"
                onClick={() => createContactMutation.mutate({ openOutreach: true })}
                disabled={createContactMutation.isPending}
                className="px-4 py-2 text-xs font-semibold text-white bg-[#201D6E] hover:bg-[#1a1758] rounded-lg shadow-2xs transition-colors flex items-center space-x-1.5"
              >
                <Send className="w-3.5 h-3.5" />
                <span>{createContactMutation.isPending ? 'Saving...' : 'Save & Set Outreach'}</span>
              </button>
            </div>
          </div>
        </div>
      </Modal>
    </div>
  );
};
