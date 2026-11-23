import React, { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Building2,
  ExternalLink,
  RotateCw,
  ShieldCheck,
  CheckCircle2,
  AlertCircle,
  Clock,
  Sparkles,
  Users,
  Send,
  Link as LinkIcon,
  HelpCircle,
  ArrowLeft,
  ArrowRight,
  Search,
  ChevronRight,
  Briefcase,
} from 'lucide-react';
import { apiClient } from '@/lib/apiClient';
import { StandardResponse } from '@/types/api';
import { LoadingState } from '@/components/ui/FeedbackStates';

interface CompanyListItem {
  account_id: string;
  company_name: string;
  domain: string;
  industry: string;
  priority_score: number;
  priority_tier: string;
  why_now: string;
  buying_signal: string;
  research_status: string;
  contacts_count: number;
  opportunity_offering?: string;
  last_updated?: string;
  is_synthetic?: boolean;
}

interface IntelligenceData {
  account_id: string;
  company_name: string;
  domain: string;
  website: string;
  industry: string;
  priority_score: number;
  priority_tier: string;
  why_now: string;
  research_status: string;
  last_research_date: string;
  is_synthetic: boolean;
  overview: {
    description: string;
    products_services: string[];
    recent_developments: string;
    buying_signal_summary: string;
  };
  buying_signals: Array<{
    signal_id: string;
    type: string;
    observed_fact: string;
    observed_at: string;
    source: { url?: string; source_type?: string };
    confidence?: string;
  }>;
  research_findings: {
    verified_facts: Array<{ fact: string; source: string; confidence: string }>;
    hypotheses: Array<{ hypothesis: string; status: string }>;
    potential_opportunity: string;
    sources: string[];
    ai_analysis: string;
  };
  contacts: Array<{
    contact_id: string;
    full_name: string;
    job_title: string;
    department: string;
    seniority: string;
    email: string;
    phone?: string;
    linkedin?: string;
    data_source: string;
    verification_status: string;
    contact_eligibility: string;
    is_primary: boolean;
  }>;
  activity_history: Array<{
    step: string;
    status: string;
    date: string;
    details: string;
  }>;
}

/**
 * 1. Company List View (Main Screen for /research/company)
 * Displays all companies directly so users can browse and click to view full details.
 */
const CompanyListView: React.FC = () => {
  const navigate = useNavigate();
  const [search, setSearch] = useState('');
  const [industryFilter, setIndustryFilter] = useState('all');

  const { data: companies, isLoading } = useQuery({
    queryKey: ['research', 'companies'],
    queryFn: async () => {
      const res = await apiClient.get<StandardResponse<CompanyListItem[]>>('/research/companies');
      return res.data.data;
    },
  });

  if (isLoading || !companies) {
    return <LoadingState message="Loading companies for intelligence..." />;
  }

  // Filter companies
  const filtered = companies.filter((c) => {
    const matchesSearch =
      c.company_name.toLowerCase().includes(search.toLowerCase()) ||
      c.domain.toLowerCase().includes(search.toLowerCase()) ||
      c.industry.toLowerCase().includes(search.toLowerCase()) ||
      (c.why_now && c.why_now.toLowerCase().includes(search.toLowerCase()));

    const matchesIndustry =
      industryFilter === 'all' || c.industry.toLowerCase() === industryFilter.toLowerCase();

    return matchesSearch && matchesIndustry;
  });

  const industries = Array.from(new Set(companies.map((c) => c.industry))).filter(Boolean);

  const totalCompanies = companies.length;
  const completedResearch = companies.filter((c) => c.research_status.toLowerCase() === 'completed').length;
  const totalContacts = companies.reduce((sum, c) => sum + (c.contacts_count || 0), 0);
  const avgPriority = Math.round(
    companies.reduce((sum, c) => sum + (c.priority_score || 0), 0) / (companies.length || 1)
  );

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between pb-3 border-b border-slate-200 gap-3">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-slate-900">Company Intelligence</h1>
          <p className="text-xs text-slate-500 mt-1">
            Grounded corporate intelligence dossiers, verified research findings, buying signal analysis, and decision-maker mapping.
          </p>
        </div>

        <div className="flex items-center space-x-2">
          <button
            onClick={() => navigate('/research/contacts')}
            className="px-3 py-1.5 text-xs font-semibold text-slate-700 bg-white border border-slate-200 hover:bg-slate-50 rounded-lg shadow-2xs transition-colors flex items-center space-x-1.5"
          >
            <Users className="w-3.5 h-3.5" />
            <span>All Contacts ({totalContacts})</span>
          </button>
          <button
            onClick={() => navigate('/research/outreach')}
            className="px-3.5 py-1.5 text-xs font-semibold text-white bg-[#201D6E] hover:bg-[#1a1758] rounded-lg shadow-2xs transition-colors flex items-center space-x-1.5"
          >
            <Send className="w-3.5 h-3.5" />
            <span>Outreach Studio</span>
          </button>
        </div>
      </div>

      {/* KPI Stats Bar */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-white p-4 rounded-xl border border-slate-200/90 shadow-2xs">
          <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">Total Companies</div>
          <div className="text-2xl font-bold text-slate-900 mt-1">{totalCompanies}</div>
          <div className="text-[11px] text-slate-500 mt-0.5">Identified in pipeline</div>
        </div>

        <div className="bg-white p-4 rounded-xl border border-slate-200/90 shadow-2xs">
          <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">Research Completed</div>
          <div className="text-2xl font-bold text-emerald-600 mt-1">{completedResearch}</div>
          <div className="text-[11px] text-slate-500 mt-0.5">Full dossiers synthesized</div>
        </div>

        <div className="bg-white p-4 rounded-xl border border-slate-200/90 shadow-2xs">
          <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">Decision-Makers</div>
          <div className="text-2xl font-bold text-indigo-600 mt-1">{totalContacts}</div>
          <div className="text-[11px] text-slate-500 mt-0.5">Mapped executive targets</div>
        </div>

        <div className="bg-white p-4 rounded-xl border border-slate-200/90 shadow-2xs">
          <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">Avg Priority Fit</div>
          <div className="text-2xl font-bold text-[#201D6E] mt-1">{avgPriority}%</div>
          <div className="text-[11px] text-slate-500 mt-0.5">High ICP correlation</div>
        </div>
      </div>

      {/* Search and Filters Bar */}
      <div className="p-3 bg-white rounded-xl border border-slate-200/90 shadow-2xs flex flex-col md:flex-row md:items-center justify-between gap-3">
        <div className="relative flex-1 max-w-md">
          <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-2.5" />
          <input
            type="text"
            placeholder="Search companies by name, domain, or buying signal..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-9 pr-3.5 py-1.5 bg-slate-50 border border-slate-200 rounded-lg text-xs text-slate-800 placeholder:text-slate-400 focus:outline-none focus:ring-1 focus:ring-indigo-500"
          />
        </div>

        <div className="flex items-center space-x-3 text-xs">
          <div className="flex items-center space-x-1.5">
            <span className="text-slate-400 text-xs font-medium">Industry:</span>
            <select
              value={industryFilter}
              onChange={(e) => setIndustryFilter(e.target.value)}
              className="px-2.5 py-1 bg-slate-50 border border-slate-200 rounded-lg text-xs font-semibold text-slate-700 focus:outline-none focus:ring-1 focus:ring-indigo-500"
            >
              <option value="all">All Industries</option>
              {industries.map((ind) => (
                <option key={ind} value={ind}>
                  {ind}
                </option>
              ))}
            </select>
          </div>
          <span className="text-slate-400 font-medium">Showing {filtered.length} companies</span>
        </div>
      </div>

      {/* Companies Table */}
      <div className="bg-white rounded-xl border border-slate-200/90 shadow-2xs overflow-hidden text-xs">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse min-w-[950px]">
            <thead>
              <tr className="border-b border-slate-100 bg-slate-50/60 text-[10px] font-bold text-slate-400 uppercase tracking-wider">
                <th className="py-3 px-4 w-60">COMPANY &amp; DOMAIN</th>
                <th className="py-3 px-4 w-44">INDUSTRY</th>
                <th className="py-3 px-3 w-28 text-center">PRIORITY FIT</th>
                <th className="py-3 px-4 min-w-[280px]">BUYING SIGNAL / WHY PRIORITIZED</th>
                <th className="py-3 px-3 w-28 text-center">CONTACTS</th>
                <th className="py-3 px-3 w-32">RESEARCH STATUS</th>
                <th className="py-3 px-4 w-32 text-right">ACTION</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {filtered.map((company) => {
                const isCompleted = company.research_status.toLowerCase() === 'completed';
                return (
                  <tr
                    key={company.account_id}
                    onClick={() => navigate(`/research/company/${company.account_id}`)}
                    className="hover:bg-slate-50/80 cursor-pointer transition-colors group"
                  >
                    {/* Company Name & Domain */}
                    <td className="py-3.5 px-4 align-middle">
                      <div className="flex items-center space-x-2.5">
                        <div className="w-8 h-8 rounded-lg bg-indigo-50 text-[#201D6E] flex items-center justify-center font-bold text-xs shrink-0 group-hover:bg-[#201D6E] group-hover:text-white transition-colors">
                          <Building2 className="w-4 h-4" />
                        </div>
                        <div>
                          <div className="font-bold text-slate-900 group-hover:text-indigo-600 transition-colors">
                            {company.company_name}
                          </div>
                          <div className="text-[11px] text-slate-400 font-mono flex items-center space-x-1 mt-0.5">
                            <span>{company.domain}</span>
                            <ExternalLink className="w-2.5 h-2.5 text-slate-400" />
                          </div>
                        </div>
                      </div>
                    </td>

                    {/* Industry */}
                    <td className="py-3.5 px-4 align-middle">
                      <span className="bg-slate-100 text-slate-700 font-medium px-2 py-0.5 rounded text-[11px]">
                        {company.industry}
                      </span>
                    </td>

                    {/* Priority Fit */}
                    <td className="py-3.5 px-3 align-middle text-center">
                      <div className="inline-flex flex-col items-center">
                        <span className="font-bold text-slate-800 text-xs">
                          {company.priority_score}%
                        </span>
                        <div className="w-16 h-1.5 bg-slate-100 rounded-full mt-1 overflow-hidden">
                          <div
                            className="h-full bg-[#201D6E] rounded-full"
                            style={{ width: `${Math.min(company.priority_score, 100)}%` }}
                          />
                        </div>
                      </div>
                    </td>

                    {/* Buying Signal */}
                    <td className="py-3.5 px-4 align-middle">
                      <div className="flex items-start space-x-1.5 text-slate-700 leading-snug">
                        <Sparkles className="w-3.5 h-3.5 text-amber-500 shrink-0 mt-0.5" />
                        <span className="line-clamp-2">{company.why_now || company.buying_signal}</span>
                      </div>
                    </td>

                    {/* Contacts Count */}
                    <td className="py-3.5 px-3 align-middle text-center">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          navigate(`/research/contacts?company=${company.account_id}`);
                        }}
                        className="inline-flex items-center space-x-1 px-2 py-0.5 bg-indigo-50/70 hover:bg-indigo-100 text-indigo-700 font-semibold rounded text-[11px] transition-colors"
                      >
                        <Users className="w-3 h-3" />
                        <span>{company.contacts_count}</span>
                      </button>
                    </td>

                    {/* Research Status */}
                    <td className="py-3.5 px-3 align-middle">
                      <span
                        className={`inline-flex items-center space-x-1 px-2 py-0.5 rounded-full text-[10px] font-semibold ${
                          isCompleted
                            ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                            : 'bg-amber-50 text-amber-800 border border-amber-200'
                        }`}
                      >
                        {isCompleted ? (
                          <CheckCircle2 className="w-2.5 h-2.5" />
                        ) : (
                          <Clock className="w-2.5 h-2.5" />
                        )}
                        <span>{company.research_status}</span>
                      </span>
                    </td>

                    {/* Action */}
                    <td className="py-3.5 px-4 align-middle text-right">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          navigate(`/research/company/${company.account_id}`);
                        }}
                        className="px-3 py-1.5 text-xs font-semibold text-white bg-[#201D6E] hover:bg-[#1a1758] rounded-lg shadow-2xs transition-colors inline-flex items-center space-x-1"
                      >
                        <span>View Dossier</span>
                        <ChevronRight className="w-3 h-3" />
                      </button>
                    </td>
                  </tr>
                );
              })}

              {filtered.length === 0 && (
                <tr>
                  <td colSpan={7} className="py-12 text-center text-slate-500 text-xs">
                    No companies matched your search criteria.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        <div className="p-3 border-t border-slate-100 flex items-center justify-between text-xs text-slate-500 bg-white">
          <div>Showing {filtered.length} of {totalCompanies} companies</div>
          <div className="text-slate-400">Click any company to open its detailed research dossier</div>
        </div>
      </div>
    </div>
  );
};

/**
 * 2. Detailed Company Intelligence Dossier View
 * Rendered when a specific company is selected (/research/company/:accountId).
 * Includes 5 workspace tabs and a clear "Back to Companies" button.
 */
interface CompanyDossierViewProps {
  accountId: string;
}

const CompanyDossierView: React.FC<CompanyDossierViewProps> = ({ accountId }) => {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<'overview' | 'signals' | 'findings' | 'contacts' | 'history'>('overview');

  const { data: intelligence, isLoading } = useQuery({
    queryKey: ['research', 'company', accountId],
    queryFn: async () => {
      const res = await apiClient.get<StandardResponse<IntelligenceData>>(`/research/company/${accountId}`);
      return res.data.data;
    },
  });

  const runResearchMutation = useMutation({
    mutationFn: async () => {
      const res = await apiClient.post<StandardResponse<any>>(`/research/company/${accountId}/run`, {
        execution_mode: 'test',
      });
      return res.data.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['research', 'company', accountId] });
      queryClient.invalidateQueries({ queryKey: ['research', 'companies'] });
      queryClient.invalidateQueries({ queryKey: ['research', 'queue'] });
    },
  });

  if (isLoading || !intelligence) {
    return <LoadingState message="Loading company intelligence dossier..." />;
  }

  return (
    <div className="space-y-6">
      {/* 1. Header Navigation Bar with "Back to Companies" */}
      <div className="flex items-center justify-between bg-white px-4 py-2.5 rounded-xl border border-slate-200/90 shadow-2xs text-xs">
        <div className="flex items-center space-x-3">
          <button
            onClick={() => navigate('/research/company')}
            className="px-3 py-1.5 text-xs font-semibold text-slate-700 bg-white border border-slate-200 hover:bg-slate-50 rounded-lg shadow-2xs transition-colors flex items-center space-x-1.5"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            <span>Back to Companies</span>
          </button>

          <span className="text-slate-300">|</span>

          <span className="font-bold text-slate-900 text-xs">
            {intelligence.company_name} ({accountId})
          </span>

          {intelligence.is_synthetic && (
            <span className="bg-amber-50 text-amber-800 border border-amber-200/70 rounded-full px-2 py-0.5 text-[10px] font-semibold">
              Synthetic Demo Dossier
            </span>
          )}
        </div>

        <div className="flex items-center space-x-2">
          <button
            onClick={() => navigate(`/research/contacts?company=${accountId}`)}
            className="px-3 py-1.5 text-xs font-semibold text-slate-700 bg-white border border-slate-200 hover:bg-slate-50 rounded-lg transition-colors flex items-center space-x-1"
          >
            <Users className="w-3.5 h-3.5" />
            <span>Contacts ({intelligence.contacts.length})</span>
          </button>
          <button
            onClick={() => navigate(`/research/outreach/${accountId}`)}
            className="px-3.5 py-1.5 text-xs font-semibold text-white bg-[#201D6E] hover:bg-[#1a1758] rounded-lg transition-colors flex items-center space-x-1"
          >
            <Send className="w-3.5 h-3.5" />
            <span>Open in Outreach Studio</span>
          </button>
        </div>
      </div>

      {/* 2. Compact Workspace Header Card */}
      <div className="p-5 bg-white rounded-xl border border-slate-200/90 shadow-2xs space-y-4">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center space-x-3">
              <h1 className="text-xl font-bold tracking-tight text-slate-900">
                {intelligence.company_name}
              </h1>
              <span className="bg-emerald-50 text-emerald-700 border border-emerald-200 rounded-full px-2.5 py-0.5 text-[10px] font-semibold flex items-center space-x-1">
                <CheckCircle2 className="w-2.5 h-2.5" />
                <span>{intelligence.research_status}</span>
              </span>
            </div>

            <div className="flex flex-wrap items-center gap-3 text-xs text-slate-500 pt-0.5">
              <a
                href={intelligence.website}
                target="_blank"
                rel="noopener noreferrer"
                className="text-indigo-600 hover:text-indigo-800 flex items-center space-x-1 font-medium"
              >
                <span>{intelligence.domain}</span>
                <ExternalLink className="w-3 h-3" />
              </a>
              <span>&bull;</span>
              <span>{intelligence.industry}</span>
              <span>&bull;</span>
              <span>Last Research: {intelligence.last_research_date.split('T')[0]}</span>
            </div>
          </div>

          {/* Right Metrics & Run Button */}
          <div className="flex items-center space-x-3">
            <div className="px-3.5 py-2 bg-slate-50 rounded-lg border border-slate-200/70 text-right">
              <div className="text-[10px] text-slate-400 font-medium">Priority Fit</div>
              <div className="text-lg font-bold text-[#201D6E]">{intelligence.priority_score}%</div>
            </div>

            <button
              onClick={() => runResearchMutation.mutate()}
              disabled={runResearchMutation.isPending}
              className="px-3.5 py-2 bg-slate-100 hover:bg-indigo-50 text-slate-700 hover:text-indigo-700 rounded-lg border border-slate-200 text-xs font-semibold flex items-center space-x-1.5 transition-colors disabled:opacity-60"
            >
              <RotateCw className={`w-3.5 h-3.5 ${runResearchMutation.isPending ? 'animate-spin text-indigo-600' : ''}`} />
              <span>{runResearchMutation.isPending ? 'Refreshing...' : 'Refresh Research'}</span>
            </button>
          </div>
        </div>

        {/* Why Now Banner */}
        <div className="p-3 bg-amber-50/70 border border-amber-200/80 rounded-lg flex items-start space-x-2 text-xs text-amber-900">
          <Sparkles className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
          <div>
            <strong className="font-semibold">Why Prioritized:</strong> {intelligence.why_now}
          </div>
        </div>
      </div>

      {/* 3. Five-Tab Navigation */}
      <div className="border-b border-slate-200 flex space-x-6 text-xs">
        {[
          { key: 'overview', label: 'Overview' },
          { key: 'signals', label: `Buying Signals (${intelligence.buying_signals.length})` },
          { key: 'findings', label: 'Research Findings' },
          { key: 'contacts', label: `Contacts (${intelligence.contacts.length})` },
          { key: 'history', label: 'Activity History' },
        ].map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key as any)}
            className={`pb-2.5 font-semibold text-xs border-b-2 transition-colors ${
              activeTab === tab.key
                ? 'border-[#201D6E] text-[#201D6E]'
                : 'border-transparent text-slate-500 hover:text-slate-800'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* 4. Tab Contents */}
      {/* Tab 1: Overview */}
      {activeTab === 'overview' && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5 text-xs">
          <div className="bg-white p-5 rounded-xl border border-slate-200/90 shadow-2xs space-y-3">
            <h3 className="text-xs font-bold text-slate-900 uppercase tracking-wider">
              Company Overview &amp; Activities
            </h3>
            <p className="text-slate-700 leading-relaxed">
              {intelligence.overview.description}
            </p>
            <div>
              <div className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider mb-1.5">
                Primary Offerings
              </div>
              <div className="flex flex-wrap gap-1.5">
                {intelligence.overview.products_services.map((item) => (
                  <span key={item} className="bg-slate-100 text-slate-700 px-2 py-0.5 rounded text-[11px] font-medium">
                    {item}
                  </span>
                ))}
              </div>
            </div>
          </div>

          <div className="bg-white p-5 rounded-xl border border-slate-200/90 shadow-2xs space-y-3">
            <h3 className="text-xs font-bold text-slate-900 uppercase tracking-wider">
              Recent Business Developments
            </h3>
            <p className="text-slate-700 leading-relaxed">
              {intelligence.overview.recent_developments}
            </p>
            <div className="pt-2 border-t border-slate-100">
              <span className="text-[11px] text-slate-400 block mb-1">Official Domain</span>
              <a
                href={intelligence.website}
                target="_blank"
                rel="noopener noreferrer"
                className="text-indigo-600 hover:text-indigo-800 font-semibold flex items-center space-x-1"
              >
                <span>{intelligence.website}</span>
                <ExternalLink className="w-3 h-3" />
              </a>
            </div>
          </div>
        </div>
      )}

      {/* Tab 2: Buying Signals */}
      {activeTab === 'signals' && (
        <div className="space-y-3 text-xs">
          {intelligence.buying_signals.map((sig) => (
            <div
              key={sig.signal_id}
              className="bg-white p-4 rounded-xl border border-slate-200/90 shadow-2xs space-y-2"
            >
              <div className="flex items-center justify-between">
                <span className="bg-amber-50 text-amber-800 border border-amber-200 px-2.5 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-wider">
                  {sig.type.replace('_', ' ')}
                </span>
                <span className="text-[11px] text-slate-400">{sig.observed_at}</span>
              </div>
              <p className="text-slate-800 font-medium text-xs leading-snug">
                {sig.observed_fact}
              </p>
              {sig.source?.url && (
                <div className="pt-1 flex items-center space-x-1 text-[11px] text-indigo-600">
                  <LinkIcon className="w-3 h-3" />
                  <a href={sig.source.url} target="_blank" rel="noopener noreferrer" className="hover:underline truncate">
                    {sig.source.url}
                  </a>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Tab 3: Research Findings */}
      {activeTab === 'findings' && (
        <div className="space-y-5 text-xs">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
            {/* Verified Facts */}
            <div className="bg-white p-5 rounded-xl border border-slate-200/90 shadow-2xs space-y-3">
              <div className="flex items-center space-x-1.5 text-emerald-700">
                <ShieldCheck className="w-4 h-4" />
                <h3 className="text-xs font-bold uppercase tracking-wider">
                  Verified Grounded Facts
                </h3>
              </div>
              <div className="space-y-2.5">
                {intelligence.research_findings.verified_facts.map((vf, idx) => (
                  <div key={idx} className="p-2.5 bg-emerald-50/40 border border-emerald-100 rounded-lg space-y-1">
                    <p className="text-slate-800 font-medium">{vf.fact}</p>
                    <span className="text-[10px] text-emerald-700 font-semibold block truncate">
                      Source: {vf.source}
                    </span>
                  </div>
                ))}
              </div>
            </div>

            {/* Unverified Hypotheses */}
            <div className="bg-white p-5 rounded-xl border border-slate-200/90 shadow-2xs space-y-3">
              <div className="flex items-center space-x-1.5 text-amber-700">
                <HelpCircle className="w-4 h-4" />
                <h3 className="text-xs font-bold uppercase tracking-wider">
                  Unverified Hypotheses (Assumptions)
                </h3>
              </div>
              <div className="space-y-2.5">
                {intelligence.research_findings.hypotheses.map((hyp, idx) => (
                  <div key={idx} className="p-2.5 bg-amber-50/40 border border-amber-100 rounded-lg space-y-1">
                    <p className="text-slate-800 font-medium">{hyp.hypothesis}</p>
                    <span className="text-[10px] text-amber-800 font-semibold block uppercase">
                      Status: Needs Discovery Validation
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* AI Opportunity Analysis */}
          <div className="bg-white p-5 rounded-xl border border-slate-200/90 shadow-2xs space-y-2">
            <h3 className="text-xs font-bold text-slate-900 uppercase tracking-wider flex items-center space-x-1.5">
              <Sparkles className="w-3.5 h-3.5 text-indigo-600" />
              <span>AI Strategic Opportunity Synthesis</span>
            </h3>
            <p className="text-slate-700 leading-relaxed">
              {intelligence.research_findings.ai_analysis}
            </p>
            <div className="p-3 bg-indigo-50/50 border border-indigo-100 rounded-lg font-medium text-indigo-950 mt-2">
              <strong>Potential Business Opportunity:</strong> {intelligence.research_findings.potential_opportunity}
            </div>
          </div>
        </div>
      )}

      {/* Tab 4: Contacts */}
      {activeTab === 'contacts' && (
        <div className="bg-white rounded-xl border border-slate-200/90 shadow-2xs overflow-hidden text-xs">
          <div className="p-3.5 border-b border-slate-100 flex items-center justify-between">
            <h3 className="text-xs font-bold text-slate-900 uppercase tracking-wider">
              Identified Decision-Makers ({intelligence.contacts.length})
            </h3>
            <button
              onClick={() => navigate(`/research/contacts?company=${accountId}`)}
              className="text-xs text-indigo-600 hover:text-indigo-800 font-semibold flex items-center space-x-1"
            >
              <span>Manage &amp; Discover Contacts</span>
              <ExternalLink className="w-3 h-3" />
            </button>
          </div>
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-slate-100 bg-slate-50/60 text-[10px] font-bold text-slate-400 uppercase tracking-wider">
                <th className="py-2.5 px-4">NAME</th>
                <th className="py-2.5 px-3">ROLE</th>
                <th className="py-2.5 px-3">EMAIL</th>
                <th className="py-2.5 px-3">STATUS</th>
                <th className="py-2.5 px-3 text-right">ACTION</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {intelligence.contacts.map((c) => (
                <tr key={c.contact_id} className="hover:bg-slate-50">
                  <td className="py-3 px-4 font-semibold text-slate-900">
                    <div className="flex items-center space-x-2">
                      <span>{c.full_name}</span>
                      {c.is_primary && (
                        <span className="bg-indigo-50 text-indigo-700 border border-indigo-200 rounded px-1.5 py-0.2 text-[9px] font-bold">
                          Primary
                        </span>
                      )}
                    </div>
                  </td>
                  <td className="py-3 px-3 text-slate-600">{c.job_title}</td>
                  <td className="py-3 px-3 text-slate-600 font-mono text-[11px]">{c.email}</td>
                  <td className="py-3 px-3">
                    <span className="bg-emerald-50 text-emerald-700 border border-emerald-200 rounded-full px-2 py-0.5 text-[10px] font-medium capitalize">
                      {c.verification_status}
                    </span>
                  </td>
                  <td className="py-3 px-3 text-right">
                    <button
                      onClick={() => navigate(`/research/outreach/${accountId}?contact=${c.contact_id}`)}
                      className="px-2.5 py-1 text-xs text-indigo-700 bg-indigo-50 hover:bg-indigo-100 rounded font-semibold transition-colors"
                    >
                      Draft Message
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Tab 5: Activity History */}
      {activeTab === 'history' && (
        <div className="bg-white rounded-xl border border-slate-200/90 shadow-2xs p-5 space-y-4 text-xs">
          <h3 className="text-xs font-bold text-slate-900 uppercase tracking-wider">
            Pipeline 2 Execution Audit Trail
          </h3>
          <div className="divide-y divide-slate-100">
            {intelligence.activity_history.map((hist, idx) => (
              <div key={idx} className="py-3 flex items-start justify-between">
                <div>
                  <div className="font-semibold text-slate-800 text-xs">{hist.step}</div>
                  <div className="text-slate-500 text-[11px] mt-0.5">{hist.details}</div>
                </div>
                <div className="text-right">
                  <span className="bg-emerald-50 text-emerald-700 border border-emerald-200 rounded-full px-2 py-0.5 text-[10px] font-medium">
                    {hist.status}
                  </span>
                  <div className="text-[10px] text-slate-400 mt-1">{hist.date}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

/**
 * Main CompanyIntelligencePage Route Component
 * Routes to CompanyListView if no accountId in URL params, or CompanyDossierView if accountId is present.
 */
export const CompanyIntelligencePage: React.FC = () => {
  const { accountId } = useParams<{ accountId?: string }>();

  if (!accountId) {
    return <CompanyListView />;
  }

  return <CompanyDossierView accountId={accountId} />;
};
