"use client";
import {useEffect,useState} from "react";
import {useProtectedApi} from "../../use-protected-api";
const API=process.env.NEXT_PUBLIC_API_URL||"http://localhost:8000";
type SourceRow={id:string;name:string;url:string;collector_type:string;interval_minutes:number;status:"DRAFT"|"APPROVED"|"DISABLED"|"RETIRED";last_success?:string;created_at:string};
const STATUSES:SourceRow["status"][]=["APPROVED","DRAFT","DISABLED","RETIRED"];
export default function AdminSourcesPage(){
  const {apiFetch,isAuthenticated,isLoading}=useProtectedApi();
  const [sources,setSources]=useState<SourceRow[]>([]);
  const [allSources,setAllSources]=useState<SourceRow[]>([]);
  const [error,setError]=useState("");
  const [busy,setBusy]=useState<string|null>(null);
  const [filter,setFilter]=useState<string>("ALL");
  const [newName,setNewName]=useState("");
  const [newUrl,setNewUrl]=useState("");
  const [createErr,setCreateErr]=useState("");
  const load=()=>{
    if(isLoading)return;
    if(!isAuthenticated){setError("Sign in with an admin account to manage sources.");return}
    setError("");
    apiFetch(`${API}/sources`,{headers:{"content-type":"application/json"}})
      .then(async r=>{if(!r.ok){const b=await r.json().catch(()=>({detail:r.statusText}));throw new Error(b.detail||`HTTP ${r.status}`)}return r.json()})
      .then((rows:SourceRow[])=>{setAllSources(rows);setSources(filter==="ALL"?rows:rows.filter(s=>s.status===filter))})
      .catch(e=>setError(e.message||"Could not load sources. ADMIN role required."));
  };
  useEffect(()=>{load()},[isLoading,isAuthenticated]);
  useEffect(()=>{setSources(filter==="ALL"?allSources:allSources.filter(s=>s.status===filter))},[filter,allSources]);
  async function createSource(){
    setCreateErr("");
    if(!isAuthenticated){setCreateErr("Sign in with an admin account to create sources.");return}
    if(!newName.trim()||!newUrl.trim()){setCreateErr("Name and URL are required.");return}
    const res=await apiFetch(`${API}/sources`,{method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify({name:newName.trim(),url:newUrl.trim(),collector_type:"RSS",interval_minutes:60})});
    if(!res.ok){const b=await res.json().catch(()=>({detail:res.statusText}));setCreateErr(b.detail||"Could not create source.");return}
    setNewName("");setNewUrl("");load();
  }
  async function setStatus(sid:string,next:SourceRow["status"]){
    if(!isAuthenticated){setError("Sign in with an admin account to update sources.");return}
    setBusy(sid);setError("");
    const res=await apiFetch(`${API}/sources/${sid}/status`,{method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify({status:next})});
    if(!res.ok){const b=await res.json().catch(()=>({detail:res.statusText}));setError(b.detail||"Could not update source status.");setBusy(null);return}
    setBusy(null);load();
  }
  async function runOnce(sid:string){
    if(!isAuthenticated){setError("Sign in with an admin or analyst account to run sources.");return}
    setBusy(sid);setError("");
    const res=await apiFetch(`${API}/sources/${sid}/run-once`,{method:"POST",headers:{"content-type":"application/json"}});
    if(!res.ok){const b=await res.json().catch(()=>({detail:res.statusText}));setError(b.detail||"Could not trigger source run-once. Ensure source is APPROVED first.");setBusy(null);return}
    setBusy(null);
  }
  return <main>
    <header><b>AIPEIISR Admin</b><span>Source governance and ingestion controls</span></header>
    <section>
      <p className="eyebrow">SOURCE GOVERNANCE</p>
      <h1>Manage ingestion sources.</h1>
      <p className="muted small">This workspace uses your verified Auth0 access token. ADMIN role is required for source creation and status changes. API permissions are enforced server-side.</p>
      <p>New sources default to <b>DRAFT</b> and do not ingest until an ADMIN advances them to <b>APPROVED</b>. <b>DISABLED</b> and <b>DRAFT</b> sources gate ingestion with 409 at the API and scheduler layer.</p>
      <article>
        <h2>Register a new source</h2>
        <div className="filters">
          <input type="text" value={newName} onChange={e=>setNewName(e.target.value)} placeholder="Source name"/>
          <input type="url" value={newUrl} onChange={e=>setNewUrl(e.target.value)} placeholder="https://… RSS or collection URL"/>
          <button onClick={createSource}>Create source (DRAFT)</button>
        </div>
        {createErr&&<p role="alert">{createErr}</p>}
      </article>
      <div className="filters">
        <div className="sortbar">
          <button className={filter==="ALL"?"chip chip-on":"chip"} onClick={()=>setFilter("ALL")}>All ({allSources.length})</button>
          {STATUSES.map(s=>(<button key={s} className={filter===s?"chip chip-on":"chip"} onClick={()=>setFilter(s)}>{s.toLowerCase().replace(/^\w/,c=>c.toUpperCase())} ({allSources.filter(x=>x.status===s).length})</button>))}
        </div>
        <button onClick={load}>Refresh</button>
      </div>
      {error&&<p role="alert">{error}</p>}
      {sources.length===0&&!error&&<p className="muted">No sources match this filter yet.</p>}
      {sources.length>0&&<table className="sources-table">
        <thead><tr><th>Source</th><th>Status</th><th>Cadence</th><th>Last ingest</th><th>Governance actions</th></tr></thead>
        <tbody>
          {sources.map(s=>(<tr key={s.id}>
            <td>
              <div><b>{s.name}</b></div>
              <div className="muted small">{s.id}</div>
              <div className="muted small"><a href={s.url} target="_blank" rel="noreferrer">{s.url}</a> · {s.collector_type}</div>
            </td>
            <td><span className={`status-pill status-${s.status}`}>{s.status.replaceAll("_"," ")}</span></td>
            <td className="muted small">every {s.interval_minutes} min</td>
            <td className="muted small">{s.last_success?new Date(s.last_success).toLocaleString():"—"}</td>
            <td>
              <div className="sortbar">
                {s.status!=="APPROVED"&&<button className="chip" disabled={busy===s.id} onClick={()=>setStatus(s.id,"APPROVED")}>Approve</button>}
                {s.status!=="DISABLED"&&s.status!=="RETIRED"&&<button className="chip" disabled={busy===s.id} onClick={()=>setStatus(s.id,"DISABLED")}>Disable</button>}
                {s.status!=="DRAFT"&&<button className="chip" disabled={busy===s.id} onClick={()=>setStatus(s.id,"DRAFT")}>Reset to draft</button>}
                <button className="chip" disabled={busy===s.id||s.status!=="APPROVED"} onClick={()=>runOnce(s.id)}>Run once</button>
              </div>
              <div className="muted small" style={{marginTop:6}}>Created {new Date(s.created_at).toLocaleDateString()}</div>
            </td>
          </tr>))}
        </tbody>
      </table>}
    </section>
  </main>;
}
