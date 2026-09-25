"use client";
import {useEffect,useState} from "react";
const API=process.env.NEXT_PUBLIC_API_URL||"http://localhost:8000";
type EvidenceItem={id:string;claim_id?:string;source_url:string;excerpt:string;relation:string;public:boolean;review_status:string;created_at:string};
type InvestigationStub={id:string;submission_id?:string;status:string;created_at:string};
type FindingVersion={id:string;finding_id:string;version:number;label:string;status:string;actor:string;note?:string;created_at:string};
type FindingDetail={
  finding:{id:string;investigation_id:string;label:string;status:string;created_at:string};
  investigation:InvestigationStub|null;
  evidence:EvidenceItem[];
  versions:FindingVersion[];
};
export default function FindingDetailPage({params}:{params:{id:string}}){
  const fid=decodeURIComponent(params.id);
  const [data,setData]=useState<FindingDetail>();
  const [error,setError]=useState("");
  const [statusCode,setStatusCode]=useState<number|null>(null);

  useEffect(()=>{
    let cancelled=false;
    async function load(){
      try{
        const r=await fetch(`${API}/public/findings/${fid}`);
        if(!r.ok){
          setStatusCode(r.status);
          if(r.status===404){setError("This finding does not exist or is no longer available.");return}
          if(r.status===403||r.status===401){setError("This finding is not publicly available.");return}
          const b=await r.json().catch(()=>({detail:r.statusText}));
          throw new Error(b.detail||`HTTP ${r.status}`);
        }
        const json=await r.json();
        if(!cancelled){setData(json);setStatusCode(200)}
      }catch(e:any){setError(e.message||"Finding detail is temporarily unavailable.")}
    }
    load();
    return ()=>{cancelled=true};
  },[fid]);

  const isUnpublished=!!error&&(statusCode===403||statusCode===401);
  const is404=!!error&&statusCode===404;

  return <main>
    <header><b>AIPEIISR</b><span>Finding detail — human-reviewed publication record</span></header>
    <section>
      <p className="eyebrow">PUBLISHED FINDING</p>
      <div className="filters" style={{marginBottom:14}}>
        <a href="/findings" className="chip">← Back to all findings</a>
      </div>
      {isUnpublished&&<article>
        <h2 style={{marginTop:0}}>This finding is not publicly available.</h2>
        <p>The investigation record you are trying to access is under active review or has not yet been authorized for publication by a human publisher.</p>
        <ul style={{marginLeft:16,color:"#526c7c"}}>
          <li>Only <b>PUBLISHED</b> findings are visible on the public site.</li>
          <li>Unpublished investigations require ANALYST credentials to view.</li>
          <li>If this is a known incident, you can check the <a href="/findings">full published findings list</a>.</li>
        </ul>
        <p style={{marginTop:10,color:"#102c43"}}>If you believe this finding should be public, or if you are an analyst with credentials, sign in to the Situation Room for access.</p>
      </article>}
      {is404&&<article>
        <h2 style={{marginTop:0}}>Finding not found.</h2>
        <p>The finding you requested does not exist or was removed.</p>
        <a href="/findings" className="chip">Browse all published findings →</a>
      </article>}
      {error&&!isUnpublished&&!is404&&<p role="alert">{error}</p>}
      {!data&&!error&&<p>Loading finding record…</p>}
      {data&&<>
        <h1>{data.finding.label}</h1>
        <div className="filters">
          <span className={`status-pill status-${data.finding.status}`}>{data.finding.status.replaceAll("_"," ")}</span>
          <span className="muted small">Finding ID: {data.finding.id}</span>
          <span className="provider-chip provider-search">Human-reviewed and authorized for release</span>
        </div>
        <article>
          <h2>Background</h2>
          <p><b>Publication status:</b> <span className={`status-pill status-${data.finding.status}`}>{data.finding.status.replaceAll("_"," ")}</span></p>
          <p><b>Released:</b> {new Date(data.finding.created_at).toLocaleString()}</p>
          {data.investigation&&<>
            <p><b>Investigation ID:</b> {data.investigation.id}</p>
            <p><b>Investigation status:</b> {data.investigation.status.replaceAll("_"," ")}</p>
            {data.investigation.submission_id&&<p><b>Referenced citizen submission:</b> {data.investigation.submission_id}</p>}
          </>}
          <p className="muted small" style={{marginTop:10}}>
            This finding has been reviewed and authorized for release by human publishers.
            AI tools were used as an aid during the investigation; the final publication decision is a human-only action.
          </p>
        </article>
        <article>
          <h2>Linked evidence ({data.evidence.length})</h2>
          {data.evidence.length===0&&<p className="muted">No evidence is linked to this finding yet.</p>}
          <ul className="evidence-list">
            {data.evidence.map(e=>(<li key={e.id} className="evidence-card">
              <div className="evidence-meta">
                <span className="badge">{e.review_status.replaceAll("_"," ")}</span>
                {e.public&&<span className="status-pill status-APPROVED">PUBLIC</span>}
                {e.source_url&&<a href={e.source_url} target="_blank" rel="noreferrer" className="source-link">Source</a>}
              </div>
              <p className="excerpt">{e.excerpt}</p>
            </li>))}
          </ul>
        </article>
        <article>
          <h2>Publication history ({data.versions.length} version{data.versions.length===1?"":"s"})</h2>
          <ul className="version-list">
            {data.versions.map((v,i)=>(
              <li key={v.id} className={`version-item ${i===0?"v-head":""}`}>
                <div>
                  <span className="version-tag">v{v.version}</span>
                  <b>{v.label}</b>
                  <span className={`status-pill status-${v.status==="PUBLISHED"?"APPROVED":v.status==="UNPUBLISHED"?"DISABLED":"DRAFT"}`}>{v.status.replaceAll("_"," ")}</span>
                </div>
                <div className="version-meta">
                  {v.actor} · {new Date(v.created_at).toLocaleString()}
                  {v.note&&<div className="version-note">{v.note}</div>}
                </div>
              </li>
            ))}
          </ul>
        </article>
      </>}
    </section>
  </main>;
}
