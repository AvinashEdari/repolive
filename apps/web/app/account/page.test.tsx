import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const auth = vi.hoisted(() => ({
  getAccessToken: vi.fn(),
  listener: undefined as undefined | (() => void),
  signInWithPassword: vi.fn(),
  signOut: vi.fn(),
  signUp: vi.fn(),
  unsubscribe: vi.fn(),
}));

vi.mock("../../lib/supabase", () => ({
  getAccessToken: auth.getAccessToken,
  getSupabaseClient: () => ({
    auth: {
      onAuthStateChange: (listener: () => void) => {
        auth.listener = listener;
        return { data: { subscription: { unsubscribe: auth.unsubscribe } } };
      },
      signInWithPassword: auth.signInWithPassword,
      signOut: auth.signOut,
      signUp: auth.signUp,
    },
  }),
}));

import AccountPage from "./page";

describe("account authentication", () => {
  beforeEach(() => {
    auth.getAccessToken.mockResolvedValue(null);
    auth.signInWithPassword.mockResolvedValue({ error: null });
    auth.signOut.mockResolvedValue({ error: null });
    auth.signUp.mockResolvedValue({ error: null });
  });

  afterEach(() => {
    vi.clearAllMocks();
    vi.unstubAllGlobals();
    auth.listener = undefined;
  });

  it("shows a safe invalid-login message", async () => {
    auth.signInWithPassword.mockResolvedValue({ error: { message: "Invalid credentials" } });
    render(<AccountPage />);

    fireEvent.change(screen.getByLabelText("Email address"), {
      target: { value: "person@example.com" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "incorrect-password" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByText("Invalid credentials")).toBeTruthy();
    expect(auth.signInWithPassword).toHaveBeenCalledWith({
      email: "person@example.com",
      password: "incorrect-password",
    });
  });

  it("clears an invalid server session and asks the user to sign in again", async () => {
    auth.getAccessToken.mockResolvedValue("expired-token");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 401 }));
    render(<AccountPage />);

    auth.listener?.();

    await waitFor(() => expect(auth.signOut).toHaveBeenCalled());
    expect(
      screen.getByText("Your session expired. Sign in again to view private history."),
    ).toBeTruthy();
    expect(screen.getByRole("button", { name: "Sign in" })).toBeTruthy();
  });

  it("uses an idempotent hosted-checkout request and explains unavailable billing", async () => {
    auth.getAccessToken.mockResolvedValue("valid-token");
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({ ok: true, status: 200, json: async () => [] })
      .mockResolvedValueOnce({ ok: true, status: 200, json: async () => ({ plan: "free" }) })
      .mockResolvedValueOnce({
        ok: false,
        status: 503,
        json: async () => ({ detail: "Billing is not configured." }),
      });
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("crypto", { randomUUID: () => "checkout-request-1" });
    render(<AccountPage />);

    auth.listener?.();
    const upgrade = await screen.findByRole("button", { name: "Upgrade to Pro" });
    fireEvent.click(upgrade);

    expect(await screen.findByText("Billing is not configured.")).toBeTruthy();
    expect(fetchMock).toHaveBeenLastCalledWith(
      "http://localhost:8000/api/v1/billing/checkout",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({ "Idempotency-Key": "checkout-request-1" }),
      }),
    );
  });
});
