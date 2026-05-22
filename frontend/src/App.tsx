import { ChangeEvent, FormEvent, useEffect, useState, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import ReactMarkdown from "react-markdown";
import {
  claimCheckout,
  createCheckout,
  createUploadAudit,
  getAudit,
  getBillingMe,
  redeemInvite
} from "./api";
import type {
  AuditJobResponse,
  BillingAccessResponse,
  AuditSourceType,
  ComplianceIssue,
  ComplianceStatus,
  JobStatus
} from "./types";

const TERMINAL_STATUSES = new Set<JobStatus>(["COMPLETED", "FAILED"]);
const BILLING_TOKEN_STORAGE_KEY = "portfolio-demo-billing-token";
const BILLING_EMAIL_STORAGE_KEY = "portfolio-demo-billing-email";

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
  description: "Upload your ad video and get a quick read on whether it is ready for YouTube.",
  inputLabel: "Video file",
  helper: "Upload MP4, MOV, M4V, WEBM, AVI, MKV, MPEG, or MPG."
};

export default function App() {
  const queryClient = useQueryClient();
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadDurationSeconds, setUploadDurationSeconds] = useState<number | null>(null);
  const [durationError, setDurationError] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [activeAuditId, setActiveAuditId] = useState<string | null>(null);
  const [seedAudit, setSeedAudit] = useState<AuditJobResponse | null>(null);
  const [billingToken, setBillingToken] = useState<string | null>(() =>
    window.localStorage.getItem(BILLING_TOKEN_STORAGE_KEY)
  );
  const [billingEmail, setBillingEmail] = useState<string>(() =>
    window.localStorage.getItem(BILLING_EMAIL_STORAGE_KEY) ?? ""
  );
  const [inviteCode, setInviteCode] = useState("");
  const [billingMessage, setBillingMessage] = useState<string | null>(null);

  const billingQuery = useQuery({
    queryKey: ["billing", billingToken],
    queryFn: () => getBillingMe(billingToken),
    retry: false
  });

  const billingStatusReady = billingQuery.isSuccess;
  const paywallConfig = billingQuery.data?.config;
  const paywallEnabled = paywallConfig?.enabled ?? false;
  const billingLocked = billingQuery.isError;
  const showAccessPanel = paywallEnabled || billingLocked;
  const availableCredits = billingQuery.data?.credits ?? 0;
  const creditSeconds = paywallConfig?.credit_seconds ?? 60;
  const maxVideoSeconds = paywallConfig?.max_video_seconds ?? 180;
  const requiredCredits =
    uploadFile && uploadDurationSeconds !== null
      ? Math.max(1, Math.ceil(uploadDurationSeconds / creditSeconds))
      : 0;
  const hasEnoughCredits = !paywallEnabled || (requiredCredits > 0 && availableCredits >= requiredCredits);

  function saveBillingAccess(access: BillingAccessResponse) {
    window.localStorage.setItem(BILLING_TOKEN_STORAGE_KEY, access.access_token);
    window.localStorage.setItem(BILLING_EMAIL_STORAGE_KEY, access.email);
    setBillingToken(access.access_token);
    setBillingEmail(access.email);
    queryClient.setQueryData(["billing", access.access_token], {
      email: access.email,
      credits: access.credits,
      config: access.config
    });
  }

  const checkoutMutation = useMutation({
    mutationFn: (email: string) => createCheckout(email),
    onSuccess: (checkout) => {
      window.localStorage.setItem(BILLING_EMAIL_STORAGE_KEY, billingEmail.trim());
      window.location.assign(checkout.checkout_url);
    },
    onError: (error) => {
      setBillingMessage(error instanceof Error ? error.message : "Could not start checkout.");
    }
  });

  const claimCheckoutMutation = useMutation({
    mutationFn: (sessionId: string) => claimCheckout(sessionId),
    onSuccess: (access) => {
      saveBillingAccess(access);
      setBillingMessage("Credits added. You can run the audit now.");
      window.history.replaceState({}, document.title, window.location.pathname);
    },
    onError: (error) => {
      setBillingMessage(error instanceof Error ? error.message : "Could not confirm checkout.");
    }
  });

  const redeemMutation = useMutation({
    mutationFn: ({ email, code }: { email: string; code: string }) =>
      redeemInvite({ email, inviteCode: code }),
    onSuccess: (access) => {
      saveBillingAccess(access);
      setInviteCode("");
      setBillingMessage("Invite code applied. Credits are ready.");
    },
    onError: (error) => {
      setBillingMessage(error instanceof Error ? error.message : "Could not redeem that invite code.");
    }
  });

  const createAuditMutation = useMutation({
    mutationFn: ({
      file,
      declaredDurationSeconds,
      accessToken
    }: {
      file: File;
      declaredDurationSeconds: number | null;
      accessToken: string | null;
    }) =>
      createUploadAudit({
        file,
        declaredDurationSeconds,
        accessToken
      }),
    onSuccess: (audit) => {
      setFormError(null);
      setSeedAudit(audit);
      setActiveAuditId(audit.audit_id);
      queryClient.invalidateQueries({ queryKey: ["billing"] });
      queryClient.setQueryData(["audit", audit.audit_id], audit);
    },
    onError: (error) => {
      setSeedAudit(null);
      setActiveAuditId(null);
      setFormError(error instanceof Error ? error.message : "Unable to start the audit.");
    }
  });

  useEffect(() => {
    const sessionId = new URLSearchParams(window.location.search).get("checkout_session_id");
    if (sessionId) {
      claimCheckoutMutation.mutate(sessionId);
    }
  }, []);

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
  const canSubmit =
    Boolean(uploadFile) &&
    billingStatusReady &&
    !createAuditMutation.isPending &&
    !billingLocked &&
    (!paywallEnabled || (!durationError && Boolean(billingToken) && hasEnoughCredits));
  const submitButtonLabel = createAuditMutation.isPending
    ? "Starting audit..."
    : uploadFile && billingQuery.isPending
      ? "Checking access..."
      : "Run audit";

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

    if (paywallEnabled) {
      if (!billingToken) {
        setFormError("Buy credits or redeem an invite code before running an audit.");
        return;
      }
      if (durationError || uploadDurationSeconds === null) {
        setFormError("Wait for the video duration check to finish before running the audit.");
        return;
      }
      if (uploadDurationSeconds > maxVideoSeconds) {
        setFormError(`Portfolio demo audits are limited to ${formatDuration(maxVideoSeconds)}.`);
        return;
      }
      if (!hasEnoughCredits) {
        setFormError(`This audit needs ${requiredCredits} credits. Add credits or use an invite code.`);
        return;
      }
    }

    setFormError(null);
    resetPendingAudit();
    createAuditMutation.mutate({
      file: uploadFile,
      declaredDurationSeconds: paywallEnabled ? uploadDurationSeconds : null,
      accessToken: paywallEnabled ? billingToken : null
    });
  }

  function handleUploadChange(event: ChangeEvent<HTMLInputElement>) {
    const nextFile = event.target.files?.[0] ?? null;
    setUploadFile(nextFile);
    setUploadDurationSeconds(null);
    setDurationError(null);
    if (formError) {
      setFormError(null);
    }
    if (!nextFile) {
      return;
    }
    loadVideoDuration(nextFile)
      .then((duration) => {
        setUploadDurationSeconds(duration);
        if (duration > maxVideoSeconds) {
          setDurationError(`Portfolio demo audits are limited to ${formatDuration(maxVideoSeconds)}.`);
        }
      })
      .catch(() => {
        setDurationError("Could not read the video duration. Try another video file.");
      });
  }

  function handleCheckout() {
    setBillingMessage(null);
    checkoutMutation.mutate(billingEmail);
  }

  function handleRedeemInvite() {
    setBillingMessage(null);
    redeemMutation.mutate({
      email: billingEmail,
      code: inviteCode
    });
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
              <h1>AI-powered review for YouTube ad compliance.</h1>
              <p className="hero-copy">
                A demo project built with RAG, GPT-4o, Text Embedding 3, and Azure AI vector
                search to assess ad creative against YouTube advertising guidance.
              </p>
            </div>
          </div>

          {showAccessPanel ? (
            <section className="access-panel" aria-label="Demo access">
              <div className="access-copy">
                <p className="hero-callout-label">Portfolio demo access</p>
                <h2>Credits only cover cloud processing costs.</h2>
                {billingLocked ? (
                  <p>
                    Billing status could not be loaded from the backend. Check paywall environment
                    variables and redeploy, then refresh this page.
                  </p>
                ) : (
                  <p>
                    This is not a commercial product. Each audit uses paid Azure services, so credits
                    keep random traffic from creating surprise cloud bills. Recruiters and evaluators
                    can use an invite code if I have shared one with them.
                  </p>
                )}
              </div>

              <div className="access-controls">
                <label className="input-label" htmlFor="billing-email">
                  Email
                </label>
                <input
                  id="billing-email"
                  className="url-input"
                  type="email"
                  value={billingEmail}
                  onChange={(event) => setBillingEmail(event.target.value)}
                  placeholder="you@example.com"
                />

                <div className="access-actions">
                  <button
                    className="secondary-button"
                    type="button"
                    disabled={!billingEmail || checkoutMutation.isPending || billingLocked}
                    onClick={handleCheckout}
                  >
                    {checkoutMutation.isPending
                      ? "Opening checkout..."
                      : `Buy ${paywallConfig?.pack_credits ?? 3} credits - ${formatCurrencyCents(
                          paywallConfig?.pack_price_cents ?? 300
                        )}`}
                  </button>
                  <span className="credit-balance">{availableCredits} credits available</span>
                </div>

                {(paywallConfig?.invite_enabled ?? true) ? (
                  <div className="invite-row">
                    <input
                      className="url-input"
                      type="text"
                      value={inviteCode}
                      onChange={(event) => setInviteCode(event.target.value)}
                      placeholder="Invite code"
                    />
                    <button
                      className="secondary-button secondary-button-muted"
                      type="button"
                      disabled={!billingEmail || !inviteCode || redeemMutation.isPending || billingLocked}
                      onClick={handleRedeemInvite}
                    >
                      {redeemMutation.isPending ? "Applying..." : "Use invite code"}
                    </button>
                  </div>
                ) : null}

                {billingMessage ? <p className="inline-note">{billingMessage}</p> : null}
              </div>
            </section>
          ) : null}

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
                {submitButtonLabel}
              </button>
            </div>

            <div className="helper-row">
              <span>{UPLOAD_COPY.helper}</span>
              {uploadFile ? <span className="helper-chip">File: {uploadFile.name}</span> : null}
              {paywallEnabled && uploadFile && uploadDurationSeconds !== null && !durationError ? (
                <span className="helper-chip">
                  This audit will use {requiredCredits} {requiredCredits === 1 ? "credit" : "credits"}
                </span>
              ) : null}
              {paywallEnabled && uploadFile && uploadDurationSeconds === null && !durationError ? (
                <span className="helper-chip">Checking video duration...</span>
              ) : null}
            </div>

            {paywallEnabled && durationError ? <p className="inline-error">{durationError}</p> : null}
            {billingQuery.isError ? (
              <p className="inline-error">Could not load credit status. Audit runs are locked for now.</p>
            ) : null}
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

        <footer className="app-footer">
          <span>Built as an Azure AI demo project.</span>
          <a
            href="https://github.com/srikara202/youtube-ad-compliance-checker"
            target="_blank"
            rel="noreferrer"
          >
            View the project on GitHub
          </a>
        </footer>
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

function loadVideoDuration(file: File): Promise<number> {
  return new Promise((resolve, reject) => {
    const objectUrl = URL.createObjectURL(file);
    const video = document.createElement("video");
    video.preload = "metadata";
    video.onloadedmetadata = () => {
      URL.revokeObjectURL(objectUrl);
      if (Number.isFinite(video.duration) && video.duration > 0) {
        resolve(video.duration);
        return;
      }
      reject(new Error("Invalid video duration."));
    };
    video.onerror = () => {
      URL.revokeObjectURL(objectUrl);
      reject(new Error("Could not read video duration."));
    };
    video.src = objectUrl;
  });
}

function formatDuration(seconds: number): string {
  const minutes = Math.ceil(seconds / 60);
  return `${minutes} ${minutes === 1 ? "minute" : "minutes"}`;
}

function formatCurrencyCents(cents: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0
  }).format(cents / 100);
}
