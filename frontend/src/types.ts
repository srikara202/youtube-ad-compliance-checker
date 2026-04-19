export type JobStatus = "QUEUED" | "PROCESSING" | "COMPLETED" | "FAILED";
export type ComplianceStatus = "PASS" | "FAIL" | "UNKNOWN";

export interface ComplianceIssue {
  category: string;
  severity: string;
  description: string;
}

export interface AuditVideoPreview {
  video_url: string;
  youtube_video_id: string;
  title: string;
  thumbnail_url: string;
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
