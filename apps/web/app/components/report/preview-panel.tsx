"use client";

import { useCallback, useEffect, useState } from "react";
import { getAccessToken } from "../../../lib/supabase";

type Policy = { decision: string; detected_profile?: string; reasons: string[]; warnings: string[] };
type Preview = { preview_id: string; status: string; preview_url?: string; expires_at?: string; safe_failure_message?: string; retryable: boolean };
type Event = { event_id: string; safe_message: string; created_at: string };
const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export function PreviewPanel({ publicId }: { publicId: string }) {
  const [available, setAvailable] = useState(false); const [policy, setPolicy] = useState<Policy | null>(null);
  const [preview, setPreview] = useState<Preview | null>(null); const [events, setEvents] = useState<Event[]>([]); const [message, setMessage] = useState("");
  useEffect(() => { void Promise.all([fetch(`${apiUrl}/api/v1/preview-capabilities`).then(async r => { if (r.ok) setAvailable(Boolean(((await r.json()) as {available:boolean}).available)); }), fetch(`${apiUrl}/api/v1/analyses/${encodeURIComponent(publicId)}/preview-policy`).then(async r => { if (r.ok) setPolicy((await r.json()) as Policy); })]); }, [publicId]);
  const refresh = useCallback(async (id: string) => { const token = await getAccessToken(); if (!token) return; const headers = { Authorization: `Bearer ${token}` }; const [statusResponse, eventsResponse] = await Promise.all([fetch(`${apiUrl}/api/v1/previews/${id}`, { headers }), fetch(`${apiUrl}/api/v1/previews/${id}/events`, { headers })]); if (statusResponse.ok) setPreview((await statusResponse.json()) as Preview); if (eventsResponse.ok) setEvents((await eventsResponse.json()) as Event[]); }, []);
  useEffect(() => { if (!preview || ["destroyed","rejected","failed","timed_out","expired","canceled"].includes(preview.status)) return; const timer = window.setInterval(() => void refresh(preview.preview_id), 2000); return () => window.clearInterval(timer); }, [preview, refresh]);
  async function action(kind: "create" | "stop" | "retry") { const token = await getAccessToken(); if (!token) { setMessage("Sign in from Account before requesting a preview."); return; } const path = kind === "create" ? `/analyses/${encodeURIComponent(publicId)}/previews` : `/previews/${preview?.preview_id}/${kind}`; const response = await fetch(`${apiUrl}/api/v1${path}`, { method: "POST", headers: { Authorization: `Bearer ${token}` } }); if (response.ok && response.headers.get("content-type")?.includes("json")) { const value = (await response.json()) as Preview; setPreview(value); void refresh(value.preview_id); } else if (response.ok && preview) void refresh(preview.preview_id); else { const error = (await response.json()) as {detail?:string}; setMessage(error.detail ?? "Preview request failed safely."); } }
  const eligible = policy?.decision === "eligible";
  return <section className="panel" aria-labelledby="preview-title"><p className="eyebrow">Disposable preview</p><h2 id="preview-title">Run this static site temporarily</h2><p className="muted">Untrusted repository content runs in a disposable sandbox. Previews are temporary, are not production deployments, and may fail when services or secrets are required. Only run repositories you have permission to use.</p>
    {!available && <div className="notice">Preview execution is disabled in this environment.</div>}
    {policy && !eligible && <div className="notice warning"><strong>Unsupported repository</strong><p>{policy.reasons.join(" ")}</p></div>}
    {available && eligible && !preview && <button className="primaryButton" type="button" onClick={() => void action("create")}>Run live preview</button>}
    {message && <p className="notice" role="status">{message}</p>}
    {preview && <div className="stack"><p>Status: <strong>{preview.status}</strong>{preview.expires_at ? ` · expires ${new Date(preview.expires_at).toLocaleString()}` : ""}</p><div className="buttonRow">{preview.preview_url && <><a className="primaryButton" href={preview.preview_url} target="_blank" rel="noreferrer">Open preview</a><button className="secondaryButton" type="button" onClick={() => void navigator.clipboard.writeText(preview.preview_url!)}>Copy URL</button></>}{!["destroyed","expired","canceled"].includes(preview.status) && <button className="dangerButton" type="button" onClick={() => void action("stop")}>Stop preview</button>}{preview.retryable && <button className="secondaryButton" type="button" onClick={() => void action("retry")}>Retry</button>}</div>{preview.safe_failure_message && <p className="notice warning">{preview.safe_failure_message}</p>}<details><summary>Sanitized status log</summary><ol>{events.map(event => <li key={event.event_id}>{event.safe_message}</li>)}</ol></details></div>}
  </section>;
}
