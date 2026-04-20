import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "./App";

function renderApp() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false
      },
      mutations: {
        retry: false
      }
    }
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  );
}

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      "Content-Type": "application/json"
    }
  });
}

function setYouTubeUrl(value: string) {
  fireEvent.change(screen.getByLabelText(/youtube url/i), {
    target: {
      value
    }
  });
}

function setMediaUrl(value: string) {
  fireEvent.change(screen.getByLabelText(/media url or sas url/i), {
    target: {
      value
    }
  });
}

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("App", () => {
  it("shows inline validation for unsupported YouTube links", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    renderApp();
    setYouTubeUrl("https://example.com/ad");

    expect(screen.getByText(/use a youtube watch, short, embed, or share link/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /run audit/i })).toBeDisabled();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("renders video preview and completed audit results for YouTube links", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse(
          {
            audit_id: "audit-1",
            job_status: "QUEUED",
            video: {
              video_url: "https://www.youtube.com/watch?v=abc123xyz45",
              source_type: "youtube",
              source_label: "abc123xyz45",
              youtube_video_id: "abc123xyz45",
              title: "Acme Spring Promo",
              thumbnail_url: "https://example.com/thumb.jpg"
            },
            result: null,
            error: null,
            created_at: "2026-04-19T00:00:00+00:00",
            updated_at: "2026-04-19T00:00:00+00:00"
          },
          202
        )
      )
      .mockResolvedValueOnce(
        jsonResponse({
          audit_id: "audit-1",
          job_status: "COMPLETED",
          video: {
            video_url: "https://www.youtube.com/watch?v=abc123xyz45",
            source_type: "youtube",
            source_label: "abc123xyz45",
            youtube_video_id: "abc123xyz45",
            title: "Acme Spring Promo",
            thumbnail_url: "https://example.com/thumb.jpg"
          },
          result: {
            status: "FAIL",
            compliance_results: [
              {
                category: "FTC Disclosure",
                severity: "CRITICAL",
                description: "Missing sponsorship disclosure in the spoken content."
              }
            ],
            final_report: "## Final report\n\nFlagged a disclosure gap in the ad."
          },
          error: null,
          created_at: "2026-04-19T00:00:00+00:00",
          updated_at: "2026-04-19T00:01:00+00:00"
        })
      );

    vi.stubGlobal("fetch", fetchMock);

    renderApp();
    const user = userEvent.setup();

    setYouTubeUrl("https://youtu.be/abc123xyz45");
    await user.click(screen.getByRole("button", { name: /run audit/i }));

    expect(await screen.findByText("Acme Spring Promo")).toBeInTheDocument();
    expect(await screen.findByText(/compliance fail/i)).toBeInTheDocument();
    expect(screen.getByText("FTC Disclosure")).toBeInTheDocument();
    expect(screen.getByText(/missing sponsorship disclosure/i)).toBeInTheDocument();
    expect(screen.getByText(/flagged a disclosure gap in the ad/i)).toBeInTheDocument();

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledTimes(2);
    });
  });

  it("submits a Blob or SAS URL through the media source mode", async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(
      jsonResponse(
        {
          audit_id: "audit-media",
          job_status: "COMPLETED",
          video: {
            video_url: "https://storageaccount.blob.core.windows.net/videos/ad.mp4?sig=test",
            source_type: "media_url",
            source_label: "ad.mp4",
            youtube_video_id: null,
            title: "Ad",
            thumbnail_url: null
          },
          result: {
            status: "PASS",
            compliance_results: [],
            final_report: "No issues found."
          },
          error: null,
          created_at: "2026-04-19T00:00:00+00:00",
          updated_at: "2026-04-19T00:01:00+00:00"
        },
        202
      )
    );

    vi.stubGlobal("fetch", fetchMock);

    renderApp();
    const user = userEvent.setup();

    await user.click(screen.getByRole("button", { name: /blob url/i }));
    setMediaUrl("https://storageaccount.blob.core.windows.net/videos/ad.mp4?sig=test");
    await user.click(screen.getByRole("button", { name: /run audit/i }));

    expect(await screen.findByText("Ad")).toBeInTheDocument();
    expect(screen.getByText(/compliance pass/i)).toBeInTheDocument();

    const [requestUrl, requestInit] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(requestUrl).toMatch(/\/audits$/);
    expect(requestInit.method).toBe("POST");
    expect(requestInit.body).toContain("\"source_type\":\"media_url\"");
  });

  it("submits uploads through the multipart endpoint", async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(
      jsonResponse(
        {
          audit_id: "audit-upload",
          job_status: "COMPLETED",
          video: {
            video_url: "uploaded://ad.mp4",
            source_type: "upload",
            source_label: "ad.mp4",
            youtube_video_id: null,
            title: "Ad",
            thumbnail_url: null
          },
          result: {
            status: "PASS",
            compliance_results: [],
            final_report: "No issues found."
          },
          error: null,
          created_at: "2026-04-19T00:00:00+00:00",
          updated_at: "2026-04-19T00:01:00+00:00"
        },
        202
      )
    );

    vi.stubGlobal("fetch", fetchMock);

    renderApp();
    const user = userEvent.setup();
    const file = new File(["video-data"], "ad.mp4", { type: "video/mp4" });

    await user.click(screen.getByRole("button", { name: /upload/i }));
    await user.upload(screen.getByLabelText(/video file/i), file);
    await user.click(screen.getByRole("button", { name: /run audit/i }));

    expect(await screen.findByText("Ad")).toBeInTheDocument();
    expect(screen.getByText(/uploaded from a local file/i)).toBeInTheDocument();

    const [requestUrl, requestInit] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(requestUrl).toMatch(/\/audits\/upload$/);
    expect(requestInit.method).toBe("POST");
    expect(requestInit.body).toBeInstanceOf(FormData);
  });

  it("shows a failed audit state when the backend returns an error", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse(
          {
            audit_id: "audit-2",
            job_status: "QUEUED",
            video: {
              video_url: "https://www.youtube.com/watch?v=abc123xyz45",
              source_type: "youtube",
              source_label: "abc123xyz45",
              youtube_video_id: "abc123xyz45",
              title: "Acme Spring Promo",
              thumbnail_url: "https://example.com/thumb.jpg"
            },
            result: null,
            error: null,
            created_at: "2026-04-19T00:00:00+00:00",
            updated_at: "2026-04-19T00:00:00+00:00"
          },
          202
        )
      )
      .mockResolvedValueOnce(
        jsonResponse({
          audit_id: "audit-2",
          job_status: "FAILED",
          video: {
            video_url: "https://www.youtube.com/watch?v=abc123xyz45",
            source_type: "youtube",
            source_label: "abc123xyz45",
            youtube_video_id: "abc123xyz45",
            title: "Acme Spring Promo",
            thumbnail_url: "https://example.com/thumb.jpg"
          },
          result: null,
          error: "Video indexing failed in Azure.",
          created_at: "2026-04-19T00:00:00+00:00",
          updated_at: "2026-04-19T00:01:00+00:00"
        })
      );

    vi.stubGlobal("fetch", fetchMock);

    renderApp();
    const user = userEvent.setup();

    setYouTubeUrl("https://youtu.be/abc123xyz45");
    await user.click(screen.getByRole("button", { name: /run audit/i }));

    expect(await screen.findByText(/video indexing failed in azure/i)).toBeInTheDocument();
    expect(screen.getByText(/the audit did not finish/i)).toBeInTheDocument();
  });
});
