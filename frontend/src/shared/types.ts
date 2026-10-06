export type Role = "purchase_order" | "invoice" | "payment_request";
export type DocumentType =
  Role | "purchase_request" | "unclassified" | "unknown" | "mixed";
export interface Observation {
  id: string;
  document_id: string;
  field_key: string;
  value_type: string;
  raw_value: string | null;
  normalized_value: string | null;
  page_id: string;
  quote: string;
  group_key: string | null;
  role: string | null;
  unit: string | null;
  grounding: string;
}
export interface Extraction {
  semantic_review?: {
    basis: string;
    changes: {
      page_id: string;
      before?: { field_key: string };
      after?: { field_key: string };
      added_field?: string;
    }[];
  };
  schema_version?: string;
  processing_review_status?: "pending" | "completed";
  quality?: {
    reviewed_page_ids: string[];
    correction_count: number;
    addition_count: number;
    visual_independently_verified: boolean;
  };
  document_type: string;
  observations: Observation[];
  uncertainties: string[];
  page_coverage: string[];
}
export interface AuditDocument {
  id: string;
  role: DocumentType;
  role_hint?: Role | null;
  status: string;
  extraction: Extraction | null;
}
export type ProofExpression =
  | { observation_id: string }
  | {
      operation: string;
      operands: ProofExpression[];
    };
export interface Finding {
  id: string;
  category: string;
  scope: string;
  severity: "high" | "medium" | "low";
  title: string;
  explanation: string;
  observation_ids: string[];
  calculation_ids: string[];
  policy_refs: string[];
  semantic_review?: { verdict: string; reason: string };
  verified_checks?: {
    id: string;
    purpose: string;
    left: ProofExpression;
    right: ProofExpression;
    relation: string;
  }[];
  supporting_findings?: { title: string; explanation: string }[];
  related_issues?: {
    case_id: string;
    title: string;
    scope: string;
    relation: string;
  }[];
}
export interface Calculation {
  id: string;
  result: string;
  unit: string | null;
  comparison: {
    difference: string | null;
    status: string;
    reported?: string;
  } | null;
}
export interface Review {
  processing_status?: string;
  unresolved_checks?: string[];
  document_id?: string;
  calculations: Calculation[];
  assessed_topics: string[];
  links?: {
    status: string;
    explanation: string;
    from_document: string;
    to_document: string;
  }[];
}
export interface UsageCall {
  id: string;
  stage: string;
  model: string;
  status: string;
  latency_ms: number | null;
  prompt_tokens: number | null;
  completion_tokens: number | null;
  estimated_usd: number | null;
  estimated_neurons: number | null;
  attempt: number;
}
export interface Usage {
  calls: UsageCall[];
  stages?: {
    stage: string;
    call_count: number;
    estimated_usd: number;
    estimated_neurons: number;
    unknown_usage_calls: number;
  }[];
  call_count: number;
  prompt_tokens: number;
  completion_tokens: number;
  estimated_usd: number;
  estimated_neurons: number;
  unknown_usage_calls: number;
  pricing_version: string;
}
export interface Audit {
  id: string;
  status: string;
  assessment: string;
  verification_outdated?: boolean;
  current_stage: string;
  created_at: string;
  updated_at: string;
  error: string | null;
  documents: AuditDocument[];
  report: {
    findings?: Finding[];
    unresolved_checks?: string[];
    internal?: Review[];
    cross?: Review | null;
  };
  usage: Usage;
}
export interface HistoryItem {
  id: string;
  status: string;
  assessment: string;
  created_at: string;
  finding_count: number;
}
export interface DocumentDetail {
  id: string;
  role: DocumentType;
  extraction: Extraction | null;
  files: { id: string; name: string; url: string; media_type: string }[];
  pages: {
    id: string;
    number: number;
    preview_url: string;
    evidence: { input_method: string };
  }[];
}
