"use client";
import {useEffect,useState} from "react";
import {SafeTokenInfo,useProtectedApi} from "../use-protected-api";
const API=process.env.NEXT_PUBLIC_API_URL||"http://localhost:8000";

type SourcesDict={total:number;draft:number;disabled:number;approved:number};
type Overview={
  active_investigations:number;
  pending_reviews:number;
  sources:SourcesDict;
  documents:number;
  claims:number;
  citizen_escalations:number;
  public_evidence:number;
  internal_evidence_unreviewed:number;
  published_findings:number;
  citizen_submissions:number;
  evidence_relations:number;
  workflow:{submissions_to_escalations:number};
};
type ProviderNames={llm:string;search:string;embedding:string};
type WorkerStatus={running:boolean;pending:number;dispatched:number;dead:number;name?:string;poll_seconds?:number};
type SchedulerStatus={running:boolean;sources_total:number;sources_approved:number;interval_seconds?:number};
type Inventory={sources:number;documents:number;claims:number;evidence_relations:number;finding_versions:number};
type HealthInfo={
  status:string;mode:string;providers:ProviderNames;persistence:string;
  worker:WorkerStatus;scheduler:SchedulerStatus;inventory:Inventory;
  auth?:{method:string;role:string;auth0_configured:boolean;auth0_expected_issuer?:string;auth0_expected_audience?:string;auth0_validation_diagnostic?:string|null;x_role_enabled:boolean};
};

export default function SituationRoom(){
  const {apiFetch,getSafeTokenInfo,isAuthenticated,isLoading}=useProtectedApi();
  const [data,setData]=useState<Overview>();
  const [health,setHealth]=useState<HealthInfo>();
  const [error,setError]=useState("");
  const [healthError,setHealthError]=useState("");
  const [tokenInfo,setTokenInfo]=useState<SafeTokenInfo>();
  const [tokenError,setTokenError]=useState("");
  useEffect(()=>{
    if(isLoading)return;
    if(!isAuthenticated){setError("Sign in with an analyst, reviewer, publisher, manager, or admin account to view the Situation Room.");return}
    getSafeTokenInfo().then(setTokenInfo).catch((e:unknown)=>setTokenError(e instanceof Error?e.message:"Could not inspect access-token metadata."));
    apiFetch(`${API}/room/overview`)
      .then(async r=>{
        if(r.ok)return r.json();
        const body=await r.json().catch(()=>({}));
        throw new Error(`Request ${r.status}${body.detail?`: ${body.detail}`:""}`);
      })
      .then(setData)
      .catch((e:unknown)=>setError(`Operational data is temporarily unavailable. Reference: room-overview. ${e instanceof Error?e.message:"Request failed."}`));
    apiFetch(`${API}/health`)
      .then(async r=>{
        if(r.ok)return r.json();
        const body=await r.json().catch(()=>({}));
        throw new Error(`Request ${r.status}${body.detail?`: ${body.detail}`:""}`);
      })
      .then(setHealth)
      .catch((e:unknown)=>setHealthError(`Health and provider data is temporarily unavailable. Reference: health-endpoint. ${e instanceof Error?e.message:"Request failed."}`));
  },[apiFetch,getSafeTokenInfo,isAuthenticated,isLoading]);

  function providerState(name:string|undefined):{state:"online"|"offline"|"mock";label:string}{
    if(!name)return{state:"offline",label:"Not available"};
    const n=name.toLowerCase();
    if(n.includes("mock"))return{state:"mock",label:"Mock (deterministic dev)"};
    if(n.includes("ollama")||n.includes("hugging")||n.includes("hf")||n.includes("openrouter")||n.includes("open-ai")||n.includes("gemini"))return{state:"online",label:`Live · ${name}`};
    return{state:"mock",label:name};
  }

  return <main>
    <header>
      <b>AIPEIISR Situation Room</b><span>Professional investigation environment</span>
    </header>
    <section>
      <p className="eyebrow">OVERVIEW</p>
      <h1>What needs human attention?</h1>
      <p className="muted small">This workspace uses your verified Auth0 access token. API permissions are enforced server-side.</p>
      {health?.auth&&<p className="muted small">API authentication: <b>{health.auth.method}</b> · interpreted platform role: <b>{health.auth.role}</b></p>}
      {tokenInfo&&<p className="muted small">Token diagnostic: algorithm <b>{tokenInfo.alg||"missing"}</b> · issuer <b>{tokenInfo.iss||"missing"}</b> · audience <b>{tokenInfo.aud||"missing"}</b> · roles claim <b>{tokenInfo.rolesClaimPresent?"present":"missing"}</b>.</p>}
      {health?.auth?.auth0_expected_issuer&&<p className="muted small">API expects: issuer <b>{health.auth.auth0_expected_issuer}</b> · audience <b>{health.auth.auth0_expected_audience}</b>.</p>}
      {health?.auth?.auth0_validation_diagnostic&&<p className="muted small">Local API validation category: <b>{health.auth.auth0_validation_diagnostic}</b>.</p>}
      {tokenError&&<p role="alert">Token diagnostic: {tokenError}</p>}
      {error&&<p role="alert">{error}</p>}
      {!data&&!error&&<p>Loading operational overview…</p>}
      {data&&<>
        <div className="grid">
          <Card n={data.active_investigations} t="Active investigations"/>
          <Card n={data.pending_reviews} t="Pending peer reviews"/>
          <Card n={data.citizen_escalations} t="Citizen escalations"/>
          <Card n={data.published_findings} t="Published findings"/>
          <Card n={data.claims} t="Detected claims"/>
          <Card n={data.documents} t="Collected documents"/>
          <Card n={data.public_evidence} t="Public evidence"/>
          <Card n={data.internal_evidence_unreviewed} t="Evidence awaiting review"/>
          <Card n={data.evidence_relations} t="Evidence citation links"/>
          <Card n={data.citizen_submissions} t="Citizen submissions"/>
          <Card n={data.workflow.submissions_to_escalations} t="Escalation rate" suffix="x"/>
        </div>
        <div className="sources-block">
          <p className="eyebrow">SOURCE GOVERNANCE</p>
          <div className="subgrid">
            <SubCard n={data.sources.total} t="Total sources"/>
            <SubCard n={data.sources.approved} t="Approved" tone="good"/>
            <SubCard n={data.sources.draft} t="Draft" tone="warn"/>
            <SubCard n={data.sources.disabled} t="Disabled" tone="bad"/>
          </div>
          <p className="muted small">Only <b>APPROVED</b> sources contribute to scheduled ingestion. Draft and disabled sources gate ingestion with 409 at the API layer.</p>
        </div>
        <div className="sources-block">
          <p className="eyebrow">AI PROVIDER HEALTH</p>
          {healthError&&<p role="alert">{healthError}</p>}
          {!health&&!healthError&&<p>Loading provider status…</p>}
          {health&&<>
            <div className="health-providers">
              {(()=>{
                const llm=providerState(health.providers.llm);
                const emb=providerState(health.providers.embedding);
                const sch=health.providers.search;
                const pers=health.persistence;
                return <>
                  <ProviderCard kind="LLM Analyze" name={health.providers.llm||"Unavailable"} state={llm.state} stateLabel={llm.label}/>
                  <ProviderCard kind="Embedding" name={health.providers.embedding||"Unavailable"} state={emb.state} stateLabel={emb.label}/>
                  <ProviderCard kind="Search" name={sch||"internal"} state={sch.includes("semantic")||sch.includes("analyst")?"mock":"online"} stateLabel={`Internal · ${sch}`}/>
                  <ProviderCard kind="Persistence" name={pers||"sqlite"} state={pers.includes("postgres")||pers.includes("sqlite")?"online":"offline"} stateLabel={pers.toUpperCase()}/>
                </>;
              })()}
            </div>
            <div className="subgrid" style={{marginTop:12}}>
              <SubCard n={health.inventory.sources} t="Sources in DB" tone="neutral"/>
              <SubCard n={health.inventory.documents} t="Documents in DB" tone="neutral"/>
              <SubCard n={health.inventory.claims} t="Claims in DB" tone="neutral"/>
              <SubCard n={health.inventory.finding_versions} t="Finding versions" tone="neutral"/>
            </div>
            <div className="filters" style={{marginTop:12}}>
              <span className={`provider-chip ${health.worker.running?"provider-llm":"provider-mock"}`}>Worker · {health.worker.running?"RUNNING":"STOPPED"}</span>
              <span className="count-badge">Pending {health.worker.pending}</span>
              <span className="count-badge">Dispatched {health.worker.dispatched}</span>
              <span className="count-badge">Dead (DLQ) {health.worker.dead}</span>
            </div>
            <div className="filters" style={{marginTop:4}}>
              <span className={`provider-chip ${health.scheduler.running?"provider-semantic":"provider-mock"}`}>Scheduler · {health.scheduler.running?"RUNNING":"STOPPED"}</span>
              <span className="count-badge">Sources total {health.scheduler.sources_total}</span>
              <span className="count-badge">Approved {health.scheduler.sources_approved}</span>
            </div>
            <p className="muted small" style={{marginTop:8}}>
              Providers are selected via environment variables (LLM_PROVIDER / EMBEDDING_PROVIDER) and fall back to deterministic Mock on any auth or network failure.
              Mock guarantees offline test/dev availability; its outputs are explicitly non-authoritative and never auto-publish.
              Live provider pings are gated by timeouts (AI_TIMEOUT_SECONDS) and will silently downgrade to Mock on failure.
            </p>
          </>}
        </div>
        <article>
          <p className="badge">HUMAN REVIEW REQUIRED</p>
          <h2>Operating principle</h2>
          <p>AI outputs are signals and recommendations. Analysts investigate, reviewers assess, and publishers authorize findings. Source approval, evidence publication and finding release all require human actions.</p>
        </article>
      </>}
    </section>
  </main>;
}
function Card({n,t,suffix}:{n:number|string;t:string;suffix?:string}){
  return <article className="metric">
    <strong>{n}{suffix??""}</strong>
    <span>{t}</span>
  </article>;
}
function SubCard({n,t,tone}:{n:number;t:string;tone?:"good"|"warn"|"bad"|"neutral"}){
  return <article className={`submetric tone-${tone||"neutral"}`}>
    <strong>{n}</strong>
    <span>{t}</span>
  </article>;
}
function ProviderCard({kind,name,state,stateLabel}:{kind:string;name:string;state:"online"|"offline"|"mock";stateLabel:string}){
  return <div className={`provider-card ${state}`}>
    <span className="kind">{kind}</span>
    <span className="name">{name}</span>
    <span className="status-dot">{stateLabel}</span>
  </div>;
}
