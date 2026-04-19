const VIDEO_ID_PATTERN = /^[A-Za-z0-9_-]{6,}$/;

export interface YouTubeValidationResult {
  isValid: boolean;
  error: string | null;
  normalizedUrl: string | null;
  youtubeVideoId: string | null;
}

export function validateYouTubeUrl(input: string): YouTubeValidationResult {
  const trimmed = input.trim();
  if (!trimmed) {
    return {
      isValid: false,
      error: "Paste a YouTube link to start the audit.",
      normalizedUrl: null,
      youtubeVideoId: null
    };
  }

  const candidate = trimmed.includes("://") ? trimmed : `https://${trimmed}`;

  let parsed: URL;
  try {
    parsed = new URL(candidate);
  } catch {
    return {
      isValid: false,
      error: "Enter a valid URL.",
      normalizedUrl: null,
      youtubeVideoId: null
    };
  }

  const host = parsed.hostname.replace(/^www\./, "").toLowerCase();
  let videoId: string | null = null;

  if (host === "youtu.be") {
    videoId = parsed.pathname.split("/").filter(Boolean)[0] ?? null;
  } else if (["youtube.com", "m.youtube.com", "music.youtube.com"].includes(host)) {
    if (parsed.pathname === "/watch") {
      videoId = parsed.searchParams.get("v");
    } else if (
      parsed.pathname.startsWith("/shorts/") ||
      parsed.pathname.startsWith("/embed/") ||
      parsed.pathname.startsWith("/live/")
    ) {
      videoId = parsed.pathname.split("/").filter(Boolean)[1] ?? null;
    }
  }

  if (!videoId || !VIDEO_ID_PATTERN.test(videoId)) {
    return {
      isValid: false,
      error: "Use a YouTube watch, short, embed, or share link.",
      normalizedUrl: null,
      youtubeVideoId: null
    };
  }

  return {
    isValid: true,
    error: null,
    normalizedUrl: `https://www.youtube.com/watch?v=${videoId}`,
    youtubeVideoId: videoId
  };
}
