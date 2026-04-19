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
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {})
    },
    ...init
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

export async function createAudit(videoUrl: string): Promise<AuditJobResponse> {
  return fetchJson<AuditJobResponse>("/audits", {
    method: "POST",
    body: JSON.stringify({ video_url: videoUrl })
  });
}

export async function getAudit(auditId: string): Promise<AuditJobResponse> {
  return fetchJson<AuditJobResponse>(`/audits/${auditId}`);
}

export { ApiError };
