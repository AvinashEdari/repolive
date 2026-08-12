"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { getAccessToken, getSupabaseClient } from "../../lib/supabase";
import { SiteHeader } from "../components/site-header";

type HistoryItem = {
  public_id: string;
  owner: string;
  repository_name: string;
  commit_sha: string;
  saved_at: string;
  scores: { name: string; value: number }[];
};

const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export default function AccountPage() {
  const supabase = getSupabaseClient();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState(
    supabase
      ? "Sign in to save and revisit analyses."
      : "Accounts are not configured in this environment.",
  );
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [signedIn, setSignedIn] = useState(false);
  const [plan, setPlan] = useState<"free" | "pro">("free");
  const [billingAvailable, setBillingAvailable] = useState(false);

  const expireSession = useCallback(async () => {
    await supabase?.auth.signOut();
    setSignedIn(false);
    setHistory([]);
    setMessage("Your session expired. Sign in again to view private history.");
  }, [supabase]);

  const loadHistory = useCallback(async () => {
    const token = await getAccessToken();
    setSignedIn(Boolean(token));
    if (!token) {
      setHistory([]);
      return;
    }
    try {
      const response = await fetch(`${apiUrl}/api/v1/analyses/me/history`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (response.status === 401) {
        await expireSession();
      } else if (response.ok) {
        setHistory((await response.json()) as HistoryItem[]);
        const entitlementResponse = await fetch(`${apiUrl}/api/v1/me/entitlements`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (entitlementResponse.ok) {
          const entitlements = (await entitlementResponse.json()) as { plan: "free" | "pro" };
          setPlan(entitlements.plan);
        }
        const billingResponse = await fetch(`${apiUrl}/api/v1/billing/status`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (billingResponse.ok) {
          const billing = (await billingResponse.json()) as { configured: boolean };
          setBillingAvailable(billing.configured);
        }
      } else {
        setMessage("Saved analyses are temporarily unavailable. Please retry.");
      }
    } catch {
      setMessage("Could not reach RepoLive. Check your connection and retry.");
    }
  }, [expireSession]);

  useEffect(() => {
    if (!supabase) return;
    const { data } = supabase.auth.onAuthStateChange(() => {
      void loadHistory();
    });
    return () => data.subscription.unsubscribe();
  }, [loadHistory, supabase]);

  async function submit(event: FormEvent, mode: "signin" | "signup") {
    event.preventDefault();
    if (!supabase) return;
    const result =
      mode === "signin"
        ? await supabase.auth.signInWithPassword({ email, password })
        : await supabase.auth.signUp({ email, password });
    setMessage(
      result.error?.message ??
        (mode === "signin"
          ? "Signed in."
          : "Account created. Check your email if confirmation is enabled."),
    );
  }

  async function remove(publicId: string) {
    const token = await getAccessToken();
    if (!token) return;
    const response = await fetch(`${apiUrl}/api/v1/analyses/me/history/${publicId}`, {
      method: "DELETE",
      headers: { Authorization: `Bearer ${token}` },
    });
    if (response.status === 401) await expireSession();
    else if (response.ok) await loadHistory();
    else setMessage("That saved analysis could not be removed. Please retry.");
  }

  async function openBilling(kind: "checkout" | "portal") {
    const token = await getAccessToken();
    if (!token) return;
    const body =
      kind === "checkout"
        ? JSON.stringify({
            success_url: `${window.location.origin}/account?billing=success`,
            cancel_url: `${window.location.origin}/account?billing=canceled`,
          })
        : undefined;
    try {
      const response = await fetch(`${apiUrl}/api/v1/billing/${kind}`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
          "Idempotency-Key": crypto.randomUUID(),
        },
        body,
      });
      const result = (await response.json()) as { url?: string; detail?: string };
      if (response.ok && result.url) window.location.assign(result.url);
      else setMessage(result.detail ?? "Billing is currently unavailable.");
    } catch {
      setMessage("Could not reach billing. Check your connection and retry.");
    }
  }

  return (
    <div className="pageShell">
      <SiteHeader context="Your account" />
      <main id="main-content" className="authLayout">
        <section className="panel">
          <p className="eyebrow">Account</p>
          <h1>Your account</h1>
          <p className="muted">
            Accounts are optional. Sign in to keep a private list of reports you want to revisit.
          </p>
          <p className="notice" role="status" aria-live="polite">
            {message}
          </p>
          {!signedIn && (
            <form className="stack" onSubmit={(event) => void submit(event, "signin")}>
              <div className="field">
                <label htmlFor="account-email">Email address</label>
                <input
                  id="account-email"
                  type="email"
                  autoComplete="email"
                  required
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                />
              </div>
              <div className="field">
                <label htmlFor="account-password">Password</label>
                <input
                  id="account-password"
                  type="password"
                  autoComplete="current-password"
                  required
                  minLength={8}
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                />
                <small className="muted">
                  At least 8 characters. RepoLive does not store your password.
                </small>
              </div>
              <div className="buttonRow">
                <button type="submit" className="primaryButton">
                  Sign in
                </button>
                <button
                  type="button"
                  className="secondaryButton"
                  onClick={(event) => void submit(event, "signup")}
                >
                  Create account
                </button>
              </div>
            </form>
          )}
          {signedIn && (
            <>
              <div className="notice">
                Current plan: <strong>{plan === "pro" ? "Pro" : "Free"}</strong>. Billing uses
                Stripe-hosted pages; RepoLive never receives card details.
                {billingAvailable ? (
                  <div className="buttonRow">
                    {plan === "free" ? (
                    <button
                      type="button"
                      className="secondaryButton"
                      onClick={() => void openBilling("checkout")}
                    >
                      Upgrade to Pro
                    </button>
                    ) : (
                    <button
                      type="button"
                      className="secondaryButton"
                      onClick={() => void openBilling("portal")}
                    >
                      Manage billing
                    </button>
                    )}
                  </div>
                ) : (
                  <p>Plan upgrades are not available in this environment.</p>
                )}
              </div>
              <button
                type="button"
                className="secondaryButton"
                onClick={() => void supabase?.auth.signOut()}
              >
                Sign out
              </button>
              <h2>Saved analyses</h2>
              <p className="muted">Reopen a report or remove it from your private history.</p>
              {history.length === 0 ? (
                <div className="emptyState">No saved analyses yet.</div>
              ) : (
                <ul className="historyList">
                  {history.map((item) => (
                    <li className="historyItem" key={item.public_id}>
                      <div>
                        <Link href={`/analysis/${item.public_id}`}>
                          {item.owner} / {item.repository_name}
                        </Link>
                        <small>
                          Commit {item.commit_sha.slice(0, 8)} · Saved{" "}
                          {new Date(item.saved_at).toLocaleDateString()}
                        </small>
                        <small>
                          {item.scores
                            .map((score) => `${score.name}: ${score.value}`)
                            .join(" · ")}
                        </small>
                      </div>
                      <button
                        type="button"
                        className="dangerButton"
                        onClick={() => void remove(item.public_id)}
                        aria-label={`Remove ${item.owner}/${item.repository_name} from history`}
                      >
                        Remove
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </>
          )}
        </section>
      </main>
    </div>
  );
}
