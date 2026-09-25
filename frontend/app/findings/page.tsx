"use client";
import {useState,useEffect} from "react";
const API=process.env.NEXT_PUBLIC_API_URL||"http://localhost:8000";

type FindingEvidence={id:string;claim_id?:string;source_url:string;excerpt:string;relation:string;public:boolean;review_status:string;created_at:string};
type PublicFinding={
  id:string;investigation_id:string;label:string;status:string;created_at:string;
  summary?:string;
  evidence_count:number;
  evidence:FindingEvidence[];
};
type PublicFindingsEnvelope={items:PublicFinding[];total:number;limit:number;offset:number};

export default function PublicFindingsPage(){
  const [q,setQ]=useState("");
  const [status,setStatus]=useState<string>("");
  const [page,setPage]=useState(0);
  const [limit]=useState(10);
  const [data,setData]=useState<PublicFindingsEnvelope>();
  const [error,setError]=useState("");
  const [loading,setLoading]=useState(false);

  useEffect(()=>{
    setLoading(true);setError("");
    const offset=page*limit;
    const params=new URLSearchParams({limit:String(limit),offset:String(offset)});
    if(q.trim())params.set("q",q.trim());
    if(status)params.set("status",status);
    fetch(`${API}/public/findings?${params.toString()}`)
      .then(async r=>{if(!r.ok){const b=await r.json().catch(()=>({detail:r.statusText}));throw new Error(b.detail||`HTTP ${r.status}`)}return r.json()})
      .then((d:PublicFindingsEnvelope)=>setData(d))
      .catch(e=>setError(e.message||"Published findings are temporarily unavailable."))
      .finally(()=>setLoading(false));
  },[q,status,page,limit]);

  const totalPages=data?Math.max(1,Math.ceil(data.total/limit)):1;
  const canPrev=page>0;
  const canNext=data?(page+1)*limit<data.total:false;

  return <main>
    <header>
      <b>AIPEIISR</b><span>Human-reviewed, published findings</span>
    </header>
    <section>
      <p className="eyebrow">PUBLISHED FINDINGS</p>
      <h1>Browse authorized findings.</h1>
      <p>All findings below were reviewed, approved and published by human publishers. Unpublished investigations are not visible on this public page.</p>
      <div className="filters">
        <input type="search" value={q} onChange={e=>{setQ(e.target.value);setPage(0)}} placeholder="Search finding labels…"/>
        <div className="sortbar">
          <button className={status===""?"chip chip-on":"chip"} onClick={()=>{setStatus("");setPage(0)}}>All</button>
          <button className={status==="PUBLISHED"?"chip chip-on":"chip"} onClick={()=>{setStatus("PUBLISHED");setPage(0)}}>Published</button>
        </div>
      </div>
      {error&&<p role="alert">{error}</p>}
      {loading&&<p>Loading findings…</p>}
      {!loading&&data&&<>
        <div className="filters" style={{justifyContent:"space-between"}}>
          <p className="muted small">{data.total} published {data.total===1?"finding":"findings"}. Showing {data.items.length} of page {page+1}/{totalPages}.</p>
          <div className="sortbar">
            <button className="chip" disabled={!canPrev} onClick={()=>setPage(p=>Math.max(0,p-1))}>← Prev</button>
            <span className="muted small">Page {page+1}/{totalPages}</span>
            <button className="chip" disabled={!canNext} onClick={()=>setPage(p=>p+1)}>Next →</button>
          </div>
        </div>
        {data.items.length===0&&<p className="muted">No published findings match this search yet.</p>}
        <ul className="evidence-list">
          {data.items.map(f=>(<li key={f.id} className="evidence-card">
            <div className="evidence-meta">
              <span className={`status-pill status-${f.status==="PUBLISHED"?"APPROVED":"DRAFT"}`}>{f.status.replaceAll("_"," ")}</span>
              <span className="count-badge">{f.evidence_count} evidence</span>
              <span className="provider-chip provider-search">Finding ID: {f.id}</span>
            </div>
            <h2 style={{margin:"12px 0 0",fontSize:22}}>
              <a href={`/findings/${f.id}`} style={{color:"#102c43",textDecoration:"none"}}>
                {f.label}
              </a>
            </h2>
            {f.summary&&<p className="excerpt">{f.summary}</p>}
            <div className="findings-row">
              <span className="muted small">Released: {new Date(f.created_at).toLocaleDateString()}</span>
              <a href={`/findings/${f.id}`} className="finding-chip">View full finding →</a>
            </div>
            {f.evidence&&f.evidence.length>0&&<>
              <h3 style={{margin:"16px 0 0",fontSize:14,color:"#526c7c"}}>Supporting evidence ({f.evidence.length}/{f.evidence_count})</h3>
              <ul className="evidence-list" style={{marginTop:10,gap:8}}>
                {f.evidence.map(e=>(<li key={e.id} className="evidence-card" style={{padding:12}}>
                  <div className="evidence-meta">
                    <span className="badge">{e.review_status.replaceAll("_"," ")}</span>
                    {e.source_url&&<a href={e.source_url} target="_blank" rel="noreferrer" className="source-link">Source</a>}
                  </div>
                  <p className="excerpt" style={{marginTop:8,fontSize:14}}>{e.excerpt}</p>
                </li>))}
              </ul>
            </>}
          </li>))}
        </ul>
        {data.total>limit&&<div className="filters" style={{justifyContent:"flex-end"}}>
          <button className="chip" disabled={!canPrev} onClick={()=>setPage(p=>Math.max(0,p-1))}>← Previous page</button>
          <span className="muted small">{offsetHelper(data)}</span>
          <button className="chip" disabled={!canNext} onClick={()=>setPage(p=>p+1)}>Next page →</button>
        </div>}
      </>}
    </section>
  </main>;
}
function offsetHelper(d:PublicFindingsEnvelope){
  return `${d.offset+1}–${d.offset+d.items.length} of ${d.total}`;
}
