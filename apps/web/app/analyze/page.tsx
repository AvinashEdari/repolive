"use client";
import { FormEvent, useState } from "react";
import Link from "next/link";
import styles from "./results.module.css";

type Insight = { label: string; evidence: string[] };
export type Report = { public_id: string | null; snapshot: { repository: { owner: string; name: string; canonical_url: string }; metadata: { description: string | null; stars: number; forks: number; open_issues: number }; files: { path: string }[] }; analysis: { purpose_summary: string; project_types: string[]; languages: { name: string; share_percent: number; evidence: string[] }[]; technologies: { name: string; evidence: string[] }[]; dependencies: { name: string; version_constraint: string | null; ecosystem: string; source_path: string }[]; runtimes: { runtime: string; version_constraint: string | null; evidence: string[] }[]; important_files: { path: string; role: string }[]; scores: { name: string; value: number; factors: { label: string; evidence: string[] }[] }[]; setup_steps: { title: string; command: string | null; origin: string; source_path: string }[]; prerequisites: { name: string; version_constraint: string | null; evidence: string[] }[]; compatibility: { subject: string; status: string; detail: string; evidence: string[] }[]; strengths: Insight[]; risks: Insight[]; missing_essentials: Insight[]; unknowns: Insight[] } };

export default function AnalyzePage() {
  const [url, setUrl] = useState(""); const [report, setReport] = useState<Report | null>(null);
  const [message, setMessage] = useState("Public repositories only. Code is never executed."); const [loading, setLoading] = useState(false);
  async function analyze(event: FormEvent) {
    event.preventDefault(); setLoading(true); setMessage("Retrieving bounded evidence and running deterministic analyzers…");
    try {
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/api/v1/analyses`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ repository_url: url }) });
      const payload = (await response.json()) as Report & { detail?: string };
      if (!response.ok) throw new Error(payload.detail ?? "Analysis failed.");
      setReport(payload); setMessage(`${payload.snapshot.files.length} files analyzed.`);
    } catch (error) { setReport(null); setMessage(error instanceof Error ? error.message : "The API is unavailable."); }
    finally { setLoading(false); }
  }
  return <main className={styles.shell}><header><Link href="/">RepoLive.</Link><span>Analysis workspace</span></header>
    <section className={styles.search}><p>DETERMINISTIC REPOSITORY INTELLIGENCE</p><h1>Analyze a public GitHub repository.</h1><form onSubmit={analyze}><input type="url" required value={url} onChange={(event) => setUrl(event.target.value)} placeholder="https://github.com/owner/repository"/><button disabled={loading}>{loading ? "Analyzing…" : "Analyze"}</button></form><small>{message}</small></section>
    {report && <Results report={report}/>}</main>;
}

export function Results({ report }: { report: Report }) {
  const { snapshot, analysis } = report;
  return <section className={styles.results}><div className={styles.title}><div><p>ANALYSIS COMPLETE</p><h2>{snapshot.repository.owner} / {snapshot.repository.name}</h2><span>{analysis.purpose_summary}</span></div><div>{report.public_id&&<a href={`/analysis/${report.public_id}`}>Share analysis</a>} <a href={snapshot.repository.canonical_url} target="_blank" rel="noreferrer">View on GitHub ↗</a></div></div>
    <div className={styles.metrics}>{[["Files",snapshot.files.length],["Stars",snapshot.metadata.stars],["Forks",snapshot.metadata.forks],["Issues",snapshot.metadata.open_issues]].map(([label,value])=><div key={label}><b>{Number(value).toLocaleString()}</b><span>{label}</span></div>)}</div>
    <div className={styles.grid}>{analysis.scores.map((score)=><article key={score.name}><h3>{score.name}<b>{score.value}</b></h3><progress max="100" value={score.value}/><ul>{score.factors.map((factor)=><li key={factor.label}>{factor.label}</li>)}</ul></article>)}</div>
    <div className={styles.grid}><Card title="Project profile"><Tags values={analysis.project_types}/></Card><Card title="Languages">{analysis.languages.map((item)=><div className={styles.language} key={item.name} title={item.evidence.join(", ")}><span>{item.name}</span><b>{item.share_percent}%</b><i style={{width:`${item.share_percent}%`}}/></div>)}</Card><Card title="Frameworks & tooling"><EvidenceList values={analysis.technologies.map((item)=>({label:item.name,evidence:item.evidence}))}/></Card><Card title="Runtimes">{analysis.runtimes.length?<EvidenceList values={analysis.runtimes.map((item)=>({label:`${item.runtime} ${item.version_constraint??"version unspecified"}`,evidence:item.evidence}))}/>:<p>No explicit runtime constraint detected.</p>}</Card></div>
    <div className={styles.grid}><Card title="Strengths"><EvidenceList values={analysis.strengths}/></Card><Card title="Risks & missing essentials"><EvidenceList values={[...analysis.risks,...analysis.missing_essentials]}/></Card><Card title="Compatibility"><EvidenceList values={analysis.compatibility.map((item)=>({label:`${item.subject}: ${item.detail}`,evidence:item.evidence}))}/></Card><Card title="Unknowns"><EvidenceList values={analysis.unknowns}/></Card></div>
    <Card title={`Setup guidance (${analysis.setup_steps.length})`} wide><div className={styles.files}>{analysis.setup_steps.map((item)=><div key={`${item.title}-${item.source_path}`}><span><b>{item.title}</b><br/><small>{item.origin} · {item.source_path}</small></span>{item.command?<code>{item.command}</code>:<span>No command declared</span>}</div>)}</div></Card>
    <Card title={`Dependencies (${analysis.dependencies.length})`} wide><div className={styles.items}>{analysis.dependencies.slice(0,100).map((item)=><div key={`${item.ecosystem}-${item.name}`} title={item.source_path}><b>{item.name}</b><span>{item.version_constraint??"unspecified"}</span><small>{item.ecosystem} · {item.source_path}</small></div>)}</div></Card>
    <Card title={`Important files (${analysis.important_files.length})`} wide><div className={styles.files}>{analysis.important_files.map((item)=><div key={item.path}><code>{item.path}</code><span>{item.role}</span></div>)}</div></Card></section>;
}
function Card({title,children,wide=false}:{title:string;children:React.ReactNode;wide?:boolean}){return <article className={wide?styles.wide:""}><h3>{title}</h3>{children}</article>}
function Tags({values}:{values:string[]}){return <div className={styles.tags}>{values.map((value)=><span key={value}>{value}</span>)}</div>}
function EvidenceList({values}:{values:{label:string;evidence:string[]}[]}){return values.length?<ul>{values.map((item)=><li key={`${item.label}-${item.evidence.join()}`}><span>{item.label}</span>{item.evidence.length>0&&<small>Evidence: {item.evidence.join(", ")}</small>}</li>)}</ul>:<p>No evidence detected.</p>}
