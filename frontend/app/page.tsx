"use client";
import {useState,useEffect} from "react";
const API=process.env.NEXT_PUBLIC_API_URL||"http://localhost:8000";

type FindingStub={id:string;label:string;status:string;created_at:string};
type PublicEvidence={id:string;claim_id?:string;source_url:string;excerpt:string;relation:string;public:boolean;review_status:string;created_at:string;cited_by_count:number;findings:FindingStub[]};
type PublicEvidenceEnvelope={items:PublicEvidence[];total:number;limit:number;offset:number};
type SubmissionResult={
  id:string;text?:string;url?:string;media_reference?:string;consent:boolean;
  status:string;analysis:string;created_at:string;
  citations:string[];uncertainty:string;public_evidence:PublicEvidence[];
  llm_provider:string;
};

export default function Home(){
  const [text,setText]=useState("");
  const [result,setResult]=useState<SubmissionResult>();
  const [error,setError]=useState("");
  const [evidence,setEvidence]=useState<PublicEvidenceEnvelope>();
  const [evError,setEvError]=useState("");
  const [sort,setSort]=useState<"newest"|"oldest"|"cited">("cited");
  const [q,setQ]=useState("");

  async function check(){
    setError("");
    const r=await fetch(`${API}/citizen/submissions`,{
      method:"POST",
      headers:{"content-type":"application/json"},
      body:JSON.stringify({text,consent:true}),
    });
    if(!r.ok){setError("Unable to process this submission. Please try again.");return}
    setResult(await r.json());
  }

  useEffect(()=>{
    const params=new URLSearchParams({sort,limit:"10",offset:"0"});
    if(q.trim())params.set("q",q.trim());
    setEvError("");
    fetch(`${API}/public/evidence?${params.toString()}`)
      .then(r=>r.ok?r.json():Promise.reject())
      .then((d:PublicEvidenceEnvelope)=>setEvidence(d))
      .catch(()=>setEvError("Published evidence is temporarily unavailable."));
  },[sort,q]);

  function uncertaintyClass(u:string|undefined):string{
    if(!u)return"uncertainty-unknown";
    const l=u.toLowerCase();
    if(l==="high")return"uncertainty-high";
    if(l==="medium"||l==="med")return"uncertainty-medium";
    if(l==="low")return"uncertainty-low";
    return"uncertainty-unknown";
  }
  function isUrl(s:string):boolean{return/^https?:\/\//i.test(s)}
  function providerChipClass(provider:string|undefined):string{
    if(!provider)return"provider-mock";
    const n=provider.toLowerCase();
    if(n.includes("mock"))return"provider-mock";
    if(n.includes("ollama"))return"provider-llm";
    if(n.includes("hugging")||n.includes("hf"))return"provider-llm";
    if(n.includes("openrouter")||n.includes("gpt")||n.includes("gemini")||n.includes("claude"))return"provider-llm";
    return"provider-llm";
  }

  return <main>
    <header>
      <b>AIPEIISR</b><span>Human-led information monitoring and fact-checking</span>
    </header>
    <section>
      <p className="eyebrow">CITIZEN FACT CHECK</p>
      <h1>Investigate information with evidence.</h1>
      <p>Submit a claim or paste information. AI can organize available information; human reviewers authorize findings. You can also <a href="/findings" style={{color:"#173f5f",fontWeight:600}}>browse all published findings →</a></p>
      <textarea value={text} onChange={e=>setText(e.target.value)} placeholder="Paste a claim, message, or summary"/>
      <button onClick={check} disabled={!text}>Check information</button>
      {error&&<p role="alert">{error}</p>}
      {result&&<article>
        <div className="evidence-meta">
          <span className="badge">{result.status.replaceAll("_"," ")}</span>
          <span className={`provider-chip ${providerChipClass(result.llm_provider)}`} title={`Analysis performed by provider: ${result.llm_provider||"mock"}. Provider outputs are non-authoritative; human reviewers publish findings.`}>
            LLM · {result.llm_provider||"mock"}
          </span>
          {result.uncertainty&&<span className={`provider-chip ${uncertaintyClass(result.uncertainty)}`} title={`Provider-reported uncertainty level. Higher = more caution recommended; escalate to analysts if unsure.`}>
            Uncertainty · {result.uncertainty}
          </span>}
        </div>
        <h2>Submission received</h2>
        <p>{result.analysis}</p>
        <div className="enrichments-row">
          <span className="muted small">Human review:</span>
          <span className="badge">{result.status==="PUBLISHED_FINDING"?"Available for matched evidence":"Not yet completed"}</span>
          <span className="muted small">Evidence match:</span>
          <span className="count-badge">{result.public_evidence?.length||0} published</span>
        </div>
        {result.citations&&result.citations.length>0&&<div className="enrichments-row">
          <span className="muted small">Citations / sources ({result.citations.length}):</span>
          {result.citations.map((c,i)=>(
            isUrl(c)
              ?<a key={i} href={c} target="_blank" rel="noreferrer" className="citation-chip external" title="Provider or user-supplied source URL. Verify independently; citations are non-authoritative.">
                {c.length>60?c.slice(0,57)+"…":c}
              </a>
              :<span key={i} className="citation-chip" title="Non-URL citation from provider or submission context.">{c}</span>
          ))}
        </div>}
        {result.public_evidence&&result.public_evidence.length>0&&<>
          <h3 style={{marginTop:20}}>Relevant published evidence ({result.public_evidence.length})</h3>
          <ul className="evidence-list">
            {result.public_evidence.map(e=>(<li key={e.id} className="evidence-card">
              <div className="evidence-meta">
                <span className="badge">{e.review_status.replaceAll("_"," ")}</span>
                <span className="cited-badge" title="Times cited by other evidence">× {e.cited_by_count}</span>
                {e.source_url&&<a href={e.source_url} target="_blank" rel="noreferrer" className="source-link">Source</a>}
              </div>
              <p className="excerpt">{e.excerpt}</p>
              {e.findings&&e.findings.length>0&&<div className="findings-row">
                <span className="muted small">Findings:</span>
                {e.findings.map(f=>(
                  <a key={f.id} href={`/findings/${f.id}`} className="finding-chip">{f.label}</a>
                ))}
              </div>}
            </li>))}
          </ul>
        </>}
        <p className="muted small" style={{marginTop:14}}>
          ⚠ AI-assisted analysis only. Findings are published and authorized only by human reviewers.
          Escalate to analysts if you need investigation of a specific claim.
        </p>
      </article>}
    </section>
    <section>
      <p className="eyebrow">PUBLISHED EVIDENCE</p>
      <h1>Browse reviewed findings and sources.</h1>
      <p>All evidence below has been reviewed by human analysts and approved for public disclosure. Sorted by <b>{sort}</b>. You can also <a href="/findings" style={{color:"#173f5f",fontWeight:600}}>browse published findings by category →</a></p>
      <div className="filters">
        <input type="search" value={q} onChange={e=>setQ(e.target.value)} placeholder="Search evidence excerpts or sources…"/>
        <div className="sortbar">
          <button className={sort==="newest"?"chip chip-on":"chip"} onClick={()=>setSort("newest")}>Newest</button>
          <button className={sort==="oldest"?"chip chip-on":"chip"} onClick={()=>setSort("oldest")}>Oldest</button>
          <button className={sort==="cited"?"chip chip-on":"chip"} onClick={()=>setSort("cited")}>Most cited</button>
        </div>
      </div>
      {evError&&<p role="alert">{evError}</p>}
      {!evidence&&!evError&&<p>Loading published evidence…</p>}
      {evidence&&<>
        <p className="muted">{evidence.total} reviewed {evidence.total===1?"record":"records"}. Showing {evidence.items.length}.</p>
        {evidence.items.length===0&&<p className="muted">No matching evidence is available yet.</p>}
        <ul className="evidence-list">
          {evidence.items.map(e=>(<li key={e.id} className="evidence-card">
            <div className="evidence-meta">
              <span className="badge">{e.review_status.replaceAll("_"," ")}</span>
              <span className="cited-badge" title="Times cited by other evidence">× {e.cited_by_count}</span>
              {e.source_url&&<a href={e.source_url} target="_blank" rel="noreferrer" className="source-link">Source</a>}
            </div>
            <p className="excerpt">{e.excerpt}</p>
            {e.findings&&e.findings.length>0&&<div className="findings-row">
              <span className="muted small">Findings:</span>
              {e.findings.map(f=>(
                <a key={f.id} href={`/findings/${f.id}`} className="finding-chip">{f.label}</a>
              ))}
            </div>}
          </li>))}
        </ul>
      </>}
    </section>
  </main>;
}
