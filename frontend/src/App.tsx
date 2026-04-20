import { ChangeEvent, FormEvent, useState, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import ReactMarkdown from "react-markdown";
import { createUploadAudit, getAudit } from "./api";
import type {
  AuditJobResponse,
  AuditSourceType,
  ComplianceIssue,
  ComplianceStatus,
  JobStatus
} from "./types";

const TERMINAL_STATUSES = new Set<JobStatus>(["COMPLETED", "FAILED"]);

const JOB_STATUS_COPY: Record<
  JobStatus,
  { label: string; detail: string; tone: "neutral" | "progress" | "success" | "danger" }
> = {
  QUEUED: {
    label: "Queued",
    detail: "The audit has been queued and is waiting to start processing.",
    tone: "neutral"
  },
  PROCESSING: {
    label: "Processing",
    detail: "The backend is indexing the video, checking the rules, and building the report.",
    tone: "progress"
  },
  COMPLETED: {
    label: "Completed",
    detail: "The audit finished successfully. Review the findings and final report below.",
    tone: "success"
  },
  FAILED: {
    label: "Failed",
    detail: "The audit could not complete. Review the error below and try another run.",
    tone: "danger"
  }
};

const UPLOAD_COPY = {
  title: "Upload a local video file",
  description: "Use a local video upload for the most reliable audit flow in this build.",
  inputLabel: "Video file",
  helper: "Upload MP4, MOV, M4V, WEBM, AVI, MKV, MPEG, or MPG."
};

export default function App() {
  const queryClient = useQueryClient();
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [activeAuditId, setActiveAuditId] = useState<string | null>(null);
  const [seedAudit, setSeedAudit] = useState<AuditJobResponse | null>(null);

  const createAuditMutation = useMutation({
    mutationFn: (file: File) => createUploadAudit(file),
    onSuccess: (audit) => {
      setFormError(null);
      setSeedAudit(audit);
      setActiveAuditId(audit.audit_id);
      queryClient.setQueryData(["audit", audit.audit_id], audit);
    },
    onError: (error) => {
      setSeedAudit(null);
      setActiveAuditId(null);
      setFormError(error instanceof Error ? error.message : "Unable to start the audit.");
    }
  });

  const auditQuery = useQuery({
    queryKey: ["audit", activeAuditId],
    queryFn: () => getAudit(activeAuditId as string),
    enabled: Boolean(activeAuditId),
    initialData: seedAudit ?? undefined,
    refetchInterval: (query) => {
      const status = query.state.data?.job_status;
      if (!status) {
        return 3000;
      }
      return TERMINAL_STATUSES.has(status) ? false : 3000;
    }
  });

  const audit = auditQuery.data ?? seedAudit;
  const currentJobStatus = audit?.job_status ?? "QUEUED";
  const statusCopy = JOB_STATUS_COPY[currentJobStatus];
  const issues = audit?.result?.compliance_results ?? [];
  const canSubmit = Boolean(uploadFile);

  function resetPendingAudit() {
    setSeedAudit(null);
    setActiveAuditId(null);
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!uploadFile) {
      setFormError("Choose a media file to upload.");
      return;
    }

    setFormError(null);
    resetPendingAudit();
    createAuditMutation.mutate(uploadFile);
  }

  function handleUploadChange(event: ChangeEvent<HTMLInputElement>) {
    const nextFile = event.target.files?.[0] ?? null;
    setUploadFile(nextFile);
    if (formError) {
      setFormError(null);
    }
  }

  return (
    <div className="shell">
      <div className="ambient ambient-left" />
      <div className="ambient ambient-right" />

      <main className="app">
        <section className="hero panel">
          <p className="eyebrow">Youtube Add Compliance Checker</p>
          <div className="hero-grid">
            <div>
              <h1>Audit ad videos from direct local uploads.</h1>
              <p className="hero-copy">
                This build is focused on the most reliable path. Upload a local video file,
                then let the Azure-backed audit run in the background.
              </p>
            </div>
            <div className="hero-callout">
              <span className="hero-callout-label">Current build</span>
              <strong>Direct upload is the supported input path.</strong>
              <p>
                YouTube links and Blob URLs have been removed from the frontend so the app
                stays on the most stable audit flow.
              </p>
            </div>
          </div>

          <form className="audit-form" onSubmit={handleSubmit}>
            <div className="source-mode-copy">
              <p className="source-mode-title">{UPLOAD_COPY.title}</p>
              <p>{UPLOAD_COPY.description}</p>
            </div>

            <label className="input-label" htmlFor="video-file">
              {UPLOAD_COPY.inputLabel}
            </label>

            <div className="input-row">
              <input
                key="upload-file"
                id="video-file"
                name="video-file"
                className="file-input"
                type="file"
                accept=".mp4,.mov,.m4v,.webm,.avi,.mkv,.mpeg,.mpg,video/*"
                onChange={handleUploadChange}
              />
              <button className="primary-button" type="submit" disabled={createAuditMutation.isPending || !canSubmit}>
                {createAuditMutation.isPending ? "Starting audit..." : "Run audit"}
              </button>
            </div>

            <div className="helper-row">
              <span>{UPLOAD_COPY.helper}</span>
              {uploadFile ? <span className="helper-chip">File: {uploadFile.name}</span> : null}
            </div>

            {formError ? <p className="inline-error">{formError}</p> : null}
          </form>
        </section>

        <section className="workspace">
          <section className="panel preview-panel">
            <div className="section-header">
              <div>
                <p className="section-kicker">1. Video preview</p>
                <h2>Title and source details</h2>
              </div>
            </div>

            {audit ? (
              <article className="video-card">
                <PreviewArtwork video={audit.video} />
                <div className="video-meta">
                  <StatusBadge tone="neutral">{audit.video.source_label}</StatusBadge>
                  <h3>{audit.video.title}</h3>
                  {isExternalVideoUrl(audit.video.video_url) ? (
                    <a href={audit.video.video_url} target="_blank" rel="noreferrer">
                      {audit.video.video_url}
                    </a>
                  ) : (
                    <p className="video-source-note">Uploaded from a local file.</p>
                  )}
                </div>
              </article>
            ) : (
              <EmptyPanel
                title="Source details will appear here"
                description="Once the file upload is accepted, the backend will create a preview and start the audit job."
              />
            )}
          </section>

          <section className="panel status-panel">
            <div className="section-header">
              <div>
                <p className="section-kicker">2. Audit progress</p>
                <h2>Background job status</h2>
              </div>
              {audit ? <StatusBadge tone={statusCopy.tone}>{statusCopy.label}</StatusBadge> : null}
            </div>

            {audit ? (
              <div className="status-card">
                <div className="status-card-top">
                  <div className={`status-orbit status-orbit-${statusCopy.tone}`} />
                  <div>
                    <h3>{statusCopy.label}</h3>
                    <p>{statusCopy.detail}</p>
                  </div>
                </div>
                <dl className="status-meta">
                  <div>
                    <dt>Audit ID</dt>
                    <dd>{audit.audit_id}</dd>
                  </div>
                  <div>
                    <dt>Last updated</dt>
                    <dd>{formatTimestamp(audit.updated_at)}</dd>
                  </div>
                </dl>
                {audit.error ? <p className="status-error">{audit.error}</p> : null}
              </div>
            ) : (
              <EmptyPanel
                title="No audit running yet"
                description="Upload a local file to create an audit job and track it here."
              />
            )}
          </section>
        </section>

        <section className="results-grid">
          <section className="panel findings-panel">
            <div className="section-header">
              <div>
                <p className="section-kicker">3. Compliance result</p>
                <h2>Pass or fail</h2>
              </div>
              {audit?.result ? (
                <StatusBadge tone={getComplianceTone(audit.result.status)}>
                  Compliance {audit.result.status === "PASS" ? "pass" : "fail"}
                </StatusBadge>
              ) : null}
            </div>

            {audit?.result ? (
              <div className="issues-list">
                {issues.length > 0 ? (
                  issues.map((issue, index) => (
                    <IssueCard
                      issue={issue}
                      key={`${issue.category}-${issue.severity}-${index}`}
                    />
                  ))
                ) : (
                  <EmptyPanel
                    title="No violations detected"
                    description="The backend completed the audit and returned a clean compliance result."
                  />
                )}
              </div>
            ) : audit?.job_status === "FAILED" ? (
              <EmptyPanel
                title="The audit did not finish"
                description="Fix the backend issue shown above, then run the audit again."
              />
            ) : (
              <EmptyPanel
                title="Results will appear here"
                description="The pass or fail verdict and each compliance issue will populate once the job completes."
              />
            )}
          </section>

          <section className="panel report-panel">
            <div className="section-header">
              <div>
                <p className="section-kicker">4. Final report</p>
                <h2>Rendered summary</h2>
              </div>
            </div>

            {audit?.result ? (
              <div className="report-markdown">
                <ReactMarkdown>{audit.result.final_report}</ReactMarkdown>
              </div>
            ) : (
              <EmptyPanel
                title="The final report is not ready yet"
                description="When the backend finishes, the report will render here using safe markdown output."
              />
            )}
          </section>
        </section>
      </main>
    </div>
  );
}

function PreviewArtwork({ video }: { video: AuditJobResponse["video"] }) {
  if (video.thumbnail_url) {
    return <img src={video.thumbnail_url} alt={video.title} className="video-thumbnail" />;
  }

  return (
    <div className={`video-thumbnail video-thumbnail-fallback video-thumbnail-${video.source_type}`}>
      <span>{getSourceTypeLabel(video.source_type)}</span>
    </div>
  );
}

function StatusBadge({
  children,
  tone
}: {
  children: ReactNode;
  tone: "neutral" | "progress" | "success" | "danger";
}) {
  return <span className={`status-badge status-badge-${tone}`}>{children}</span>;
}

function IssueCard({ issue }: { issue: ComplianceIssue }) {
  return (
    <article className="issue-card">
      <div className="issue-card-header">
        <div>
          <p className="issue-category">{issue.category}</p>
          <h3>{issue.description}</h3>
        </div>
        <StatusBadge tone={getSeverityTone(issue.severity)}>{issue.severity}</StatusBadge>
      </div>
    </article>
  );
}

function EmptyPanel({ title, description }: { title: string; description: string }) {
  return (
    <div className="empty-panel">
      <h3>{title}</h3>
      <p>{description}</p>
    </div>
  );
}

function getSourceTypeLabel(sourceType: AuditSourceType): string {
  if (sourceType === "youtube") {
    return "YouTube preview";
  }
  if (sourceType === "media_url") {
    return "Blob or media URL";
  }
  return "Uploaded file";
}

function isExternalVideoUrl(videoUrl: string): boolean {
  return /^https?:\/\//i.test(videoUrl);
}

function getSeverityTone(severity: string): "neutral" | "progress" | "success" | "danger" {
  const normalized = severity.toUpperCase();
  if (normalized === "CRITICAL") {
    return "danger";
  }
  if (normalized === "WARNING") {
    return "progress";
  }
  return "neutral";
}

function getComplianceTone(status: ComplianceStatus): "neutral" | "progress" | "success" | "danger" {
  if (status === "PASS") {
    return "success";
  }
  if (status === "FAIL") {
    return "danger";
  }
  return "neutral";
}

function formatTimestamp(timestamp: string): string {
  const parsed = new Date(timestamp);
  if (Number.isNaN(parsed.getTime())) {
    return timestamp;
  }
  return parsed.toLocaleString();
}
