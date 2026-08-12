import type { Metadata } from "next";
import { siteDescription, siteName, siteUrl } from "../lib/site";
import "./styles.css";

export const metadata: Metadata = {
  metadataBase: siteUrl,
  title: { default: `${siteName} — Understand public repositories`, template: `%s | ${siteName}` },
  description: siteDescription,
  alternates: { canonical: "/" },
  robots: { index: true, follow: true },
  openGraph: {
    type: "website",
    url: "/",
    siteName,
    title: `${siteName} — Understand public repositories`,
    description: siteDescription,
    images: [{ url: "/opengraph-image", width: 1200, height: 630, alt: "RepoLive" }],
  },
  twitter: {
    card: "summary_large_image",
    title: `${siteName} — Understand public repositories`,
    description: siteDescription,
    images: ["/opengraph-image"],
  },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
