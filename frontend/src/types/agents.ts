export type AgentStatus =
  | 'completed'
  | 'waiting_for_input'
  | 'waiting_for_review'
  | 'blocked'
  | 'retryable_failure'
  | 'terminal_failure'
  | 'cancelled';

export interface ArtifactReference {
  artifact_id: string;
  artifact_type: string;
  version: string;
  summary?: string;
}

export interface EvidenceReference {
  source_url: string;
  source_type: string;
  excerpt: string;
  confidence: number;
}

export interface AgentExecutionResult {
  agent_id: string;
  execution_id: string;
  status: AgentStatus;
  structured_result: Record<string, unknown>;
  artifact_references: ArtifactReference[];
  evidence_references: EvidenceReference[];
  uncertainty: number;
  proposed_next_actions: string[];
  error_details?: string;
  execution_metadata: Record<string, unknown>;
}

export interface AgentTaskSummary {
  id: string;
  agent_id: string;
  execution_id: string;
  status: AgentStatus;
  uncertainty: number;
  created_at: string;
}
