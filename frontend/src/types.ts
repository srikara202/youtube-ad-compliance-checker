export type JobStatus = "QUEUED" | "PROCESSING" | "COMPLETED" | "FAILED";
export type ComplianceStatus = "PASS" | "FAIL" | "UNKNOWN";
export type AuditSourceType = "youtube" | "media_url" | "upload";

export interface ComplianceIssue {
  category: string;
  severity: string;
  description: string;
}

export interface AuditVideoPreview {
  video_url: string;
  source_type: AuditSourceType;
  source_label: string;
  youtube_video_id: string | null;
  title: string;
  thumbnail_url: string | null;
}

export interface AuditJobResult {
  status: ComplianceStatus;
  compliance_results: ComplianceIssue[];
  final_report: string;
}

export interface AuditJobResponse {
  audit_id: string;
  job_status: JobStatus;
  video: AuditVideoPreview;
  result: AuditJobResult | null;
  error: string | null;
  created_at: string;
  updated_at: string;
}

export interface PaywallConfig {
  enabled: boolean;
  pack_credits: number;
  pack_price_cents: number;
  max_video_seconds: number;
  credit_seconds: number;
  invite_enabled: boolean;
}

export interface BillingMeResponse {
  email: string | null;
  credits: number;
  config: PaywallConfig;
}

export interface BillingAccessResponse {
  email: string;
  credits: number;
  access_token: string;
  config: PaywallConfig;
}

export interface BillingCheckoutResponse {
  session_id: string;
  checkout_url: string;
}
