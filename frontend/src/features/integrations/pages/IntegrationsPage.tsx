import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { PageHeader } from '@/components/layout/PageHeader';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { LoadingState, ErrorState } from '@/components/ui/FeedbackStates';
import { apiClient } from '@/lib/apiClient';
import { StandardResponse } from '@/types/api';
import { Plug, CheckCircle2, AlertTriangle, RefreshCw, Radio } from 'lucide-react';

interface IntegrationHealth {
  adapter_name: string;
  is_healthy: boolean;
  status: string;
  latency_ms: number;
  error_message?: string;
}

export const IntegrationsPage: React.FC = () => {
  const { data: adapters = [], isLoading, isError, error, refetch } = useQuery({
    queryKey: ['integrations', 'health'],
    queryFn: async () => {
      const res = await apiClient.get<StandardResponse<IntegrationHealth[]>>('/integrations/health');
      return res.data.data;
    },
  });

  return (
    <div className="space-y-6">
      <PageHeader
        title="Integration Ecosystem"
        description="External CRM, telephony, calendar, AI model, and data storage connectors with circuit breaker safeguards."
        action={
          <Button variant="outline" onClick={() => refetch()}>
            <RefreshCw className="w-4 h-4 mr-2" />
            Ping Adapters
          </Button>
        }
      />

      {isLoading ? (
        <LoadingState message="Testing integration health..." />
      ) : isError ? (
        <ErrorState
          message={(error as Error)?.message || 'Failed to query integration health.'}
          onRetry={() => refetch()}
        />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {adapters.map((adapter) => (
            <div
              key={adapter.adapter_name}
              className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 p-5 shadow-xs flex flex-col justify-between space-y-4"
            >
              <div>
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center space-x-2">
                    <Plug className="w-4 h-4 text-brand-600" />
                    <h4 className="text-sm font-bold text-slate-900 dark:text-slate-100 uppercase tracking-tight">
                      {adapter.adapter_name}
                    </h4>
                  </div>
                  <Badge variant={adapter.is_healthy ? 'success' : 'danger'}>
                    {adapter.status}
                  </Badge>
                </div>
                <p className="text-xs text-slate-500">
                  {adapter.error_message || 'Adapter operational and responding to health probes.'}
                </p>
              </div>

              <div className="pt-3 border-t border-slate-100 dark:border-slate-800 flex items-center justify-between text-xs text-slate-400">
                <span>Latency: {adapter.latency_ms.toFixed(0)}ms</span>
                <span className="flex items-center space-x-1 text-emerald-600 font-semibold">
                  <Radio className="w-3.5 h-3.5 animate-pulse" />
                  <span>Connected</span>
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
