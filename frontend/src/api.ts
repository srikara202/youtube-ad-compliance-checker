import type { AuditJobResponse } from "./types";

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
  sourceUrl
}: {
  sourceType: "youtube" | "media_url";
  sourceUrl: string;
}): Promise<AuditJobResponse> {
  return fetchJson<AuditJobResponse>("/audits", {
    method: "POST",
    body: JSON.stringify({
      source_type: sourceType,
      source_url: sourceUrl
    })
  });
}

export async function createUploadAudit(file: File): Promise<AuditJobResponse> {
  const formData = new FormData();
  formData.append("file", file);

  return fetchJson<AuditJobResponse>("/audits/upload", {
    method: "POST",
    body: formData
  });
}

export async function getAudit(auditId: string): Promise<AuditJobResponse> {
  return fetchJson<AuditJobResponse>(`/audits/${auditId}`);
}

export { ApiError };
