"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useProtectedApi } from "../../../use-protected-api";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
type FindingDetail = {
  finding: { id: string; label: string; status: string };
  investigation?: { id: string; status: string };
  evidence: Array<{ id: string; source_url: string; excerpt: string; public: boolean; review_status: string }>;
  versions: Array<{ version: number; status: string; label: string; note?: string }>;
};

export default function AnalystFinding({ params }: { params: Promise<{ id: string }> }) {
  const { apiFetch, isAuthenticated, isLoading } = useProtectedApi();
  const [id, setId] = useState("");
  const [data, setData] = useState<FindingDetail>();
  const [error, setError] = useState("");
  useEffect(() => { params.then(({ id }) => setId(decodeURIComponent(id))); }, [params]);
  useEffect(() => {
    if (!id) return;
    if (isLoading) return;
    if (!isAuthenticated) { setError("Sign in with an analyst, reviewer, publisher, or admin account to view internal finding details."); return; }
    let cancelled = false;
    apiFetch(`${API}/findings/${encodeURIComponent(id)}`)
      .then(async response => { if (!response.ok) throw Error(String(response.status)); return response.json(); })
      .then(value => { if (!cancelled) setData(value); })
      .catch(value => { if (!cancelled) setError(value.message); });
    return () => { cancelled = true; };
  }, [id, isLoading, isAuthenticated, apiFetch]);
  return <main><header><b>AIPEIISR Analyst Finding</b><span>Internal review workspace</span></header><section>
    <p className="eyebrow">ANALYST ACCESS</p>
    <p className="muted small">This workspace uses your verified Auth0 access token. ANALYST, REVIEWER, PUBLISHER, or ADMIN role is required. API permissions are enforced server-side.</p>
    <Link className="finding-chip" href="/room">← Situation Room</Link>
    {!data && !error && <p>Loading finding…</p>}
    {error && <article role="alert"><h1>Finding unavailable</h1><p>Reference: finding-{error}. Check analyst access or return to Situation Room.</p></article>}
    {data && <><p className={`status-pill status-${data.finding.status}`}>{data.finding.status.replaceAll("_", " ")}</p><h1>{data.finding.label}</h1><p className="muted">Finding ID: {data.finding.id}</p>
      <article><h2>Investigation</h2><p>{data.investigation ? `Case ${data.investigation.id} — ${data.investigation.status}` : "No linked investigation found."}</p></article>
      <article><h2>Evidence</h2>{data.evidence.length ? data.evidence.map(e => <div className="evidence-card" key={e.id}><b>{e.review_status}</b><p>{e.excerpt}</p><a className="source-link" href={e.source_url} target="_blank">Source reference</a><small>{e.public ? "Public evidence" : "Internal evidence"}</small></div>) : <p>No linked evidence.</p>}</article>
      <article><h2>Publication history</h2><ul className="version-list">{data.versions.map(v => <li className="version-item" key={v.version}><b>v{v.version} — {v.status}</b><br />{v.label}{v.note ? ` — ${v.note}` : ""}</li>)}</ul></article>
    </>}
  </section></main>;
}
