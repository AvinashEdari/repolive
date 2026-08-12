import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Account",
  description: "Manage authentication and private RepoLive analysis history.",
  robots: { index: false, follow: false },
};

export default function AccountLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return children;
}
