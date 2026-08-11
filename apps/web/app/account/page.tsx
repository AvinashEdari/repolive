"use client";
import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { getAccessToken, getSupabaseClient } from "../../lib/supabase";
type HistoryItem = { public_id:string; owner:string; repository_name:string; commit_sha:string; saved_at:string; scores:{name:string;value:number}[] };
const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
export default function AccountPage() {
  const supabase = getSupabaseClient(); const [email,setEmail]=useState(""); const [password,setPassword]=useState("");
  const [message,setMessage]=useState(supabase?"Sign in to save and revisit analyses.":"Accounts are not configured in this environment.");
  const [history,setHistory]=useState<HistoryItem[]>([]); const [signedIn,setSignedIn]=useState(false);
  async function loadHistory(){const token=await getAccessToken();setSignedIn(Boolean(token));if(!token){setHistory([]);return;}const response=await fetch(`${apiUrl}/api/v1/analyses/me/history`,{headers:{Authorization:`Bearer ${token}`}});if(response.ok)setHistory(await response.json() as HistoryItem[]);}
  useEffect(()=>{if(!supabase)return;const {data}=supabase.auth.onAuthStateChange(()=>{void loadHistory();});return()=>data.subscription.unsubscribe();},[supabase]);
  async function submit(event:FormEvent,mode:"signin"|"signup"){event.preventDefault();if(!supabase)return;const result=mode==="signin"?await supabase.auth.signInWithPassword({email,password}):await supabase.auth.signUp({email,password});setMessage(result.error?.message??(mode==="signin"?"Signed in.":"Account created. Check your email if confirmation is enabled."));}
  async function remove(publicId:string){const token=await getAccessToken();if(!token)return;const response=await fetch(`${apiUrl}/api/v1/analyses/me/history/${publicId}`,{method:"DELETE",headers:{Authorization:`Bearer ${token}`}});if(response.ok)await loadHistory();}
  return <main><header><Link href="/">RepoLive.</Link> <Link href="/analyze">Analyze</Link></header><section><h1>Your account</h1><p role="status">{message}</p>
    {!signedIn&&<form><label>Email<input type="email" required value={email} onChange={e=>setEmail(e.target.value)}/></label><label>Password<input type="password" required minLength={8} value={password} onChange={e=>setPassword(e.target.value)}/></label><button onClick={e=>void submit(e,"signin")}>Sign in</button><button onClick={e=>void submit(e,"signup")}>Create account</button></form>}
    {signedIn&&<><button onClick={()=>void supabase?.auth.signOut()}>Sign out</button><h2>Saved analyses</h2>{history.length===0?<p>No saved analyses yet.</p>:<ul>{history.map(item=><li key={item.public_id}><Link href={`/analysis/${item.public_id}`}>{item.owner} / {item.repository_name}</Link> <small>{item.commit_sha.slice(0,8)} · {new Date(item.saved_at).toLocaleDateString()}</small> {item.scores.map(score=>`${score.name}: ${score.value}`).join(" · ")} <button onClick={()=>void remove(item.public_id)}>Remove</button></li>)}</ul>}</>}
  </section></main>;
}
