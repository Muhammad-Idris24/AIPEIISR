"use client";
import {useEffect,useState} from "react";
import {useProtectedApi} from "../../use-protected-api";
const API=process.env.NEXT_PUBLIC_API_URL||"http://localhost:8000";

type SortMode="newest"|"oldest"|"semantic"|"relevance";
type CollectionKey="investigations"|"evidence"|"claims"|"documents"|"findings";

type ResultItem=Record<string,any>&{semantic_score?:number};
type CollectionBag={items:ResultItem[];total:number;semantic_reranked?:boolean};
type SortInfo={by:string;dir:string;semantic:boolean;embedding_provider?:string|null};
type Facets={statuses:Record<string,number>;review_statuses:Record<string,number>;uncertainty:Record<string,number>;source_statuses:Record<string,number>};
type SearchResponse={query:string|null;collections:CollectionKey[];sort:SortInfo;facets:Facets;results:Record<CollectionKey,CollectionBag>};

const COLLECTIONS:{key:CollectionKey;label:string}[]=[
  {key:"investigations",label:"Investigations"},
  {key:"evidence",label:"Evidence"},
  {key:"claims",label:"Claims"},
  {key:"documents",label:"Documents"},
  {key:"findings",label:"Findings"},
];
const SORTS:{key:SortMode;label:string}[]=[
  {key:"newest",label:"Newest"},
  {key:"oldest",label:"Oldest"},
  {key:"relevance",label:"Relevance"},
  {key:"semantic",label:"Semantic"},
];

export default function AnalystSearchPage(){
  const {apiFetch,isAuthenticated,isLoading}=useProtectedApi();
  const [q,setQ]=useState("");
  const [collections,setCollections]=useState<Set<CollectionKey>>(new Set(COLLECTIONS.map(c=>c.key)));
  const [sort,setSort]=useState<SortMode>("newest");
  const [limit,setLimit]=useState(25);
  const [offset,setOffset]=useState(0);
  const [result,setResult]=useState<SearchResponse>();
  const [error,setError]=useState("");
  const [loading,setLoading]=useState(false);

  async function runSearch(off?:number){
    if(isLoading)return;
    if(!isAuthenticated){setError("Sign in with an analyst, reviewer, publisher, or admin account to search.");return}
    if(collections.size===0){setError("Select at least one collection.");return}
    setLoading(true);setError("");
    try{
      const r=await apiFetch(`${API}/analyst/search`,{
        method:"POST",
        headers:{"content-type":"application/json"},
        body:JSON.stringify({
          q:q.trim()||null,
          collections:Array.from(collections),
          sort_by:sort,
          sort_dir:"desc",
          limit,
          offset:off??offset,
        }),
      });
      if(!r.ok){const b=await r.json().catch(()=>({detail:r.statusText}));throw new Error(b.detail||`HTTP ${r.status}`)}
      setResult(await r.json());
    }catch(e:any){setError(e.message||"Search failed.")}
    finally{setLoading(false)}
  }

  function toggleCollection(k:CollectionKey){
    const next=new Set(collections);
    if(next.has(k))next.delete(k);else next.add(k);
    setCollections(next);setOffset(0);
  }
  function changeSort(s:SortMode){setSort(s);setOffset(0)}
  function changeLimit(n:number){setLimit(n);setOffset(0)}
  function changeQuery(v:string){setQ(v);setOffset(0)}

  useEffect(()=>{runSearch(0)},[isLoading,isAuthenticated]);

  function totalHits(r:SearchResponse):number{
    return COLLECTIONS.filter(c=>r.results[c.key]&&collections.has(c.key)).reduce((acc,c)=>acc+(r.results[c.key]?.total||0),0);
  }
  function maxTotalPerCollection(r:SearchResponse):number{
    let m=0;for(const c of COLLECTIONS){const t=r.results[c.key]?.total||0;if(t>m)m=t}return m;
  }

  return <main>
    <header><b>AIPEIISR Analyst</b><span>Structured multi-collection search with semantic rerank</span></header>
    <section>
      <p className="eyebrow">ANALYST SEARCH</p>
      <h1>Investigate across collections.</h1>
      <p className="muted small">This workspace uses your verified Auth0 access token. ANALYST, REVIEWER, PUBLISHER, or ADMIN role is required. API permissions are enforced server-side.</p>
      <p>Search investigations, evidence, claims, documents and findings. Use <b>Semantic</b> sort for cosine-reranked semantic similarity powered by the configured embedding provider. You can also browse <a href="/findings" style={{color:"#173f5f",fontWeight:600}}>published findings here →</a></p>
      <article>
        <div className="filters">
          <input type="search" value={q} onChange={e=>changeQuery(e.target.value)} placeholder="Query text (claim, entity, excerpt, ID…)" className="search-input"/>
          <label className="muted small">Top N
            <select value={limit} onChange={e=>changeLimit(parseInt(e.target.value,10))} className="limit-select">
              <option value={10}>10</option>
              <option value={25}>25</option>
              <option value={50}>50</option>
              <option value={100}>100</option>
            </select>
          </label>
          <button onClick={()=>runSearch(0)} disabled={loading}>{loading?"Searching…":"Search"}</button>
        </div>
        <div className="filters">
          <span className="muted small">Collections:</span>
          <div className="sortbar">
            {COLLECTIONS.map(c=>(
              <button key={c.key} className={collections.has(c.key)?"chip chip-on":"chip"} onClick={()=>toggleCollection(c.key)}>{c.label}</button>
            ))}
          </div>
        </div>
        <div className="filters">
          <span className="muted small">Sort:</span>
          <div className="sortbar">
            {SORTS.map(s=>(
              <button key={s.key} className={sort===s.key?"chip chip-on":"chip"} onClick={()=>changeSort(s.key)}>{s.label}</button>
            ))}
          </div>
          {result&&result.sort.semantic&&<span className="provider-chip provider-semantic" title={`Embedding provider: ${result.sort.embedding_provider||"mock"}`}>Semantic rerank · {result.sort.embedding_provider||"mock"}</span>}
        </div>
      </article>
      {error&&<p role="alert">{error}</p>}
      {!result&&!error&&!loading&&<p>Idle. Click <b>Search</b> to begin.</p>}
      {loading&&<p>Searching…</p>}
      {result&&<>
        <div className="filters" style={{justifyContent:"space-between"}}>
          <p className="muted small">Query: <i>{result.query||"(none)"}</i> · Sort by: <b>{result.sort.by}</b> · Collections queried: {result.collections.join(", ")} · Total candidate hits: <b>{totalHits(result)}</b> · Showing offset <b>{offset}</b>.</p>
          <div className="sortbar">
            <button className="chip" disabled={offset===0||loading} onClick={()=>{const n=Math.max(0,offset-limit);setOffset(n);runSearch(n)}}>← Prev page</button>
            <span className="muted small">page {Math.floor(offset/limit)+1} · showing {limit} per page</span>
            <button className="chip" disabled={loading||result?offset+limit>=maxTotalPerCollection(result):true} onClick={()=>{const n=offset+limit;setOffset(n);runSearch(n)}}>Next page →</button>
          </div>
        </div>
        <article>
          <h2>Facets</h2>
          <div className="subgrid facets-grid">
            <FacetCard title="Investigation statuses" data={result.facets.statuses}/>
            <FacetCard title="Evidence review" data={result.facets.review_statuses}/>
            <FacetCard title="Claim uncertainty" data={result.facets.uncertainty}/>
            <FacetCard title="Source statuses" data={result.facets.source_statuses}/>
          </div>
        </article>
        {COLLECTIONS.filter(c=>collections.has(c.key)).map(c=>{
          const bag=result.results[c.key];
          if(!bag)return null;
          return <article key={c.key}>
            <div className="filters" style={{justifyContent:"space-between"}}>
              <h2 style={{margin:0}}>{c.label} <span className="muted small">({bag.items.length}/{bag.total})</span></h2>
              <div className="sortbar">
                {bag.semantic_reranked&&<span className="provider-chip provider-semantic" title="Results reranked by cosine similarity to query embedding">Semantic reranked</span>}
                {c.key==="findings"&&<a href="/findings" className="chip chip-on">Browse all findings</a>}
              </div>
            </div>
            {bag.items.length===0&&<p className="muted">No results in this collection.</p>}
            {bag.items.length>0&&<ul className="evidence-list">
              {bag.items.map(item=>(<li key={item.id} className="evidence-card">
                <div className="evidence-meta">
                  {item.status&&<span className={`status-pill status-${item.status==="PUBLISHED"||item.status==="APPROVED"?"APPROVED":item.status==="UNPUBLISHED"||item.status==="DISABLED"?"DISABLED":"DRAFT"}`}>{item.status.replaceAll("_"," ")}</span>}
                  {item.review_status&&<span className="badge">{item.review_status.replaceAll("_"," ")}</span>}
                  {item.public===true&&<span className="status-pill status-APPROVED">PUBLIC</span>}
                  {item.semantic_score!==undefined&&<span className="semantic-badge" title={`Cosine similarity score (higher=closer match). Semantic sort: ${result.sort.semantic}. Provider: ${result.sort.embedding_provider||"mock"}`}>∿ {(item.semantic_score as number).toFixed(3)}</span>}
                  {item.cited_by_count!==undefined&&<span className="cited-badge" title="Times cited by other evidence">× {item.cited_by_count}</span>}
                  {item.finding_count!==undefined&&<span className="count-badge">{item.finding_count} finding{item.finding_count===1?"":"s"}</span>}
                  {item.evidence_count!==undefined&&<span className="count-badge">{item.evidence_count} evidence</span>}
                  {item.claim_count!==undefined&&<span className="count-badge">{item.claim_count} claim{item.claim_count===1?"":"s"}</span>}
                  {item.version_count!==undefined&&<span className="count-badge">v{item.version_count}</span>}
                  {item.investigation_count!==undefined&&<span className="count-badge">{item.investigation_count} inv</span>}
                </div>
                <p className="excerpt">{item.label||item.text||item.excerpt||item.content?.slice(0,300)||item.id}</p>
                <div className="findings-row">
                  {item.source_name&&<span className="muted small">Source: {item.source_name}</span>}
                  {item.source_url&&<a href={item.source_url} target="_blank" rel="noreferrer" className="source-link">Source</a>}
                  {item.submission_id&&<span className="muted small">Submission: {item.submission_id}</span>}
                  {item.created_at&&<span className="muted small">{new Date(item.created_at).toLocaleDateString()}</span>}
                  {c.key==="findings"&&item.id&&<a href={`/findings/${item.id}`} className="finding-chip">View finding →</a>}
                </div>
              </li>))}
            </ul>}
          </article>
        })}
        <div className="filters" style={{justifyContent:"flex-end",marginTop:8}}>
          <button className="chip" disabled={offset===0||loading} onClick={()=>{const n=Math.max(0,offset-limit);setOffset(n);runSearch(n)}}>← Prev page</button>
          <span className="muted small">Showing {offset+1}–{limit} offset window (per collection)</span>
          <button className="chip" disabled={loading||result?offset+limit>=maxTotalPerCollection(result):true} onClick={()=>{const n=offset+limit;setOffset(n);runSearch(n)}}>Next page →</button>
        </div>
      </>}
    </section>
  </main>;
}

function FacetCard({title,data}:{title:string;data:Record<string,number>}){
  const entries=Object.entries(data||{});
  return <div className="submetric tone-neutral">
    <span style={{fontWeight:600,fontSize:13,color:"#102c43",marginBottom:6}}>{title}</span>
    {entries.length===0?<span className="muted small">—</span>:<div style={{display:"flex",flexDirection:"column",gap:4}}>
      {entries.map(([k,v])=>(<div key={k} style={{display:"flex",justifyContent:"space-between",gap:8}}>
        <span className="muted small">{k.replaceAll("_"," ")}</span>
        <strong style={{fontSize:14,color:"#102c43"}}>{v}</strong>
      </div>))}
    </div>}
  </div>
}
