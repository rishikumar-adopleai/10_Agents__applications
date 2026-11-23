import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { AppShell } from '@/components/layout/AppShell';
import { ProtectedRoute } from './ProtectedRoute';
import { LoginPage } from '@/features/auth/pages/LoginPage';
import { DashboardPage } from '@/features/dashboard/pages/DashboardPage';
import { AgentsPage } from '@/features/agents/pages/AgentsPage';
import { ApprovalsPage } from '@/features/approvals/pages/ApprovalsPage';
import { AccountsPage } from '@/features/sales/pages/AccountsPage';
import { RadarPage } from '@/features/sales/pages/RadarPage';
import { ResearchOverviewPage } from '@/features/research/pages/ResearchOverviewPage';
import { ResearchQueuePage } from '@/features/research/pages/ResearchQueuePage';
import { CompanyIntelligencePage } from '@/features/research/pages/CompanyIntelligencePage';
import { ContactDiscoveryPage } from '@/features/research/pages/ContactDiscoveryPage';
import { OutreachStudioPage } from '@/features/research/pages/OutreachStudioPage';
import { ApprovalCenterPage } from '@/features/research/pages/ApprovalCenterPage';
import { ResponderDashboardPage } from '@/features/responder/pages/ResponderDashboardPage';
import { UnifiedInboxPage } from '@/features/responder/pages/UnifiedInboxPage';
import { MeetingsCalendarPage } from '@/features/responder/pages/MeetingsCalendarPage';
import { WorkflowMonitoringPage } from '@/features/responder/pages/WorkflowMonitoringPage';
import { ContactsPage } from '@/features/sales/pages/ContactsPage';
import { ConversationsPage } from '@/features/sales/pages/ConversationsPage';
import { DealsPage } from '@/features/sales/pages/DealsPage';
import { WorkflowsPage } from '@/features/workflows/pages/WorkflowsPage';
import { IntegrationsPage } from '@/features/integrations/pages/IntegrationsPage';
import { SettingsPage } from '@/features/settings/pages/SettingsPage';
import { UserListPage } from '@/features/users/pages/UserListPage';

export const AppRoutes: React.FC = () => {
  return (
    <Routes>
      {/* Public Routes */}
      <Route path="/login" element={<LoginPage />} />

      {/* Protected Routes inside AppShell */}
      <Route element={<ProtectedRoute />}>
        <Route element={<AppShell />}>
          <Route path="/" element={<Navigate to="/radar" replace />} />
          <Route path="/dashboard" element={<Navigate to="/radar" replace />} />
          <Route path="/radar" element={<RadarPage />} />
          {/* Agent 2: Research & Personal Outreach */}
          <Route path="/research" element={<Navigate to="/research/overview" replace />} />
          <Route path="/research/overview" element={<ResearchOverviewPage />} />
          <Route path="/research/queue" element={<ResearchQueuePage />} />
          <Route path="/research/company" element={<CompanyIntelligencePage />} />
          <Route path="/research/company/:accountId" element={<CompanyIntelligencePage />} />
          <Route path="/research/contacts" element={<ContactDiscoveryPage />} />
          <Route path="/research/contacts/:accountId" element={<ContactDiscoveryPage />} />
          <Route path="/research/outreach" element={<OutreachStudioPage />} />
          <Route path="/research/outreach/:accountId" element={<OutreachStudioPage />} />
          <Route path="/research/approvals" element={<ApprovalCenterPage />} />

          {/* Agent 4: 24/7 Lead Responder */}
          <Route path="/responder" element={<Navigate to="/responder/dashboard" replace />} />
          <Route path="/responder/dashboard" element={<ResponderDashboardPage />} />
          <Route path="/responder/inbox" element={<UnifiedInboxPage />} />
          <Route path="/responder/meetings" element={<MeetingsCalendarPage />} />
          <Route path="/responder/monitoring" element={<WorkflowMonitoringPage />} />

          <Route path="/agents" element={<AgentsPage />} />
          <Route path="/approvals" element={<ApprovalsPage />} />
          <Route path="/accounts" element={<AccountsPage />} />
          <Route path="/contacts" element={<ContactsPage />} />
          <Route path="/conversations" element={<ConversationsPage />} />
          <Route path="/deals" element={<DealsPage />} />
          <Route path="/workflows" element={<WorkflowsPage />} />
          <Route path="/partners" element={<AgentsPage />} />
          <Route path="/security" element={<ApprovalsPage />} />
          <Route path="/proof" element={<ApprovalsPage />} />
          <Route path="/visibility" element={<AgentsPage />} />
          <Route path="/revival" element={<AgentsPage />} />
          <Route path="/integrations" element={<IntegrationsPage />} />
          <Route path="/settings" element={<SettingsPage />} />

          {/* Admin Protected Route */}
          <Route
            element={<ProtectedRoute allowedRoles={['ADMINISTRATOR', 'SALES_MANAGER']} />}
          >
            <Route path="/users" element={<UserListPage />} />
          </Route>
        </Route>
      </Route>

      {/* Catch-all fallback */}
      <Route path="*" element={<Navigate to="/radar" replace />} />
    </Routes>
  );
};
