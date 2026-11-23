import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { PageHeader } from '@/components/layout/PageHeader';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { apiClient } from '@/lib/apiClient';
import { StandardResponse } from '@/types/api';
import { GitBranch, Play, CheckCircle2, Clock, Sparkles } from 'lucide-react';

const WORKFLOW_SPECS = [
  { id: 'signal_to_outreach', name: 'Signal-to-Personalized-Outreach', desc: 'Triggers research & outreach draft upon verified buying signal. Strictly enforces 3-attempt cap.' },
  { id: 'discovery_to_proposal', name: 'Discovery-to-Approved-Proposal', desc: 'Ensures discovery completion before Deal Desk generates commercial proposals for review.' },
  { id: 'security_questionnaire_resolution', name: 'Security-Questionnaire-Resolution', desc: 'Trust Desk fills questionnaire with approved evidence and routes gaps to Security Reviewer.' },
  { id: 'delivery_to_proof', name: 'Delivery-to-Verified-Proof', desc: 'Generates case studies after delivery owner verification and client permission clearance.' },
  { id: 'dormant_lead_revival', name: 'Dormant-Lead-Revival', desc: 'Scans cold accounts for fresh intent events and checks suppression registry before outreach.' },
];

export const WorkflowsPage: React.FC = () => {
  const { data: runs = [] } = useQuery({
    queryKey: ['workflows', 'runs'],
    queryFn: async () => {
      try {
        const res = await apiClient.get<StandardResponse<any[]>>('/workflows/runs');
        return res.data.data;
      } catch {
        return [];
      }
    },
  });

  return (
    <div className="space-y-8">
      <PageHeader
        title="Durable Workflow Engine"
        description="Event-driven, asynchronous multi-agent workflows executing with outbox delivery and state checkpointing."
      />

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {WORKFLOW_SPECS.map((wf) => (
          <div
            key={wf.id}
            className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 p-5 shadow-xs space-y-3"
          >
            <div className="flex items-center justify-between">
              <span className="flex items-center space-x-2 text-brand-600 font-bold text-sm">
                <GitBranch className="w-4 h-4" />
                <span>{wf.name}</span>
              </span>
              <Badge variant="success">Active Spec</Badge>
            </div>
            <p className="text-xs text-slate-500 leading-relaxed">{wf.desc}</p>
            <div className="pt-2 border-t border-slate-100 dark:border-slate-800 flex justify-between items-center text-xs">
              <span className="font-mono text-slate-400">{wf.id}</span>
              <Button size="sm" variant="outline">
                <Play className="w-3.5 h-3.5 mr-1" />
                Trigger Workflow
              </Button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
