import { FormEvent, useState, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import ReactMarkdown from "react-markdown";
import { createAudit, getAudit } from "./api";
import type { AuditJobResponse, ComplianceIssue, ComplianceStatus, JobStatus } from "./types";
import { validateYouTubeUrl } from "./utils/youtube";

const TERMINAL_STATUSES = new Set<JobStatus>(["COMPLETED", "FAILED"]);

const JOB_STATUS_COPY: Record<
  JobStatus,
  { label: string; detail: string; tone: "neutral" | "progress" | "success" | "danger" }
> = {
  QUEUED: {
    label: "Queued",
    detail: "The audit has been queued and is about to start processing.",
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

export default function App() {
  const queryClient = useQueryClient();
  const [videoUrl, setVideoUrl] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [activeAuditId, setActiveAuditId] = useState<string | null>(null);
  const [seedAudit, setSeedAudit] = useState<AuditJobResponse | null>(null);

  const validation = videoUrl.trim() ? validateYouTubeUrl(videoUrl) : null;

  const createAuditMutation = useMutation({
    mutationFn: createAudit,
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

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const nextValidation = validateYouTubeUrl(videoUrl);
    if (!nextValidation.isValid || !nextValidation.normalizedUrl) {
      setFormError(nextValidation.error);
      return;
    }

    setFormError(null);
    setSeedAudit(null);
    setActiveAuditId(null);
    createAuditMutation.mutate(nextValidation.normalizedUrl);
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
              <h1>Audit YouTube ads before compliance issues slip through.</h1>
              <p className="hero-copy">
                Paste a YouTube link and the app will fetch the preview, run the backend
                compliance workflow, and assemble a final report for review.
              </p>
            </div>
            <div className="hero-callout">
              <span className="hero-callout-label">Internal MVP</span>
              <strong>Fast preview + background audit</strong>
              <p>The UI returns video context up front, then keeps polling until the full report is ready.</p>
            </div>
          </div>

          <form className="audit-form" onSubmit={handleSubmit}>
            <label className="input-label" htmlFor="video-url">
              YouTube URL
            </label>
            <div className="input-row">
              <input
                id="video-url"
                name="video-url"
                className="url-input"
                placeholder="https://www.youtube.com/watch?v=..."
                value={videoUrl}
                onChange={(event) => {
                  setVideoUrl(event.target.value);
                  if (formError) {
                    setFormError(null);
                  }
                }}
              />
              <button
                className="primary-button"
                type="submit"
                disabled={
                  createAuditMutation.isPending ||
                  !validation?.isValid
                }
              >
                {createAuditMutation.isPending ? "Starting audit..." : "Run audit"}
              </button>
            </div>
            <div className="helper-row">
              <span>Supports watch URLs, share links, shorts, and embed links.</span>
              {validation?.youtubeVideoId ? (
                <span className="helper-chip">Video ID: {validation.youtubeVideoId}</span>
              ) : null}
            </div>
            {formError ? <p className="inline-error">{formError}</p> : null}
            {!formError && validation && !validation.isValid ? (
              <p className="inline-error">{validation.error}</p>
            ) : null}
          </form>
        </section>

        <section className="workspace">
          <section className="panel preview-panel">
            <div className="section-header">
              <div>
                <p className="section-kicker">1. Video preview</p>
                <h2>Thumbnail and title</h2>
              </div>
            </div>

            {audit ? (
              <article className="video-card">
                <img
                  src={audit.video.thumbnail_url}
                  alt={audit.video.title}
                  className="video-thumbnail"
                />
                <div className="video-meta">
                  <StatusBadge tone="neutral">{audit.video.youtube_video_id}</StatusBadge>
                  <h3>{audit.video.title}</h3>
                  <a href={audit.video.video_url} target="_blank" rel="noreferrer">
                    {audit.video.video_url}
                  </a>
                </div>
              </article>
            ) : (
              <EmptyPanel
                title="Video details will appear here"
                description="Once the URL is accepted, the backend will fetch the YouTube title and thumbnail before the audit starts."
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
                description="Submit a YouTube URL to create an audit job and track it here."
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
