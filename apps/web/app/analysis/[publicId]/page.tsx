import Link from "next/link";

import { Report } from "../../analyze/page";
import { SiteHeader } from "../../components/site-header";
import { ReportView } from "../../components/report/report-view";
import styles from "../../analyze/results.module.css";
import { MachineCheckPanel } from "../../components/report/machine-check-panel";
import { PreviewPanel } from "../../components/report/preview-panel";

export default async function PublicAnalysisPage({
  params,
}: {
  params: Promise<{ publicId: string }>;
}) {
  const { publicId } = await params;
  const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
  const response = await fetch(`${apiUrl}/api/v1/analyses/${encodeURIComponent(publicId)}`, {
    cache: "no-store",
  });
  if (!response.ok) {
    return <main className={styles.shell}><header><Link href="/">RepoLive.</Link></header>
      <section className={styles.search}><p>ANALYSIS UNAVAILABLE</p><h1>This analysis could not be found.</h1><Link href="/analyze">Analyze a repository</Link></section></main>;
  }
  const report = (await response.json()) as Report;
  return <div className={styles.shell}><SiteHeader context="Shared analysis"/><main id="main-content"><ReportView report={report}/><PreviewPanel publicId={publicId}/><MachineCheckPanel publicId={publicId}/></main></div>;
}
