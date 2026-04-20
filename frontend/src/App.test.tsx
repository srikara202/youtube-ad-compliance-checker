import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
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

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("App", () => {
  it("renders upload as the only supported input mode", () => {
    vi.stubGlobal("fetch", vi.fn());

    renderApp();

    expect(screen.getByText(/ai-powered review for youtube ad compliance/i)).toBeInTheDocument();
    expect(screen.getByText(/azure ai vector search/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/video file/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /view the project on github/i })).toHaveAttribute(
      "href",
      "https://github.com/srikara202/youtube-ad-compliance-checker"
    );
    expect(screen.queryByRole("button", { name: /youtube/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /blob url/i })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /run audit/i })).toBeDisabled();
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
              video_url: "uploaded://ad.mp4",
              source_type: "upload",
              source_label: "ad.mp4",
              youtube_video_id: null,
              title: "Ad",
              thumbnail_url: null
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
            video_url: "uploaded://ad.mp4",
            source_type: "upload",
            source_label: "ad.mp4",
            youtube_video_id: null,
            title: "Ad",
            thumbnail_url: null
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
    const file = new File(["video-data"], "ad.mp4", { type: "video/mp4" });

    await user.upload(screen.getByLabelText(/video file/i), file);
    await user.click(screen.getByRole("button", { name: /run audit/i }));

    expect(await screen.findByText(/video indexing failed in azure/i)).toBeInTheDocument();
    expect(screen.getByText(/the audit did not finish/i)).toBeInTheDocument();

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledTimes(2);
    });
  });

  it("keeps submit disabled until a file is selected", () => {
    vi.stubGlobal("fetch", vi.fn());

    renderApp();
    expect(screen.getByRole("button", { name: /run audit/i })).toBeDisabled();
  });
});
