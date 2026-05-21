import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "./App";

const BILLING_DISABLED = {
  email: null,
  credits: 0,
  config: {
    enabled: false,
    pack_credits: 3,
    pack_price_cents: 300,
    max_video_seconds: 180,
    credit_seconds: 60,
    invite_enabled: false
  }
};

const BILLING_ENABLED_EMPTY = {
  email: null,
  credits: 0,
  config: {
    enabled: true,
    pack_credits: 3,
    pack_price_cents: 300,
    max_video_seconds: 180,
    credit_seconds: 60,
    invite_enabled: true
  }
};

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
  window.localStorage.clear();
});

function mockVideoDuration(duration: number) {
  vi.stubGlobal("URL", {
    ...window.URL,
    createObjectURL: vi.fn(() => "blob:test-video"),
    revokeObjectURL: vi.fn()
  });
  const originalCreateElement = document.createElement.bind(document);
  vi.spyOn(document, "createElement").mockImplementation(
    ((tagName: string, options?: ElementCreationOptions) => {
      const element = originalCreateElement(tagName, options);
      if (tagName.toLowerCase() === "video") {
        Object.defineProperty(element, "duration", {
          configurable: true,
          value: duration
        });
        setTimeout(() => {
          (element as HTMLVideoElement).onloadedmetadata?.(new Event("loadedmetadata"));
        }, 0);
      }
      return element;
    }) as typeof document.createElement
  );
}

describe("App", () => {
  it("renders upload as the only supported input mode", () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(BILLING_DISABLED)));

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
    const fetchMock = vi.fn((url: string, _init?: RequestInit) => {
      if (url.endsWith("/billing/me")) {
        return Promise.resolve(jsonResponse(BILLING_DISABLED));
      }
      return Promise.resolve(
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
    });

    vi.stubGlobal("fetch", fetchMock);

    renderApp();
    const user = userEvent.setup();
    const file = new File(["video-data"], "ad.mp4", { type: "video/mp4" });

    await user.upload(screen.getByLabelText(/video file/i), file);
    await waitFor(() => {
      expect(screen.getByRole("button", { name: /run audit/i })).not.toBeDisabled();
    });
    await user.click(screen.getByRole("button", { name: /run audit/i }));

    expect(await screen.findByText("Ad")).toBeInTheDocument();
    expect(screen.getByText(/uploaded from a local file/i)).toBeInTheDocument();

    const uploadCall = fetchMock.mock.calls.find(([url]) => String(url).endsWith("/audits/upload"));
    expect(uploadCall).toBeTruthy();
    if (!uploadCall) {
      throw new Error("Expected an upload request.");
    }
    const [requestUrl, requestInit] = uploadCall;
    expect(requestUrl).toMatch(/\/audits\/upload$/);
    expect(requestInit?.method).toBe("POST");
    expect(requestInit?.body).toBeInstanceOf(FormData);
  });

  it("keeps submit disabled while billing status is loading", async () => {
    let resolveBilling!: (response: Response) => void;
    const billingPromise = new Promise<Response>((resolve) => {
      resolveBilling = resolve;
    });
    const fetchMock = vi.fn((url: string, _init?: RequestInit) => {
      if (url.endsWith("/billing/me")) {
        return billingPromise;
      }
      return Promise.resolve(jsonResponse({}));
    });

    vi.stubGlobal("fetch", fetchMock);

    renderApp();
    const user = userEvent.setup();
    const file = new File(["video-data"], "ad.mp4", { type: "video/mp4" });

    await user.upload(screen.getByLabelText(/video file/i), file);
    const checkingButton = screen.getByRole("button", { name: /checking access/i });
    expect(checkingButton).toBeDisabled();

    await user.click(checkingButton);
    expect(fetchMock.mock.calls.some(([url]) => String(url).endsWith("/audits/upload"))).toBe(false);

    resolveBilling(jsonResponse(BILLING_DISABLED));
    await waitFor(() => {
      expect(screen.getByRole("button", { name: /run audit/i })).not.toBeDisabled();
    });
  });

  it("shows the portfolio paywall copy and invite controls", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(BILLING_ENABLED_EMPTY)));

    renderApp();

    expect(await screen.findByText(/portfolio demo access/i)).toBeInTheDocument();
    expect(screen.getByText(/not a commercial product/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /buy 3 credits/i })).toBeDisabled();
    expect(screen.getByRole("button", { name: /use invite code/i })).toBeDisabled();
  });

  it("redeems an invite code and updates the credit balance", async () => {
    const fetchMock = vi.fn((url: string, init?: RequestInit) => {
      if (url.endsWith("/billing/redeem")) {
        return Promise.resolve(
          jsonResponse({
            email: "recruiter@example.com",
            credits: 3,
            access_token: "access-token",
            config: BILLING_ENABLED_EMPTY.config
          })
        );
      }
      if (url.endsWith("/billing/me")) {
        const authorization = new Headers(init?.headers).get("Authorization");
        if (authorization === "Bearer access-token") {
          return Promise.resolve(
            jsonResponse({
              email: "recruiter@example.com",
              credits: 3,
              config: BILLING_ENABLED_EMPTY.config
            })
          );
        }
      }
      return Promise.resolve(jsonResponse(BILLING_ENABLED_EMPTY));
    });

    vi.stubGlobal("fetch", fetchMock);

    renderApp();
    const user = userEvent.setup();
    await user.type(await screen.findByLabelText(/email/i), "recruiter@example.com");
    await user.type(screen.getByPlaceholderText(/invite code/i), "RECRUITER-DEMO");
    await user.click(screen.getByRole("button", { name: /use invite code/i }));

    expect(await screen.findByText(/invite code applied/i)).toBeInTheDocument();
    expect(await screen.findByText(/3 credits available/i)).toBeInTheDocument();
  });

  it("calculates credits from selected video duration", async () => {
    window.localStorage.setItem("portfolio-demo-billing-token", "access-token");
    mockVideoDuration(75);
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse({
          email: "recruiter@example.com",
          credits: 3,
          config: BILLING_ENABLED_EMPTY.config
        })
      )
    );

    renderApp();
    const user = userEvent.setup();
    const file = new File(["video-data"], "ad.mp4", { type: "video/mp4" });

    await user.upload(screen.getByLabelText(/video file/i), file);

    expect(await screen.findByText(/this audit will use 2 credits/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /run audit/i })).not.toBeDisabled();
  });

  it("sends the access token and declared duration with paywalled uploads", async () => {
    window.localStorage.setItem("portfolio-demo-billing-token", "access-token");
    mockVideoDuration(75);
    const fetchMock = vi.fn((url: string, _init?: RequestInit) => {
      if (url.endsWith("/billing/me")) {
        return Promise.resolve(
          jsonResponse({
            email: "recruiter@example.com",
            credits: 3,
            config: BILLING_ENABLED_EMPTY.config
          })
        );
      }
      return Promise.resolve(
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
    });

    vi.stubGlobal("fetch", fetchMock);

    renderApp();
    const user = userEvent.setup();
    const file = new File(["video-data"], "ad.mp4", { type: "video/mp4" });

    await user.upload(screen.getByLabelText(/video file/i), file);
    await screen.findByText(/this audit will use 2 credits/i);
    await user.click(screen.getByRole("button", { name: /run audit/i }));

    await screen.findByText("Ad");
    const uploadCall = fetchMock.mock.calls.find(([url]) => String(url).endsWith("/audits/upload"));
    expect(uploadCall).toBeTruthy();
    if (!uploadCall) {
      throw new Error("Expected an upload request.");
    }
    const [, requestInit] = uploadCall;
    const body = requestInit?.body instanceof FormData ? requestInit.body : null;
    expect(new Headers(requestInit?.headers).get("Authorization")).toBe("Bearer access-token");
    expect(body).toBeInstanceOf(FormData);
    expect(body?.get("declared_duration_seconds")).toBe("75");
  });

  it("shows a failed audit state when the backend returns an error", async () => {
    const fetchMock = vi.fn((url: string) => {
      if (url.endsWith("/billing/me")) {
        return Promise.resolve(jsonResponse(BILLING_DISABLED));
      }
      if (url.endsWith("/audits/upload")) {
        return Promise.resolve(
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
        );
      }
      return Promise.resolve(
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
    });

    vi.stubGlobal("fetch", fetchMock);

    renderApp();
    const user = userEvent.setup();
    const file = new File(["video-data"], "ad.mp4", { type: "video/mp4" });

    await user.upload(screen.getByLabelText(/video file/i), file);
    await waitFor(() => {
      expect(screen.getByRole("button", { name: /run audit/i })).not.toBeDisabled();
    });
    await user.click(screen.getByRole("button", { name: /run audit/i }));

    expect(await screen.findByText(/video indexing failed in azure/i)).toBeInTheDocument();
    expect(screen.getByText(/the audit did not finish/i)).toBeInTheDocument();

    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url]) => String(url).includes("/audits/audit-2"))).toBe(true);
    });
  });

  it("keeps submit disabled until a file is selected", () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(BILLING_DISABLED)));

    renderApp();
    expect(screen.getByRole("button", { name: /run audit/i })).toBeDisabled();
  });
});
