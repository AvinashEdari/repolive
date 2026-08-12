import Link from "next/link";

export function SiteHeader({ context }: { context?: string }) {
  return <><a className="skipLink" href="#main-content">Skip to main content</a><header className="siteHeader"><Link className="brand" href="/" aria-label="RepoLive home">RepoLive<span>.</span></Link>{context&&<span className="headerContext">{context}</span>}<nav aria-label="Primary navigation"><Link href="/analyze">Analyze</Link><Link href="/account">Account</Link><Link href="/legal/privacy">Privacy</Link></nav></header></>;
}
