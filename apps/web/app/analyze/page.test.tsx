import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import AnalyzePage from "./page";

afterEach(() => {
  vi.restoreAllMocks();
});

describe("analysis workspace", () => {
  it("shows provider errors without presenting fake results", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        json: async () => ({ detail: "GitHub rate limit blocked the request." }),
      }),
    );
    render(<AnalyzePage />);
    fireEvent.change(screen.getByPlaceholderText("https://github.com/owner/repository"), {
      target: { value: "https://github.com/a/b" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Analyze" }));
    expect(await screen.findByText("GitHub rate limit blocked the request.")).toBeTruthy();
    expect(screen.queryByText("ANALYSIS COMPLETE")).toBeNull();
  });

  it("renders evidence-backed results and a share link", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => report,
      }),
    );
    render(<AnalyzePage />);
    fireEvent.change(screen.getByPlaceholderText("https://github.com/owner/repository"), {
      target: { value: "https://github.com/a/b" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Analyze" }));
    await waitFor(() => expect(screen.getByText("a / b")).toBeTruthy());
    expect(screen.getByText("Python")).toBeTruthy();
    expect(screen.getByRole("link", { name: "Share report" }).getAttribute("href")).toBe(
      "/analysis/public-id",
    );
    expect(screen.getByText("Commands are display-only")).toBeTruthy();
    expect(screen.getByRole("navigation", { name: "Report sections" })).toBeTruthy();
  });

  it("clearly labels cached and partial reports", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ ...report, cache_status: "cached", snapshot: { ...report.snapshot, ingestion_warnings: ["README was too large to read."] } }),
    }));
    render(<AnalyzePage />);
    fireEvent.change(screen.getByPlaceholderText("https://github.com/owner/repository"), { target: { value: "https://github.com/a/b" } });
    fireEvent.click(screen.getByRole("button", { name: "Analyze" }));
    expect(await screen.findByText("Cached report reused")).toBeTruthy();
    expect(screen.getByText("Partial analysis")).toBeTruthy();
    expect(screen.getByText("README was too large to read.")).toBeTruthy();
  });
});

const report = {
  public_id: "public-id",
  snapshot: {
    repository: { owner: "a", name: "b", canonical_url: "https://github.com/a/b" },
    metadata: { description: "Example", stars: 1, forks: 0, open_issues: 0 },
    files: [{ path: "main.py" }],
  },
  analysis: {
    purpose_summary: "Example project",
    project_types: ["General software repository"],
    languages: [{ name: "Python", share_percent: 100, evidence: ["main.py"] }],
    technologies: [],
    dependencies: [],
    runtimes: [],
    important_files: [],
    scores: [],
    setup_steps: [],
    prerequisites: [],
    compatibility: [],
    strengths: [],
    risks: [],
    missing_essentials: [],
    unknowns: [],
  },
};
