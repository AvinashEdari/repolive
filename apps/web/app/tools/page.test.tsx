import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import ToolsPage from "./page";

afterEach(() => vi.restoreAllMocks());

describe("product tools", () => {
  it("diagnoses pasted errors without rendering the hostile input", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => ({ label: "Missing dependency", confidence: "high", evidence: ["Repository dependency evidence: fastapi."], safe_next_checks: ["Check the manifest."], unknowns: ["Local state is unknown."], disclaimer: "Not a confirmed root cause." }) }));
    render(<ToolsPage/>);
    fireEvent.change(screen.getByPlaceholderText("Public analysis ID"), { target: { value: "analysis-id" } });
    fireEvent.change(screen.getByPlaceholderText("Paste the error message here"), { target: { value: "<script>secret()</script> ModuleNotFoundError" } });
    fireEvent.click(screen.getByRole("button", { name: "Diagnose safely" }));
    expect(await screen.findByText("Missing dependency")).toBeTruthy();
    expect(screen.queryByText(/secret\(\)/)).toBeNull();
  });

  it("renders a cached comparison table", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => ({ left_repository: "a/one", right_repository: "b/two", dimensions: [{ name: "Languages", left: "Python", right: "TypeScript", explanation: "Known bytes." }], shared_dependencies: [], summary: ["Different languages."], unknowns: ["Commits only."] }) }));
    render(<ToolsPage/>);
    const inputs = screen.getAllByRole("textbox");
    fireEvent.change(inputs[2], { target: { value: "left-id-1" } });
    fireEvent.change(inputs[3], { target: { value: "right-id-2" } });
    fireEvent.click(screen.getByRole("button", { name: "Compare" }));
    expect(await screen.findByText("a/one vs b/two")).toBeTruthy();
    expect(screen.getByRole("table")).toBeTruthy();
  });

  it("shows transparent discovery ranking", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => ({ cost: "One bounded request.", items: [{ full_name: "a/project", url: "https://github.com/a/project", description: "Example", primary_language: "Python", stars: 20, score: 70, ranking_reasons: ["License declared (+10)."] }] }) }));
    render(<ToolsPage/>);
    fireEvent.change(screen.getByPlaceholderText("accessibility"), { target: { value: "api" } });
    fireEvent.click(screen.getByRole("button", { name: "Search GitHub" }));
    expect(await screen.findByText("a/project")).toBeTruthy();
    expect(screen.getByText("License declared (+10).")).toBeTruthy();
    expect(screen.getByText("70/100")).toBeTruthy();
  });
});
