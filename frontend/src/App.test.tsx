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

function setVideoUrl(value: string) {
  fireEvent.change(screen.getByLabelText(/youtube url/i), {
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
  it("shows inline validation for unsupported links", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    renderApp();
    setVideoUrl("https://example.com/ad");

    expect(screen.getByText(/use a youtube watch, short, embed, or share link/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /run audit/i })).toBeDisabled();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("renders video preview and completed audit results", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse({
          audit_id: "audit-1",
          job_status: "QUEUED",
          video: {
            video_url: "https://www.youtube.com/watch?v=abc123xyz45",
            youtube_video_id: "abc123xyz45",
            title: "Acme Spring Promo",
            thumbnail_url: "https://example.com/thumb.jpg"
          },
          result: null,
          error: null,
          created_at: "2026-04-19T00:00:00+00:00",
          updated_at: "2026-04-19T00:00:00+00:00"
        }, 202)
      )
      .mockResolvedValueOnce(
        jsonResponse({
          audit_id: "audit-1",
          job_status: "COMPLETED",
          video: {
            video_url: "https://www.youtube.com/watch?v=abc123xyz45",
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

    setVideoUrl("https://youtu.be/abc123xyz45");
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

  it("shows a failed audit state when the backend returns an error", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse({
          audit_id: "audit-2",
          job_status: "QUEUED",
          video: {
            video_url: "https://www.youtube.com/watch?v=abc123xyz45",
            youtube_video_id: "abc123xyz45",
            title: "Acme Spring Promo",
            thumbnail_url: "https://example.com/thumb.jpg"
          },
          result: null,
          error: null,
          created_at: "2026-04-19T00:00:00+00:00",
          updated_at: "2026-04-19T00:00:00+00:00"
        }, 202)
      )
      .mockResolvedValueOnce(
        jsonResponse({
          audit_id: "audit-2",
          job_status: "FAILED",
          video: {
            video_url: "https://www.youtube.com/watch?v=abc123xyz45",
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

    setVideoUrl("https://youtu.be/abc123xyz45");
    await user.click(screen.getByRole("button", { name: /run audit/i }));

    expect(await screen.findByText(/video indexing failed in azure/i)).toBeInTheDocument();
    expect(screen.getByText(/the audit did not finish/i)).toBeInTheDocument();
  });
});
