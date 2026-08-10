"use client";
import { FormEvent, useState } from "react";
type State = { kind: "idle" | "loading" | "success" | "error"; message?: string };
export default function Home() {
  const [repositoryUrl, setRepositoryUrl] = useState("");
  const [state, setState] = useState<State>({ kind: "idle" });
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setState({ kind: "loading" });
    try {
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/api/v1/analyses`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ repository_url: repositoryUrl }) });
      const result = (await response.json()) as { snapshot?: { files?: unknown[] }; detail?: string };
      if (!response.ok) throw new Error(result.detail ?? "This repository could not be validated.");
      setState({ kind: "success", message: `Repository analyzed: ${result.snapshot?.files?.length ?? 0} files discovered.` });
    } catch (error) { setState({ kind: "error", message: error instanceof Error ? error.message : "The API is unavailable." }); }
  }
  return <main><nav aria-label="Primary"><a className="brand" href="#">RepoLive<span>.</span></a><span className="badge">Foundation preview</span></nav><section className="hero"><p className="eyebrow">Repository intelligence, without the guesswork</p><h1>Know what a repository does <em>before</em> you clone it.</h1><p className="lede">Paste a public GitHub URL. RepoLive will turn its structure, dependencies, setup, and health signals into a clear, evidence-based report.</p><form onSubmit={submit}><label htmlFor="repository-url">GitHub repository URL</label><div className="input-row"><input id="repository-url" type="url" required value={repositoryUrl} onChange={(event) => setRepositoryUrl(event.target.value)} placeholder="https://github.com/owner/repository" autoComplete="url"/><button disabled={state.kind === "loading"}>{state.kind === "loading" ? "Checking…" : "Analyze repository"}</button></div><p className={`status ${state.kind}`} role="status">{state.message ?? "Public repositories only. No account required."}</p></form></section><section className="signals" aria-label="Analysis areas"><article><b>01</b><h2>Understand</h2><p>Purpose, architecture, important files, and technical concepts in plain language.</p></article><article><b>02</b><h2>Evaluate</h2><p>Explainable signals for documentation, testing, maintainability, and readiness.</p></article><article><b>03</b><h2>Get running</h2><p>Evidence-led requirements and setup guidance for your operating system.</p></article></section></main>;
}
