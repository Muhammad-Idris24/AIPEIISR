import os
from enum import Enum
from fastapi import FastAPI,HTTPException,Header,Query,Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel,Field
from sqlalchemy import or_, desc, asc, func, and_
from .db import Session,Source,Submission,Investigation,Finding,FindingVersion,Audit,Document,Claim,Evidence,EvidenceRelation,InvestigationEvidence,OutboxEvent,Embedding,init_db,cosine_similarity,IS_SQLITE,URL as DB_URL
from .collector import collect_synthetic
from .jobs import emit,dispatch_pending
from .providers import get_llm_provider,get_embedding_provider,Analysis
from .auth import resolve_role,resolve_actor,examples_for_current_secret,X_ROLE_ENABLED,JWT_SECRET,decode_bearer_token,Role as AuthRole
from . import auth as auth_module
from . import worker
from . import scheduler

app=FastAPI(title='AIPEIISR API',version='0.6.1')
app.add_middleware(CORSMiddleware,allow_origins=['http://localhost:3000'],allow_methods=['GET','POST'],allow_headers=['content-type','x-role','authorization'])

@app.middleware('http')
async def apply_authenticated_role(request, call_next):
    """Bind a verified bearer role to legacy route guards without trusting x-role in production.

    Existing P0 routes accept ``x-role`` as their compatibility parameter. This
    middleware injects that value only after signature verification and strips
    caller-provided x-role whenever the development fallback is disabled.
    """
    authorization=request.headers.get('authorization')
    verified=auth_module.decode_bearer_token(authorization) if authorization else None
    headers=[(k,v) for k,v in request.scope['headers'] if k.lower()!=b'x-role']
    if verified:
        resolved=auth_module.resolve_role(authorization,None)
        headers.append((b'x-role',resolved.value.encode()))
    elif auth_module.X_ROLE_ENABLED:
        supplied=request.headers.get('x-role')
        if supplied:
            headers.append((b'x-role',supplied.encode()))
    request.scope['headers']=headers
    return await call_next(request)
init_db()
llm=get_llm_provider()
emb=get_embedding_provider()
worker.start_worker()
scheduler.start_scheduler()


def _embed_text(collection:str, entity_id:str, text:str) -> list[float] | None:
    s=Session()
    try:
        existing=s.query(Embedding).filter_by(collection=collection, entity_id=entity_id).first()
        if existing and existing.provider==emb.name and existing.dim and len(existing.vector)==existing.dim:
            return list(existing.vector)
        try:
            vec=emb.embed(text or "")
        except Exception:
            return None
        row=Embedding(collection=collection,entity_id=entity_id,provider=emb.name,dim=len(vec),vector=list(vec))
        if existing:
            existing.provider=row.provider;existing.dim=row.dim;existing.vector=row.vector;existing.updated_at=row.updated_at
        else:
            s.add(row)
        s.commit()
        return vec
    except Exception:
        s.rollback();return None
    finally:
        s.close()

def _semantic_rerank(collection:str, query_vec:list[float]|None, rows:list, text_for_row, limit:int) -> list:
    if not query_vec: return rows
    s=Session()
    try:
        known={e.entity_id:list(e.vector) for e in s.query(Embedding).filter(Embedding.collection==collection,Embedding.provider==emb.name).all()}
    finally:
        s.close()
    scored=[]
    for row in rows:
        eid=row.id if hasattr(row,'id') else str(row)
        vec=known.get(eid)
        if not vec:
            t=text_for_row(row) or ""
            try:
                vec=emb.embed(t) if t else None
            except Exception:
                vec=None
        scored.append((cosine_similarity(query_vec,vec or []) if vec else 0.0,row))
    scored.sort(key=lambda x:x[0],reverse=True)
    out=[]
    for sc,r in scored[:limit]:
        if hasattr(r,'_sa_instance_state'):
            d={c.name:getattr(r,c.name) for c in r.__table__.columns}
            d['semantic_score']=round(sc,4);out.append(d)
        else:
            out.append({**r,'semantic_score':round(sc,4)})
    return out

class Role(str,Enum): CITIZEN='CITIZEN';ANALYST='ANALYST';REVIEWER='REVIEWER';PUBLISHER='PUBLISHER';ADMIN='ADMIN';AI_WORKER='AI_WORKER'
class SubmissionIn(BaseModel):text:str|None=None;url:str|None=None;media_reference:str|None=None;context:str|None=None;consent:bool
class SourceIn(BaseModel):name:str;url:str;collector_type:str='RSS';interval_minutes:int=Field(60,ge=5)
class ReviewIn(BaseModel):decision:str;comments:str=Field(min_length=3)
class EvidenceIn(BaseModel):claim_id:str|None=None;source_url:str;excerpt:str=Field(min_length=3);relation:str='REQUIRES_REVIEW'
class LinkEvidenceIn(BaseModel):evidence_id:str;rationale:str=Field(min_length=3)
class PublishEvidenceIn(BaseModel):public:bool
class InternalSearchIn(BaseModel):q:str|None=None;statuses:list[str]|None=None;investigation_id:str|None=None;submission_id:str|None=None;limit:int=Field(20,ge=1,le=200)
class AnalystSearchIn(BaseModel):
    q:str|None=None;collections:list[str]=Field(default_factory=lambda:['investigations','evidence','claims','documents','findings'])
    statuses:list[str]|None=None;uncertainty:list[str]|None=None;review_statuses:list[str]|None=None;public:bool|None=None;relation_types:list[str]|None=None
    source_ids:list[str]|None=None;date_from:str|None=None;date_to:str|None=None
    sort_by:str='relevance';sort_dir:str='desc'
    limit:int=Field(25,ge=1,le=500);offset:int=0
class EvidenceRelationIn(BaseModel):target_evidence_id:str;relation_type:str=Field('CORROBORATES',min_length=2);rationale:str|None=None
class FindingUpdateIn(BaseModel):label:str;note:str|None=None;status:str='PUBLISHED'
class SourceStatusIn(BaseModel):status:str=Field(pattern='^(APPROVED|DISABLED|DRAFT|RETIRED)$')
class FindingUnpublishIn(BaseModel):note:str=Field(min_length=3)
class EvidencePublishIn(BaseModel):public:bool;release_note:str|None=None

def ses():return Session()
def req(role,allowed):
 try:r=Role(role or 'CITIZEN')
 except ValueError:raise HTTPException(403,'Permission denied')
 if r not in allowed:raise HTTPException(403,'Permission denied')
def role_resolver(authorization:str|None=Header(None,alias='Authorization'),x_role:str|None=Header(None)):
    return resolve_role(authorization,x_role)
def actor_resolver(authorization:str|None=Header(None,alias='Authorization'),x_role:str|None=Header(None)):
    return resolve_actor(authorization,x_role)
def out(o):return {c.name:getattr(o,c.name) for c in o.__table__.columns}
def log(s,a,e,actor='system'):s.add(Audit(action=a,entity=e or 'pending',actor=actor))

@app.get('/health')
def health(authorization:str|None=Header(None,alias='Authorization'),x_role:str|None=Header(None)):
    s=Session()
    try:
        sources=s.query(Source).count()
        docs=s.query(Document).count()
        claims=s.query(Claim).count()
        rels=s.query(EvidenceRelation).count()
        fvs=s.query(FindingVersion).count()
    finally:
        s.close()
    role=resolve_role(authorization,x_role)
    auth={
        'method':('auth0' if auth_module.AUTH0_ENABLED else 'jwt') if (authorization and decode_bearer_token(authorization)) else ('x-role' if (X_ROLE_ENABLED and x_role) else 'default'),
        'role':role.value,
        'jwt_configured': bool(JWT_SECRET),
        'auth0_configured': auth_module.AUTH0_ENABLED,
        'auth0_expected_issuer': auth_module.AUTH0_ISSUER if auth_module.AUTH0_ENABLED else None,
        'auth0_expected_audience': auth_module.AUTH0_AUDIENCE if auth_module.AUTH0_ENABLED else None,
        'auth0_validation_diagnostic': auth_module.auth0_validation_diagnostic() if (auth_module.AUTH0_ENABLED and (os.environ.get('APP_ENV','development') == 'development')) else None,
        'x_role_enabled': X_ROLE_ENABLED,
    }
    return {
        'status':'ok',
        'mode':'development' if X_ROLE_ENABLED and not (JWT_SECRET or auth_module.AUTH0_ENABLED) else ('production-ready' if (JWT_SECRET or auth_module.AUTH0_ENABLED) else 'staging'),
        'auth':auth,
        'providers':{'llm':llm.name,'search':'internal+analyst+semantic','embedding':emb.name},
        'persistence':'sqlite' if IS_SQLITE else DB_URL.split(':')[0],
        'worker':worker.worker_status(),
        'scheduler':scheduler.scheduler_status(),
        'inventory':{'sources':sources,'documents':docs,'claims':claims,'evidence_relations':rels,'finding_versions':fvs},
    }
# ---------- AUTH SCAFFOLD ----------
@app.get('/auth/whoami')
def auth_whoami(r:AuthRole=Depends(role_resolver),a:str=Depends(actor_resolver)):
    return {'role':r.value,'actor':a,'jwt_configured':bool(JWT_SECRET),'auth0_configured':auth_module.AUTH0_ENABLED,'x_role_enabled':X_ROLE_ENABLED}
@app.get('/auth/examples')
def auth_examples(r:AuthRole=Depends(role_resolver)):
    if r!=AuthRole.ADMIN:raise HTTPException(403,'Permission denied')
    return {'jwt_configured':bool(JWT_SECRET),'x_role_enabled':X_ROLE_ENABLED,'examples':examples_for_current_secret() or {'note':'Set JWT_SECRET env var and restart the API to generate example HS256 JWTs per role. Tokens below are HS256-signed with JWT_SECRET. NEVER hardcode secrets in repos.'}}
class LoginIn(BaseModel):email:str;password:str
@app.post('/auth/login')
def auth_login(payload:LoginIn):
    raise HTTPException(501,'Login scaffold only. Production implementation requires a user directory (DB table with bcrypt, external IdP via OAuth/OpenID Connect, or LDAP). For local dev, set JWT_SECRET and use GET /auth/examples (as ADMIN via x-role) to print example per-role JWTs that can be pasted into an Authorization: Bearer header.')

# ---------- SOURCES + SOURCE GOVERNANCE ----------
@app.post('/sources')
def create_source(b:SourceIn,role:AuthRole=Depends(role_resolver),actor:str=Depends(actor_resolver)):
 req(role,{Role.ADMIN});s=ses();o=Source(**{**b.model_dump(),'status':'DRAFT'});s.add(o);s.flush();log(s,'SOURCE_CREATED',o.id,actor);emit(s,'SourceCreated',o.id);s.commit();return out(o)
@app.get('/sources')
def sources(status:str|None=None,role:AuthRole=Depends(role_resolver)):
 req(role,{Role.ADMIN,Role.ANALYST});s=ses();q=s.query(Source)
 if status:q=q.filter(Source.status==status)
 return [out(x) for x in q.order_by(desc(Source.created_at)).all()]
@app.get('/sources/{sid}')
def get_source(sid:str,role:AuthRole=Depends(role_resolver)):
 req(role,{Role.ADMIN,Role.ANALYST});s=ses();src=s.get(Source,sid)
 if not src:raise HTTPException(404,'Source not found')
 recent_docs=s.query(Document).filter_by(source_id=sid).order_by(desc(Document.collected_at)).limit(5).all()
 changes=s.query(Audit).filter(Audit.entity==sid,Audit.action.like('SOURCE_%')).order_by(desc(Audit.created_at)).all()
 return {'source':out(src),'recent_documents':[out(d) for d in recent_docs],'audit':[out(a) for a in changes]}
@app.post('/sources/{sid}/status')
def set_source_status(sid:str,b:SourceStatusIn,x_role:str|None=Header(None)):
 req(x_role,{Role.ADMIN});s=ses();src=s.get(Source,sid)
 if not src:raise HTTPException(404,'Source not found')
 old=src.status
 src.status=b.status
 log(s,f'SOURCE_STATUS_{old}_TO_{b.status}',sid,'admin')
 if b.status in ('APPROVED','DISABLED'):emit(s,f'Source{b.status}',sid)
 s.commit();return out(src)
@app.post('/sources/{sid}/collect-fixture')
def collect_fixture(sid:str,content:str,x_role:str|None=Header(None)):
 req(x_role,{Role.ADMIN});s=ses();src=s.get(Source,sid)
 if not src:raise HTTPException(404,'Source not found')
 if src.status in ('DISABLED','DRAFT'):raise HTTPException(409,f'Source status {src.status} blocks ingestion')
 try:d,created=collect_synthetic(sid,content)
 except ValueError:raise HTTPException(404,'Source not found')
 return {'document':out(d),'created':created,'mode':'synthetic fixture','source_status':src.status}
@app.post('/sources/{sid}/run-once')
def run_source_once(sid:str,x_role:str|None=Header(None)):
 req(x_role,{Role.ADMIN,Role.ANALYST});ok=scheduler.run_source_now(sid)
 if not ok:raise HTTPException(404,'Source not found or disabled')
 return {'scheduled':True,'source_id':sid}

# ---------- DOCUMENTS ----------
@app.get('/documents')
def documents(source_id:str|None=None,status:str|None=None,limit:int=Query(100,ge=1,le=500),offset:int=Query(0,ge=0),x_role:str|None=Header(None)):
 req(x_role,{Role.ANALYST,Role.REVIEWER,Role.ADMIN})
 s=ses();q=s.query(Document)
 if source_id:q=q.filter(Document.source_id==source_id)
 if status:q=q.filter(Document.status==status)
 return [out(x) for x in q.order_by(desc(Document.collected_at)).offset(offset).limit(limit).all()]
@app.get('/documents/{did}')
def get_document(did:str,x_role:str|None=Header(None)):
 req(x_role,{Role.ANALYST,Role.REVIEWER,Role.ADMIN});s=ses();d=s.get(Document,did)
 if not d:raise HTTPException(404,'Document not found')
 return out(d)
@app.get('/documents/{did}/evidence')
def document_evidence(did:str,x_role:str|None=Header(None)):
 req(x_role,{Role.ANALYST,Role.REVIEWER,Role.ADMIN});s=ses();doc=s.get(Document,did)
 if not doc:raise HTTPException(404,'Document not found')
 claim_ids=[c.id for c in s.query(Claim).filter_by(document_id=did).all()]
 ev_rows=s.query(Evidence).filter(Evidence.claim_id.in_(claim_ids)).all() if claim_ids else []
 linked_rows=s.query(Evidence).filter(Evidence.source_url==doc.url).all() if doc.url else []
 all_ev={e.id:e for e in ev_rows+linked_rows}
 return {'document':out(doc),'claims':[out(c) for c in s.query(Claim).filter_by(document_id=did).all()],'evidence':[out(e) for e in all_ev.values()]}
@app.get('/documents/{did}/chain')
def document_chain(did:str,x_role:str|None=Header(None)):
 req(x_role,{Role.ANALYST,Role.REVIEWER,Role.ADMIN});s=ses();doc=s.get(Document,did)
 if not doc:raise HTTPException(404,'Document not found')
 source=s.get(Source,doc.source_id)
 claims=s.query(Claim).filter_by(document_id=did).all()
 chain_evidence=[];investigations_links=[]
 for c in claims:
  evs=s.query(Evidence).filter_by(claim_id=c.id).all()
  for e in evs:
   chain_evidence.append({'claim':out(c),'evidence':out(e)})
   links=s.query(InvestigationEvidence).filter_by(evidence_id=e.id).all()
   for L in links:
    inv=s.get(Investigation,L.investigation_id)
    f=s.query(Finding).filter_by(investigation_id=inv.id).first() if inv else None
    investigations_links.append({'link':out(L),'investigation':out(inv) if inv else None,'finding':out(f) if f else None})
 return {'source':out(source) if source else None,'document':out(doc),'claims':[out(c) for c in claims],'evidence_links':chain_evidence,'investigations':investigations_links}

# ---------- CLAIMS ----------
@app.get('/claims')
def claims(document_id:str|None=None,status:str|None=None,uncertainty:str|None=None,x_role:str|None=Header(None)):
 req(x_role,{Role.ANALYST,Role.REVIEWER,Role.ADMIN});s=ses();q=s.query(Claim)
 if document_id:q=q.filter(Claim.document_id==document_id)
 if status:q=q.filter(Claim.status==status)
 if uncertainty:q=q.filter(Claim.uncertainty==uncertainty)
 return [out(x) for x in q.all()]

# ---------- EVIDENCE + CITATION GRAPH ----------
@app.post('/evidence')
def add_evidence(b:EvidenceIn,x_role:str|None=Header(None)):
 req(x_role,{Role.ANALYST});s=ses();e=Evidence(**b.model_dump());s.add(e);s.flush();log(s,'EVIDENCE_ADDED',e.id,'analyst');s.commit();return out(e)
@app.get('/evidence')
def list_evidence(public:bool|None=None,review_status:str|None=None,claim_id:str|None=None,relation:str|None=None,limit:int=Query(100,ge=1,le=500),offset:int=Query(0,ge=0),x_role:str|None=Header(None)):
 if public is not True:req(x_role,{Role.ANALYST,Role.REVIEWER,Role.ADMIN})
 s=ses();q=s.query(Evidence)
 if public is not None:q=q.filter(Evidence.public==public)
 if review_status:q=q.filter(Evidence.review_status==review_status)
 if claim_id:q=q.filter(Evidence.claim_id==claim_id)
 if relation:q=q.filter(Evidence.relation==relation)
 return [out(x) for x in q.order_by(desc(Evidence.created_at)).offset(offset).limit(limit).all()]
@app.get('/evidence/{eid}')
def evidence(eid:str,x_role:str|None=Header(None)):
 s=ses();e=s.get(Evidence,eid)
 if not e:raise HTTPException(404,'Evidence not found')
 if not e.public: req(x_role,{Role.ANALYST,Role.REVIEWER,Role.PUBLISHER,Role.ADMIN})
 return out(e)
@app.post('/evidence/{eid}/public')
def set_evidence_public(eid:str,b:EvidencePublishIn,x_role:str|None=Header(None)):
 req(x_role,{Role.PUBLISHER});s=ses();e=s.get(Evidence,eid)
 if not e:raise HTTPException(404,'Evidence not found')
 e.public=b.public
 e.review_status='HUMAN_REVIEWED' if b.public else e.review_status
 log(s,'EVIDENCE_PUBLICATION_CHANGED',eid,'publisher')
 emit(s,'EvidencePublished' if b.public else 'EvidenceUnpublished',eid)
 s.commit();return out(e)
@app.get('/evidence/{eid}/investigations')
def evidence_investigations(eid:str,x_role:str|None=Header(None)):
 req(x_role,{Role.ANALYST,Role.REVIEWER,Role.ADMIN});s=ses();e=s.get(Evidence,eid)
 if not e:raise HTTPException(404,'Evidence not found')
 links=s.query(InvestigationEvidence).filter_by(evidence_id=eid).all()
 return [{'link':out(L),'investigation':out(s.get(Investigation,L.investigation_id))} for L in links]
@app.post('/evidence/{eid}/relations')
def add_evidence_relation(eid:str,b:EvidenceRelationIn,x_role:str|None=Header(None)):
 req(x_role,{Role.ANALYST,Role.REVIEWER});s=ses()
 src=s.get(Evidence,eid);tgt=s.get(Evidence,b.target_evidence_id)
 if not src or not tgt:raise HTTPException(404,'Evidence not found')
 if eid==b.target_evidence_id:raise HTTPException(422,'Evidence cannot relate to itself')
 try:
  rel=EvidenceRelation(source_evidence_id=eid,target_evidence_id=b.target_evidence_id,relation_type=b.relation_type,rationale=b.rationale)
  s.add(rel);s.flush();log(s,'EVIDENCE_RELATION_CREATED',rel.id,'analyst')
 except Exception:
  s.rollback();raise HTTPException(409,'Relation already exists or invalid')
 s.commit();return out(rel)
@app.get('/evidence/{eid}/relations')
def evidence_relations(eid:str,relation_type:str|None=None,x_role:str|None=Header(None)):
 req(x_role,{Role.ANALYST,Role.REVIEWER,Role.PUBLISHER,Role.ADMIN});s=ses();e=s.get(Evidence,eid)
 if not e:raise HTTPException(404,'Evidence not found')
 q=s.query(EvidenceRelation).filter(or_(EvidenceRelation.source_evidence_id==eid,EvidenceRelation.target_evidence_id==eid))
 if relation_type:q=q.filter(EvidenceRelation.relation_type==relation_type)
 rows=q.all()
 result=[]
 for r in rows:
  other_src=r.target_evidence_id if r.source_evidence_id==eid else r.source_evidence_id
  direction='outgoing' if r.source_evidence_id==eid else 'incoming'
  result.append({'relation':out(r),'other_evidence':out(s.get(Evidence,other_src)),'direction':direction})
 cite_in=s.query(EvidenceRelation).filter(EvidenceRelation.target_evidence_id==eid).count()
 cite_out=s.query(EvidenceRelation).filter(EvidenceRelation.source_evidence_id==eid).count()
 invs=s.query(InvestigationEvidence).filter_by(evidence_id=eid).count()
 return {'relations':result,'citation_counts':{'cited_by':cite_in,'cites':cite_out,'linked_investigations':invs}}
@app.get('/graph/evidence')
def evidence_graph(min_links:int=Query(1,ge=0),limit:int=Query(100,ge=1,le=1000),x_role:str|None=Header(None)):
 req(x_role,{Role.ANALYST,Role.REVIEWER,Role.ADMIN});s=ses()
 rels=s.query(EvidenceRelation).limit(limit).all()
 nodes={}
 for r in rels:
  nodes[r.source_evidence_id]=s.get(Evidence,r.source_evidence_id)
  nodes[r.target_evidence_id]=s.get(Evidence,r.target_evidence_id)
 return {
  'nodes':[out(n) for n in nodes.values() if n],
  'edges':[out(r) for r in rels],
  'node_count':len(nodes),
  'edge_count':len(rels),
 }

# ---------- PUBLIC PROJECTIONS ----------
@app.get('/public/evidence')
def public_evidence(q:str='',sort:str=Query('newest',pattern='^(newest|oldest|cited)$'),limit:int=Query(20,ge=1,le=200),offset:int=Query(0,ge=0)):
 s=ses();query=s.query(Evidence).filter_by(public=True)
 if q.strip():
  t=f'%{q.strip()}%';query=query.filter(or_(Evidence.excerpt.ilike(t),Evidence.source_url.ilike(t)))
 if sort=='newest':order=desc(Evidence.created_at)
 elif sort=='oldest':order=asc(Evidence.created_at)
 else:
  sub=s.query(EvidenceRelation.target_evidence_id,func.count(EvidenceRelation.id).label('cc')).group_by(EvidenceRelation.target_evidence_id).subquery()
  order=desc(func.coalesce(sub.c.cc,0))
  query=query.outerjoin(sub,sub.c.target_evidence_id==Evidence.id)
 rows=query.order_by(order).offset(offset).limit(limit).all()
 out_rows=[]
 for e in rows:
  rel=s.query(Finding).join(Investigation,Finding.investigation_id==Investigation.id).join(InvestigationEvidence,InvestigationEvidence.investigation_id==Investigation.id).filter(InvestigationEvidence.evidence_id==e.id).all()
  cite=s.query(EvidenceRelation).filter(EvidenceRelation.target_evidence_id==e.id).count()
  out_rows.append({**out(e),'findings':[out(f) for f in rel],'cited_by_count':cite})
 return {'items':out_rows,'total':query.count(),'limit':limit,'offset':offset}
@app.get('/public/findings')
def public_findings(q:str='',status:str|None=None,limit:int=Query(20,ge=1,le=200),offset:int=Query(0,ge=0)):
 s=ses();query=s.query(Finding)
 if status:query=query.filter(Finding.status==status)
 if q.strip():t=f'%{q.strip()}%';query=query.filter(Finding.label.ilike(t))
 rows=query.order_by(desc(Finding.created_at)).offset(offset).limit(limit).all()
 enriched=[]
 for f in rows:
  inv=s.get(Investigation,f.investigation_id)
  ev_links=s.query(InvestigationEvidence).filter_by(investigation_id=inv.id).all() if inv else []
  pub_ev=[out(s.get(Evidence,L.evidence_id)) for L in ev_links if s.get(Evidence,L.evidence_id) and s.get(Evidence,L.evidence_id).public]
  enriched.append({**out(f),'evidence_count':len(pub_ev),'evidence':pub_ev})
 return {'items':enriched,'total':query.count(),'limit':limit,'offset':offset}
@app.get('/public/search')
def public_search(q:str='',limit:int=Query(20,ge=1,le=200),offset:int=Query(0,ge=0)):
 s=ses();term=f'%{q.strip()}%' if q.strip() else None
 findings=s.query(Finding).filter(Finding.label.like(term)).all() if term else s.query(Finding).order_by(desc(Finding.created_at)).limit(limit).all()
 evidence_rows=s.query(Evidence).filter(Evidence.public==True,Evidence.excerpt.like(term)).all() if term else s.query(Evidence).filter_by(public=True).order_by(desc(Evidence.created_at)).limit(limit).all()
 return {'findings':[out(x) for x in findings[:limit]],'evidence':[out(x) for x in evidence_rows[:limit]],'query':q or None,'counts':{'findings':min(limit,len(findings)),'evidence':min(limit,len(evidence_rows))}}

# ---------- ANALYST STRUCTURED SEARCH ----------
@app.post('/analyst/search')
def analyst_search(b:AnalystSearchIn,x_role:str|None=Header(None)):
 req(x_role,{Role.ANALYST,Role.REVIEWER,Role.PUBLISHER,Role.ADMIN})
 s=ses();results={};q=b.q.strip() if b.q else None;t=f'%{q}%' if q else None
 q_vec=None
 if q and (b.sort_by=='semantic' or b.sort_by=='relevance'):
  try: q_vec=emb.embed(q)
  except Exception: q_vec=None
 sort_semantic=b.sort_by=='semantic' and q_vec is not None
 K=max(b.limit*4,100)
 if 'investigations' in b.collections:
  inv_q=s.query(Investigation)
  if b.statuses:inv_q=inv_q.filter(Investigation.status.in_(b.statuses))
  if t:inv_q=inv_q.filter(or_(Investigation.id.ilike(t),Investigation.submission_id.ilike(t)))
  if b.date_from:inv_q=inv_q.filter(Investigation.created_at>=b.date_from)
  if b.date_to:inv_q=inv_q.filter(Investigation.created_at<=b.date_to)
  total_inv=inv_q.count()
  inv_rows=inv_q.order_by(desc(Investigation.created_at)).offset(b.offset).limit(K if sort_semantic else b.limit).all()
  invs=_semantic_rerank('investigations',q_vec if sort_semantic else None,inv_rows,lambda r:(s.get(Submission,r.submission_id).text if s.get(Submission,r.submission_id) and s.get(Submission,r.submission_id).text else r.id),b.limit) if sort_semantic else [out(x) for x in inv_rows]
  for inv in invs:
   inv['finding_count']=s.query(Finding).filter_by(investigation_id=inv['id']).count()
   inv['evidence_count']=s.query(InvestigationEvidence).filter_by(investigation_id=inv['id']).count()
  results['investigations']={'items':invs[:b.limit],'total':total_inv,'semantic_reranked':sort_semantic}
 if 'evidence' in b.collections:
  ev_q=s.query(Evidence)
  if t:ev_q=ev_q.filter(or_(Evidence.excerpt.ilike(t),Evidence.source_url.ilike(t)))
  if b.review_statuses:ev_q=ev_q.filter(Evidence.review_status.in_(b.review_statuses))
  if b.public is not None:ev_q=ev_q.filter(Evidence.public==b.public)
  if b.relation_types:ev_q=ev_q.filter(Evidence.relation.in_(b.relation_types))
  if b.date_from:ev_q=ev_q.filter(Evidence.created_at>=b.date_from)
  if b.date_to:ev_q=ev_q.filter(Evidence.created_at<=b.date_to)
  total_ev=ev_q.count()
  ev_rows=ev_q.order_by(desc(Evidence.created_at)).offset(b.offset).limit(K if sort_semantic else b.limit).all()
  evs=_semantic_rerank('evidence',q_vec if sort_semantic else None,ev_rows,lambda r:r.excerpt or '',b.limit) if sort_semantic else [out(x) for x in ev_rows]
  for e in evs:
   e['cited_by_count']=s.query(EvidenceRelation).filter(EvidenceRelation.target_evidence_id==e['id']).count()
   e['investigation_count']=s.query(InvestigationEvidence).filter_by(evidence_id=e['id']).count()
  results['evidence']={'items':evs[:b.limit],'total':total_ev,'semantic_reranked':sort_semantic}
 if 'claims' in b.collections:
  cl_q=s.query(Claim)
  if t:cl_q=cl_q.filter(Claim.text.ilike(t))
  if b.uncertainty:cl_q=cl_q.filter(Claim.uncertainty.in_(b.uncertainty))
  total_cl=cl_q.count()
  cl_rows=cl_q.order_by(desc(Claim.created_at)).offset(b.offset).limit(K if sort_semantic else b.limit).all()
  cls=_semantic_rerank('claims',q_vec if sort_semantic else None,cl_rows,lambda r:r.text or '',b.limit) if sort_semantic else [out(x) for x in cl_rows]
  for c in cls:
   c['evidence_count']=s.query(Evidence).filter_by(claim_id=c['id']).count()
  results['claims']={'items':cls[:b.limit],'total':total_cl,'semantic_reranked':sort_semantic}
 if 'documents' in b.collections:
  doc_q=s.query(Document)
  if t:doc_q=doc_q.filter(or_(Document.content.ilike(t),Document.url.ilike(t)))
  if b.source_ids:doc_q=doc_q.filter(Document.source_id.in_(b.source_ids))
  if b.date_from:doc_q=doc_q.filter(Document.collected_at>=b.date_from)
  if b.date_to:doc_q=doc_q.filter(Document.collected_at<=b.date_to)
  total_doc=doc_q.count()
  doc_rows=doc_q.order_by(desc(Document.collected_at)).offset(b.offset).limit(K if sort_semantic else b.limit).all()
  docs=_semantic_rerank('documents',q_vec if sort_semantic else None,doc_rows,lambda r:(r.content or r.url or '')[:1500],b.limit) if sort_semantic else [out(x) for x in doc_rows]
  for d in docs:
   d['claim_count']=s.query(Claim).filter_by(document_id=d['id']).count()
   src=s.get(Source,d['source_id'])
   d['source_name']=src.name if src else None
  results['documents']={'items':docs[:b.limit],'total':total_doc,'semantic_reranked':sort_semantic}
 if 'findings' in b.collections:
  f_q=s.query(Finding)
  if t:f_q=f_q.filter(Finding.label.ilike(t))
  if b.statuses:f_q=f_q.filter(Finding.status.in_(b.statuses))
  total_f=f_q.count()
  f_rows=f_q.order_by(desc(Finding.created_at)).offset(b.offset).limit(K if sort_semantic else b.limit).all()
  fs=_semantic_rerank('findings',q_vec if sort_semantic else None,f_rows,lambda r:r.label or '',b.limit) if sort_semantic else [out(x) for x in f_rows]
  for f in fs:
   inv=s.get(Investigation,f['investigation_id'])
   f['submission_id']=inv.submission_id if inv else None
   versions=s.query(FindingVersion).filter_by(finding_id=f['id']).count()
   f['version_count']=versions
  results['findings']={'items':fs[:b.limit],'total':total_f,'semantic_reranked':sort_semantic}
 facets={
  'statuses':{r[0]:r[1] for r in s.query(Investigation.status,func.count(Investigation.id)).group_by(Investigation.status).all()},
  'review_statuses':{r[0]:r[1] for r in s.query(Evidence.review_status,func.count(Evidence.id)).group_by(Evidence.review_status).all()},
  'uncertainty':{r[0]:r[1] for r in s.query(Claim.uncertainty,func.count(Claim.id)).group_by(Claim.uncertainty).all()},
  'source_statuses':{r[0]:r[1] for r in s.query(Source.status,func.count(Source.id)).group_by(Source.status).all()},
 }
 return {'query':b.q or None,'collections':b.collections,'sort':{'by':b.sort_by,'dir':b.sort_dir,'semantic':sort_semantic,'embedding_provider':emb.name if q_vec else None},'facets':facets,'results':results}

# ---------- INTERNAL SEARCH (LEGACY - PROMOTED TO ANALYST/SEARCH) ----------
@app.post('/internal/search')
def internal_search(b:InternalSearchIn,x_role:str|None=Header(None)):
 req(x_role,{Role.ANALYST,Role.REVIEWER,Role.PUBLISHER,Role.ADMIN})
 s=ses();results={}
 q=b.q.strip() if b.q else None;t=f'%{q}%' if q else None
 docs=s.query(Document)
 if t:docs=docs.filter(or_(Document.content.ilike(t),Document.url.ilike(t)))
 if b.limit:docs=docs.order_by(desc(Document.collected_at)).limit(b.limit)
 results['documents']=[out(x) for x in docs.all()]
 claims_q=s.query(Claim)
 if t:claims_q=claims_q.filter(Claim.text.ilike(t))
 if b.limit:claims_q=claims_q.limit(b.limit)
 results['claims']=[out(x) for x in claims_q.all()]
 ev_q=s.query(Evidence)
 if t:ev_q=ev_q.filter(or_(Evidence.excerpt.ilike(t),Evidence.source_url.ilike(t)))
 if b.limit:ev_q=ev_q.limit(b.limit)
 results['evidence']=[out(x) for x in ev_q.all()]
 inv_q=s.query(Investigation)
 if b.investigation_id:inv_q=inv_q.filter(Investigation.id==b.investigation_id)
 if b.submission_id:inv_q=inv_q.filter(Investigation.submission_id==b.submission_id)
 if b.statuses:inv_q=inv_q.filter(Investigation.status.in_(b.statuses))
 if t:inv_q=inv_q.filter(Investigation.id.ilike(t))
 if b.limit:inv_q=inv_q.order_by(desc(Investigation.created_at)).limit(b.limit)
 investigations=[out(x) for x in inv_q.all()]
 for inv in investigations:
  findings=s.query(Finding).filter_by(investigation_id=inv['id']).all()
  submissions=s.get(Submission,inv['submission_id'])
  inv['findings']=[out(f) for f in findings]
  inv['submission']=out(submissions) if submissions else None
 results['investigations']=investigations
 return results

# ---------- CITIZEN SUBMISSIONS ----------
@app.post('/citizen/submissions')
def submit(b:SubmissionIn):
 if not b.consent or not any([b.text,b.url,b.media_reference]):raise HTTPException(422,'Consent and one input are required')
 s=ses();query=(b.text or b.url or '').strip();matches=[];llm_ctx=Analysis(None,[],'high',[])
 try:
  llm_ctx=llm.analyze(query,b.context or '')
 except Exception:
  llm_ctx=Analysis(None,[],'high',[])
 if query:
  token=query.split()[0]
  matches=[out(x) for x in s.query(Evidence).filter(Evidence.public==True,Evidence.excerpt.ilike(f'%{token}%')).limit(5).all()]
 published_match=bool(matches)
 status='AI_ASSISTED_ANALYSIS' if not published_match else 'PUBLISHED_FINDING'
 parts=[f"Provider ({llm.name}) analysis:{'claim: '+llm_ctx.claim if llm_ctx.claim else 'no claim identified'};uncertainty: {llm_ctx.uncertainty}."]
 if llm_ctx.entities: parts.append(f"Detected entities: {', '.join(llm_ctx.entities[:10])}.")
 if llm_ctx.citations: parts.append("Provider citations noted (non-authoritative): "+', '.join(llm_ctx.citations[:5])+".")
 parts.append('Published, human-reviewed evidence may be relevant. Review the cited sources and context.' if published_match else 'AI-assisted organization only. No human-reviewed finding is available yet.')
 analysis=' '.join(parts)
 o=Submission(**b.model_dump(),status=status,analysis=analysis);s.add(o);s.flush();log(s,'CITIZEN_SUBMITTED',o.id,'citizen');emit(s,'CitizenSubmissionCreated',o.id);emit(s,'SubmissionAIAnalyzeRequested',o.id);s.commit();_embed_text('submissions',o.id,query or o.id)
 return {**out(o),'citations':list(dict.fromkeys(([b.url] if b.url else [])+list(llm_ctx.citations))) or ['citizen-submission'],'uncertainty':llm_ctx.uncertainty,'public_evidence':matches,'llm_provider':llm.name}
@app.get('/citizen/submissions/{sid}')
def get_submission(sid:str):
 s=ses();o=s.get(Submission,sid)
 if not o:raise HTTPException(404,'Submission not found')
 return out(o)
@app.post('/citizen/submissions/{sid}/escalations')
def escalate(sid:str):
 s=ses();o=s.get(Submission,sid)
 if not o:raise HTTPException(404,'Submission not found')
 o.status='UNDER_INVESTIGATION';i=Investigation(submission_id=sid);s.add(i);s.flush();log(s,'CITIZEN_ESCALATED',i.id,'citizen');emit(s,'InvestigationCreated',i.id);s.commit();return out(i)

# ---------- INVESTIGATIONS ----------
@app.get('/investigations')
def investigations(status:str|None=None,x_role:str|None=Header(None)):
 req(x_role,{Role.ANALYST,Role.REVIEWER,Role.PUBLISHER,Role.ADMIN});s=ses();q=s.query(Investigation)
 if status:q=q.filter(Investigation.status==status)
 return [out(x) for x in q.all()]
@app.get('/investigations/{iid}')
def get_investigation(iid:str,x_role:str|None=Header(None)):
 req(x_role,{Role.ANALYST,Role.REVIEWER,Role.PUBLISHER,Role.ADMIN});s=ses();i=s.get(Investigation,iid)
 if not i:raise HTTPException(404,'Investigation not found')
 submission=s.get(Submission,i.submission_id)
 ev_links=s.query(InvestigationEvidence).filter_by(investigation_id=iid).all();evidence=[]
 for L in ev_links:
  e=s.get(Evidence,L.evidence_id);evidence.append({'link':out(L),'evidence':out(e) if e else None})
 findings=s.query(Finding).filter_by(investigation_id=iid).all();findings_with_versions=[]
 for f in findings:
  versions=s.query(FindingVersion).filter_by(finding_id=f.id).order_by(desc(FindingVersion.created_at)).all()
  findings_with_versions.append({**out(f),'versions':[out(v) for v in versions]})
 return {'investigation':out(i),'submission':out(submission) if submission else None,'evidence':evidence,'findings':findings_with_versions}
@app.post('/investigations/{iid}/submit')
def submit_investigation(iid:str,x_role:str|None=Header(None)):
 req(x_role,{Role.ANALYST});s=ses();i=s.get(Investigation,iid)
 if not i:raise HTTPException(404,'Investigation not found')
 i.status='ANALYST_SUBMISSION';log(s,'INVESTIGATION_SUBMITTED',iid,'analyst');emit(s,'InvestigationSubmitted',iid);s.commit();return out(i)
@app.post('/investigations/{iid}/evidence')
def link_evidence(iid:str,b:LinkEvidenceIn,x_role:str|None=Header(None)):
 req(x_role,{Role.ANALYST});s=ses();i=s.get(Investigation,iid);e=s.get(Evidence,b.evidence_id)
 if not i or not e:raise HTTPException(404,'Investigation or evidence not found')
 link=InvestigationEvidence(investigation_id=iid,evidence_id=e.id,rationale=b.rationale);s.add(link);i.status='EVIDENCE_COLLECTED';log(s,'EVIDENCE_LINKED',link.id,'analyst');s.commit();return out(link)

# ---------- ROOM OVERVIEW ----------
@app.get('/room/overview')
def room_overview(x_role:str|None=Header(None)):
 req(x_role,{Role.ANALYST,Role.REVIEWER,Role.PUBLISHER,Role.ADMIN});s=ses()
 public_ev=s.query(Evidence).filter_by(public=True).count()
 unreviewed=s.query(Evidence).filter_by(public=False).count()
 published_findings=s.query(Finding).count()
 submissions=s.query(Submission).count()
 escalated=s.query(Investigation).filter(Investigation.submission_id.is_not(None)).count()
 evidence_rels=s.query(EvidenceRelation).count()
 drafted=s.query(Source).filter(Source.status=='DRAFT').count()
 disabled=s.query(Source).filter(Source.status=='DISABLED').count()
 return {
  'active_investigations':s.query(Investigation).filter(Investigation.status!='PUBLISHED').count(),
  'pending_reviews':s.query(Investigation).filter(Investigation.status=='ANALYST_SUBMISSION').count(),
  'sources':{'total':s.query(Source).count(),'draft':drafted,'disabled':disabled,'approved':s.query(Source).filter(Source.status=='APPROVED').count()},
  'documents':s.query(Document).count(),
  'claims':s.query(Claim).count(),
  'citizen_escalations':escalated,
  'public_evidence':public_ev,
  'internal_evidence_unreviewed':unreviewed,
  'published_findings':published_findings,
  'citizen_submissions':submissions,
  'evidence_relations':evidence_rels,
  'workflow':{'submissions_to_escalations':round(escalated/submissions,2) if submissions else 0.0},
 }

# ---------- REVIEWS ----------
@app.post('/reviews/{iid}')
def review(iid:str,b:ReviewIn,x_role:str|None=Header(None)):
 req(x_role,{Role.REVIEWER});s=ses();i=s.get(Investigation,iid)
 if not i or i.status!='ANALYST_SUBMISSION':raise HTTPException(409,'Not ready for review')
 i.status='APPROVED' if b.decision=='APPROVE' else 'UNDER_INVESTIGATION';log(s,'REVIEW_'+b.decision,iid,'reviewer');s.commit();return out(i)

# ---------- FINDINGS + PUBLICATION RELEASE + VERSIONING ----------
@app.post('/findings/{iid}/publish')
def publish(iid:str,x_role:str|None=Header(None)):
 req(x_role,{Role.PUBLISHER});s=ses();i=s.get(Investigation,iid)
 if not i or i.status!='APPROVED':raise HTTPException(409,'Only approved investigations can publish')
 i.status='PUBLISHED';f=Finding(investigation_id=iid,label='Human-reviewed finding');s.add(f);s.flush()
 v=FindingVersion(finding_id=f.id,version=1,label=f.label,status=f.status,actor='publisher',note='Initial publication')
 s.add(v);log(s,'FINDING_PUBLISHED',f.id,'publisher');emit(s,'FindingPublished',f.id);s.commit()
 return {'finding':out(f),'version':out(v)}
@app.post('/findings/{fid}/update')
def update_finding(fid:str,b:FindingUpdateIn,x_role:str|None=Header(None)):
 req(x_role,{Role.PUBLISHER,Role.ADMIN});s=ses();f=s.get(Finding,fid)
 if not f:raise HTTPException(404,'Finding not found')
 cur=s.query(func.max(FindingVersion.version)).filter(FindingVersion.finding_id==fid).scalar() or 0
 v=FindingVersion(finding_id=fid,version=cur+1,label=b.label,status=b.status,actor='publisher',note=b.note or 'Finding updated')
 f.label=b.label;f.status=b.status
 s.add(v);log(s,'FINDING_UPDATED',fid,'publisher');emit(s,'FindingUpdated',fid);s.commit()
 return {'finding':out(f),'version':out(v)}
@app.post('/findings/{fid}/unpublish')
def unpublish_finding(fid:str,b:FindingUnpublishIn,x_role:str|None=Header(None)):
 req(x_role,{Role.PUBLISHER});s=ses();f=s.get(Finding,fid)
 if not f:raise HTTPException(404,'Finding not found')
 inv=s.get(Investigation,f.investigation_id)
 cur=s.query(func.max(FindingVersion.version)).filter(FindingVersion.finding_id==fid).scalar() or 0
 v=FindingVersion(finding_id=fid,version=cur+1,label=f.label,status='UNPUBLISHED',actor='publisher',note=b.note)
 f.status='UNPUBLISHED'
 if inv:inv.status='UNDER_INVESTIGATION'
 s.add(v);log(s,'FINDING_UNPUBLISHED',fid,'publisher');emit(s,'FindingUnpublished',fid);s.commit()
 return {'finding':out(f),'version':out(v),'investigation_status':inv.status if inv else None}
@app.get('/findings')
def findings(status:str|None=None,x_role:str|None=Header(None)):
 s=ses();q=s.query(Finding);include_all=False
 try:r=Role(x_role or 'CITIZEN')
 except ValueError:raise HTTPException(403,'Permission denied')
 if r in (Role.ANALYST,Role.REVIEWER,Role.PUBLISHER,Role.ADMIN):include_all=True
 if not include_all:q=q.filter(Finding.status=='PUBLISHED')
 if status:q=q.filter(Finding.status==status)
 return [out(x) for x in q.order_by(desc(Finding.created_at)).all()]
@app.get('/findings/{fid}')
def get_finding(fid:str,x_role:str|None=Header(None)):
 s=ses();f=s.get(Finding,fid)
 if not f:raise HTTPException(404,'Finding not found')
 include_detail=True
 try:r=Role(x_role or 'CITIZEN')
 except ValueError:raise HTTPException(403,'Permission denied')
 if f.status!='PUBLISHED' and r not in (Role.ANALYST,Role.REVIEWER,Role.PUBLISHER,Role.ADMIN):include_detail=False
 if f.status!='PUBLISHED' and not include_detail:raise HTTPException(403,'Finding not public')
 inv=s.get(Investigation,f.investigation_id)
 ev_links=s.query(InvestigationEvidence).filter_by(investigation_id=inv.id).all() if inv else []
 evidence=[out(s.get(Evidence,L.evidence_id)) for L in ev_links if s.get(Evidence,L.evidence_id)]
 versions=s.query(FindingVersion).filter_by(finding_id=fid).order_by(desc(FindingVersion.created_at)).all()
 return {'finding':out(f),'investigation':out(inv) if inv else None,'evidence':evidence,'versions':[out(v) for v in versions]}

# ---------- AUDIT ----------
@app.get('/audit')
def audit(action:str|None=None,actor:str|None=None,entity:str|None=None,limit:int=Query(200,ge=1,le=2000),x_role:str|None=Header(None)):
 req(x_role,{Role.ADMIN});s=ses();q=s.query(Audit)
 if action:q=q.filter(Audit.action==action)
 if actor:q=q.filter(Audit.actor==actor)
 if entity:q=q.filter(Audit.entity.ilike(f'%{entity}%'))
 return [out(x) for x in q.order_by(desc(Audit.created_at)).limit(limit).all()]

# ---------- OPERATIONS: OUTBOX/WORKER/SCHEDULER ----------
@app.post('/operations/outbox/dispatch')
def dispatch(x_role:str|None=Header(None)):
 req(x_role,{Role.ADMIN});return {'dispatched':dispatch_pending()}
@app.get('/operations/outbox')
def outbox(status:str|None=None,event_type:str|None=None,limit:int=Query(200,ge=1,le=2000),x_role:str|None=Header(None)):
 req(x_role,{Role.ADMIN});s=ses();q=s.query(OutboxEvent)
 if status:q=q.filter(OutboxEvent.status==status)
 if event_type:q=q.filter(OutboxEvent.event_type==event_type)
 return [out(x) for x in q.order_by(desc(OutboxEvent.created_at)).limit(limit).all()]
@app.get('/operations/outbox/{eid}')
def outbox_event(eid:str,x_role:str|None=Header(None)):
 req(x_role,{Role.ADMIN});ev=worker.get_event(eid)
 if not ev:raise HTTPException(404,'Outbox event not found')
 return ev
@app.post('/operations/outbox/{eid}/cancel')
def outbox_cancel(eid:str,x_role:str|None=Header(None)):
 req(x_role,{Role.ADMIN});ok=worker.cancel_event(eid)
 if not ok:raise HTTPException(409,'Cannot cancel dispatched or missing event')
 return {'cancelled':True,'id':eid}
@app.get('/operations/outbox-dlq')
def outbox_dlq(limit:int=Query(100,ge=1,le=1000),x_role:str|None=Header(None)):
 req(x_role,{Role.ADMIN});return worker.list_dead_events(limit=limit)
@app.post('/operations/outbox-dlq/retry')
def outbox_dlq_retry(x_role:str|None=Header(None)):
 req(x_role,{Role.ADMIN});return {'retried':worker.retry_all_dead()}
@app.post('/operations/outbox/{eid}/retry')
def outbox_retry_one(eid:str,x_role:str|None=Header(None)):
 req(x_role,{Role.ADMIN});ok=worker.retry_dead_event(eid)
 if not ok:raise HTTPException(404,'Only DEAD events can be retried')
 return {'retried':True,'id':eid}
@app.get('/operations/worker')
def op_worker(x_role:str|None=Header(None)):
 req(x_role,{Role.ADMIN});return worker.worker_status()
@app.post('/operations/worker/tick')
def op_worker_tick(x_role:str|None=Header(None)):
 req(x_role,{Role.ADMIN});worker.publish_pending_outbox_to_stream();return {'processed':worker.consume_once()}
@app.get('/operations/scheduler')
def op_scheduler(x_role:str|None=Header(None)):
 req(x_role,{Role.ADMIN});return scheduler.scheduler_status()
@app.post('/operations/scheduler/tick')
def op_scheduler_tick(x_role:str|None=Header(None)):
 req(x_role,{Role.ADMIN});ran=scheduler.tick_sources();return {'sources_triggered':ran}
