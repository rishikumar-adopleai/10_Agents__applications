export interface Account {
  id: string;
  organization_id: string;
  name: string;
  domain: string;
  industry?: string;
  employee_count?: number;
  fit_score: number;
  status: string;
  tier?: string;
  owner_id?: string;
  created_at: string;
  updated_at: string;
}

export interface Contact {
  id: string;
  organization_id: string;
  account_id: string;
  first_name: string;
  last_name: string;
  email: string;
  phone?: string;
  title?: string;
  job_title?: string;
  logical_outreach_attempts: number;
  is_suppressed: boolean;
  suppression_reason?: string;
  created_at: string;
  updated_at: string;
}

export interface Opportunity {
  id: string;
  organization_id: string;
  account_id: string;
  name: string;
  amount?: number;
  stage: string;
  discovery_completed: boolean;
  discovery_notes?: string;
  owner_id?: string;
  created_at: string;
  updated_at: string;
}

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
  source_evidence: Record<string, unknown>;
  risk_flags: string[];
  status: string;
  reviewed_by_user_id?: string;
  review_feedback?: string;
  due_at?: string;
  created_at: string;
  updated_at: string;
}
