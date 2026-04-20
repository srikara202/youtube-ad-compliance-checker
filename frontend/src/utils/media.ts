export interface MediaUrlValidationResult {
  isValid: boolean;
  error: string | null;
  normalizedUrl: string | null;
  host: string | null;
}

export function validateRemoteMediaUrl(input: string): MediaUrlValidationResult {
  const trimmed = input.trim();
  if (!trimmed) {
    return {
      isValid: false,
      error: "Paste a direct media URL or SAS URL to start the audit.",
      normalizedUrl: null,
      host: null
    };
  }

  const candidate = trimmed.includes("://") ? trimmed : `https://${trimmed}`;

  let parsed: URL;
  try {
    parsed = new URL(candidate);
  } catch {
    return {
      isValid: false,
      error: "Enter a valid media URL.",
      normalizedUrl: null,
      host: null
    };
  }

  if (!["http:", "https:"].includes(parsed.protocol) || !parsed.hostname) {
    return {
      isValid: false,
      error: "Use an http or https media URL.",
      normalizedUrl: null,
      host: null
    };
  }

  return {
    isValid: true,
    error: null,
    normalizedUrl: parsed.toString(),
    host: parsed.hostname
  };
}
