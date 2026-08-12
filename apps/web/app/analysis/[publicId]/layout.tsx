import type { Metadata } from "next";
import type { ReactNode } from "react";

export async function generateMetadata({ params }: { params: Promise<{ publicId: string }> }): Promise<Metadata> {
  const { publicId } = await params;
  const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
  const response = await fetch(`${apiUrl}/api/v1/analyses/${encodeURIComponent(publicId)}`, { cache: "no-store" });
  if (!response.ok) return { title: "Analysis unavailable", robots: { index: false, follow: false } };
  const report = (await response.json()) as { snapshot: { repository: { owner: string; name: string } } };
  const repository = `${report.snapshot.repository.owner}/${report.snapshot.repository.name}`;
  const description = `Evidence-based RepoLive analysis of ${repository}. Repository code was not executed.`;
  return { title: `${repository} analysis`, description, alternates: { canonical: `/analysis/${publicId}` }, robots: { index: true, follow: true }, openGraph: { type: "article", title: `${repository} analysis`, description, url: `/analysis/${publicId}` }, twitter: { card: "summary_large_image", title: `${repository} analysis`, description } };
}

export default function AnalysisLayout({ children }: { children: ReactNode }) {
  return children;
}
