import React from 'react';
import { PageHeader } from '@/components/layout/PageHeader';
import { Button } from '@/components/ui/Button';
import { ShieldCheck, Lock, Sliders, Database, AlertCircle } from 'lucide-react';

export const SettingsPage: React.FC = () => {
  return (
    <div className="space-y-6">
      <PageHeader
        title="Platform Governance & Policy Configuration"
        description="Global organization policies, retention schedules, and deterministic safety rules."
      />

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 p-6 shadow-xs space-y-4">
          <div className="flex items-center space-x-2 text-brand-600">
            <ShieldCheck className="w-5 h-5" />
            <h4 className="text-sm font-bold text-slate-900 dark:text-slate-100">
              Outreach & Compliance Policy
            </h4>
          </div>
          <ul className="text-xs text-slate-600 dark:text-slate-300 space-y-3">
            <li className="flex items-start space-x-2">
              <span className="font-bold text-brand-600">3 Attempts Max:</span>
              <span>Enforced centrally in database across all 10 agents and ad-hoc campaigns.</span>
            </li>
            <li className="flex items-start space-x-2">
              <span className="font-bold text-brand-600">Irrevocable Suppression:</span>
              <span>Opt-outs, unsubscribes, and bot replies can never be overridden by AI agents.</span>
            </li>
            <li className="flex items-start space-x-2">
              <span className="font-bold text-brand-600">Human Approval Mandatory:</span>
              <span>All customer-facing messages require an authorized employee sign-off.</span>
            </li>
          </ul>
        </div>

        <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 p-6 shadow-xs space-y-4">
          <div className="flex items-center space-x-2 text-emerald-600">
            <Database className="w-5 h-5" />
            <h4 className="text-sm font-bold text-slate-900 dark:text-slate-100">
              Retention & Audit Schedules
            </h4>
          </div>
          <ul className="text-xs text-slate-600 dark:text-slate-300 space-y-3">
            <li className="flex items-start space-x-2">
              <span className="font-bold text-emerald-600">Audit Trails:</span>
              <span>Every login, agent run, decision, and approval has an immutable audit log.</span>
            </li>
            <li className="flex items-start space-x-2">
              <span className="font-bold text-emerald-600">Artifact Versioning:</span>
              <span>Proposals and questionnaires maintain exact hash-tracked version trees.</span>
            </li>
            <li className="flex items-start space-x-2">
              <span className="font-bold text-emerald-600">Data Scoping:</span>
              <span>All database queries strictly filter by tenant organization ID.</span>
            </li>
          </ul>
        </div>
      </div>
    </div>
  );
};
