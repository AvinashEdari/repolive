import type { ReactNode } from "react";
import { SiteHeader } from "./site-header";
import styles from "./legal-page.module.css";

export function LegalPage({ title, summary, children }: { title: string; summary: string; children: ReactNode }) {
  return <div className="pageShell"><SiteHeader context={title}/><main id="main-content" className={styles.legal}><p className="eyebrow">RepoLive policy</p><h1>{title}</h1><p className="lede">{summary}</p><aside className="notice warning"><strong>Draft notice</strong><p>This text describes current product behavior and requires final review by qualified legal counsel before a public production launch.</p></aside>{children}</main></div>;
}
