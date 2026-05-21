import type {
  AuditJobResponse,
  BillingAccessResponse,
  BillingCheckoutResponse,
  BillingMeResponse
} from "./types";

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? "").trim();

class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers ?? {});
  if (!(init?.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers
  });

  if (!response.ok) {
    let message = "The request could not be completed.";
    try {
      const errorBody = (await response.json()) as { detail?: string };
      if (errorBody.detail) {
        message = errorBody.detail;
      }
    } catch {
      message = response.statusText || message;
    }
    throw new ApiError(message, response.status);
  }

  return (await response.json()) as T;
}

export async function createUrlAudit({
  sourceType,
  sourceUrl,
  accessToken = null
}: {
  sourceType: "youtube" | "media_url";
  sourceUrl: string;
  accessToken?: string | null;
}): Promise<AuditJobResponse> {
  return fetchJson<AuditJobResponse>("/audits", {
    method: "POST",
    headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : undefined,
    body: JSON.stringify({
      source_type: sourceType,
      source_url: sourceUrl
    })
  });
}

export async function getBillingMe(accessToken: string | null): Promise<BillingMeResponse> {
  const headers = accessToken ? { Authorization: `Bearer ${accessToken}` } : undefined;
  return fetchJson<BillingMeResponse>("/billing/me", { headers });
}

export async function createCheckout(email: string): Promise<BillingCheckoutResponse> {
  return fetchJson<BillingCheckoutResponse>("/billing/checkout", {
    method: "POST",
    body: JSON.stringify({ email })
  });
}

export async function claimCheckout(sessionId: string): Promise<BillingAccessResponse> {
  return fetchJson<BillingAccessResponse>("/billing/claim-checkout", {
    method: "POST",
    body: JSON.stringify({ session_id: sessionId })
  });
}

export async function redeemInvite({
  email,
  inviteCode
}: {
  email: string;
  inviteCode: string;
}): Promise<BillingAccessResponse> {
  return fetchJson<BillingAccessResponse>("/billing/redeem", {
    method: "POST",
    body: JSON.stringify({
      email,
      invite_code: inviteCode
    })
  });
}

export async function createUploadAudit({
  file,
  declaredDurationSeconds,
  accessToken
}: {
  file: File;
  declaredDurationSeconds: number | null;
  accessToken: string | null;
}): Promise<AuditJobResponse> {
  const formData = new FormData();
  formData.append("file", file);
  if (declaredDurationSeconds !== null) {
    formData.append("declared_duration_seconds", String(declaredDurationSeconds));
  }

  return fetchJson<AuditJobResponse>("/audits/upload", {
    method: "POST",
    headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : undefined,
    body: formData
  });
}

export async function getAudit(auditId: string): Promise<AuditJobResponse> {
  return fetchJson<AuditJobResponse>(`/audits/${auditId}`);
}

export { ApiError };
