import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { MachineCheckPanel } from "./machine-check-panel";

afterEach(() => vi.restoreAllMocks());

it("submits machine details and explains an incompatible result", async () => {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    json: async () => ({
      status: "incompatible",
      summary: "Python is older than the repository requirement.",
      conditions: [{ subject: "Python", status: "incompatible", detail: "Installed 3.8; repository declares >=3.9.", evidence: ["pyproject.toml"] }],
    }),
  });
  vi.stubGlobal("fetch", fetchMock);
  render(<MachineCheckPanel publicId="public-id" />);
  fireEvent.change(screen.getByPlaceholderText("3.12"), { target: { value: "3.8" } });
  fireEvent.click(screen.getByRole("button", { name: "Check my machine" }));
  expect(await screen.findByText("Compatibility result")).toBeTruthy();
  expect(screen.getAllByText("incompatible").length).toBeGreaterThan(0);
  expect(fetchMock).toHaveBeenCalledOnce();
});
