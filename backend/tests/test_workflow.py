from fastapi.testclient import TestClient
from app.main import app
from app import auth
c=TestClient(app)
def test_citizen_to_human_publication():
 s=c.post('/citizen/submissions',json={'text':'Synthetic test claim','consent':True}).json()
 i=c.post(f"/citizen/submissions/{s['id']}/escalations").json()
 assert c.post(f"/investigations/{i['id']}/submit",headers={'x-role':'ANALYST'}).status_code==200
 assert c.post(f"/reviews/{i['id']}",headers={'x-role':'REVIEWER'},json={'decision':'APPROVE','comments':'Evidence reviewed'}).status_code==200
 assert c.post(f"/findings/{i['id']}/publish",headers={'x-role':'PUBLISHER'}).status_code==200
def test_ai_cannot_publish():
 assert c.post('/findings/nope/publish',headers={'x-role':'AI_WORKER'}).status_code==403
def test_approved_fixture_source_creates_then_dedupes_document():
 source=c.post('/sources',headers={'x-role':'ADMIN'},json={'name':'Synthetic approved source','url':'https://example.test','interval_minutes':60}).json()
 c.post(f"/sources/{source['id']}/status",headers={'x-role':'ADMIN'},json={'status':'APPROVED'})
 url=f"/sources/{source['id']}/collect-fixture?content=Synthetic%20election%20claim%20{source['id']}"
 assert c.post(url,headers={'x-role':'ADMIN'}).json()['created'] is True
 assert c.post(url,headers={'x-role':'ADMIN'}).json()['created'] is False
 assert len(c.get('/claims',headers={'x-role':'ANALYST'}).json()) >= 1
def test_internal_evidence_requires_role_and_links_to_case():
 s=c.post('/citizen/submissions',json={'text':'Synthetic evidence claim','consent':True}).json(); i=c.post(f"/citizen/submissions/{s['id']}/escalations").json()
 e=c.post('/evidence',headers={'x-role':'ANALYST'},json={'source_url':'https://example.test/evidence','excerpt':'Synthetic evidence excerpt'}).json()
 assert c.get(f"/evidence/{e['id']}").status_code==403
 assert c.post(f"/investigations/{i['id']}/evidence",headers={'x-role':'ANALYST'},json={'evidence_id':e['id'],'rationale':'Relevant context'}).status_code==200
def test_outbox_records_and_dispatches_workflow_events():
 c.post('/citizen/submissions',json={'text':'Synthetic outbox claim','consent':True})
 events=c.get('/operations/outbox',headers={'x-role':'ADMIN'}).json(); assert any(x['event_type']=='CitizenSubmissionCreated' for x in events)
 assert c.post('/operations/outbox/dispatch',headers={'x-role':'ADMIN'}).json()['dispatched'] >= 1
def test_public_projection_never_returns_internal_evidence_until_published():
 e=c.post('/evidence',headers={'x-role':'ANALYST'},json={'source_url':'https://example.test/private','excerpt':'Synthetic restricted evidence'}).json()
 before=c.get('/public/evidence').json()
 assert 'items' in before and before['items'] == [] and before['total'] == 0
 assert c.post(f"/evidence/{e['id']}/public",headers={'x-role':'PUBLISHER'},json={'public':True}).status_code==200
 after=c.get('/public/evidence').json()
 assert after['total'] == 1 and len(after['items']) == 1
def test_citizen_submission_can_only_match_public_evidence():
 e=c.post('/evidence',headers={'x-role':'ANALYST'},json={'source_url':'https://example.test/public','excerpt':'Verified synthetic source context'}).json()
 before=c.post('/citizen/submissions',json={'text':'Verified report','consent':True}).json(); assert before['status']=='AI_ASSISTED_ANALYSIS'
 c.post(f"/evidence/{e['id']}/public",headers={'x-role':'PUBLISHER'},json={'public':True})
 after=c.post('/citizen/submissions',json={'text':'Verified report','consent':True}).json(); assert after['status']=='PUBLISHED_FINDING'
def test_health_reports_worker_scheduler_and_inventory():
 h=c.get('/health').json()
 assert h['status']=='ok'
 assert 'worker' in h
 assert 'scheduler' in h
 assert 'inventory' in h
 assert h['inventory']['sources'] >= 0
def test_worker_status_requires_admin():
 assert c.get('/operations/worker').status_code==403
 w=c.get('/operations/worker',headers={'x-role':'ADMIN'}).json()
 assert 'transport' in w and 'pending' in w and 'dead' in w
def test_worker_tick_dispatches_pending():
 c.post('/citizen/submissions',json={'text':'Tick-test submission','consent':True})
 r=c.post('/operations/worker/tick',headers={'x-role':'ADMIN'}).json()
 assert 'processed' in r
def test_scheduler_status_requires_admin():
 assert c.get('/operations/scheduler').status_code==403
 s=c.get('/operations/scheduler',headers={'x-role':'ADMIN'}).json()
 assert 'mode' in s and 'sources' in s and 'stats' in s
def test_scheduler_tick_and_run_once():
 src=c.post('/sources',headers={'x-role':'ADMIN'},json={'name':'Tick source','url':'https://example.test/tick','interval_minutes':5}).json()
 c.post(f"/sources/{src['id']}/status",headers={'x-role':'ADMIN'},json={'status':'APPROVED'})
 r=c.post('/operations/scheduler/tick',headers={'x-role':'ADMIN'}).json()
 assert 'sources_triggered' in r
 assert c.post(f"/sources/{src['id']}/run-once",headers={'x-role':'ANALYST'}).status_code==200
 assert c.post('/sources/nope/run-once',headers={'x-role':'ANALYST'}).status_code==404
def test_document_evidence_projection_links_claims_and_evidence():
 src=c.post('/sources',headers={'x-role':'ADMIN'},json={'name':'Doc-evidence src','url':'https://example.test/doc','interval_minutes':60}).json()
 c.post(f"/sources/{src['id']}/status",headers={'x-role':'ADMIN'},json={'status':'APPROVED'})
 coll=c.post(f"/sources/{src['id']}/collect-fixture?content=Document%20with%20claim%20for%20evidence",headers={'x-role':'ADMIN'}).json()
 did=coll['document']['id']
 assert c.get(f"/documents/{did}/evidence",headers={'x-role':'ANALYST'}).status_code==200
 proj=c.get(f"/documents/{did}/evidence",headers={'x-role':'ANALYST'}).json()
 assert 'document' in proj and 'claims' in proj and 'evidence' in proj
 assert c.get('/documents/missing/evidence',headers={'x-role':'ANALYST'}).status_code==404
 assert c.get(f"/documents/{did}/evidence").status_code==403

def test_job_lifecycle_dlq_retry_cancel_endpoints():
 sub=c.post('/citizen/submissions',json={'text':'DLQ workflow submission','consent':True}).json()
 events=c.get('/operations/outbox',headers={'x-role':'ADMIN'},params={'event_type':'CitizenSubmissionCreated'}).json()
 eid=events[0]['id']
 assert c.get(f"/operations/outbox/{eid}",headers={'x-role':'ADMIN'}).status_code==200
 assert c.get('/operations/outbox-dlq',headers={'x-role':'ADMIN'}).status_code==200
 assert c.post(f"/operations/outbox/{eid}/cancel",headers={'x-role':'ADMIN'}).status_code==200
 assert c.post(f"/operations/outbox/{eid}/retry",headers={'x-role':'ADMIN'}).status_code==404
 assert c.post('/operations/outbox-dlq/retry',headers={'x-role':'ADMIN'}).json()['retried'] >= 0
 assert c.get('/operations/outbox/nope',headers={'x-role':'ADMIN'}).status_code==404
 assert c.get('/operations/outbox').status_code==403

def test_public_evidence_projection_has_pagination_sort_and_findings():
 ev=c.post('/evidence',headers={'x-role':'ANALYST'},json={'source_url':'https://example.test/pubproj','excerpt':'Projected public evidence context'}).json()
 c.post(f"/evidence/{ev['id']}/public",headers={'x-role':'PUBLISHER'},json={'public':True})
 resp=c.get('/public/evidence',params={'q':'Projected','limit':5,'sort':'newest'}).json()
 assert 'items' in resp and 'total' in resp and resp['total'] >= 1
 first=resp['items'][0]
 assert 'findings' in first
 assert c.get('/public/evidence',params={'sort':'oldest'}).status_code==200

def test_public_findings_and_public_search_rewrite():
 s=c.post('/citizen/submissions',json={'text':'Finding-test claim','consent':True}).json()
 i=c.post(f"/citizen/submissions/{s['id']}/escalations").json()
 c.post(f"/investigations/{i['id']}/submit",headers={'x-role':'ANALYST'})
 c.post(f"/reviews/{i['id']}",headers={'x-role':'REVIEWER'},json={'decision':'APPROVE','comments':'ok'})
 c.post(f"/findings/{i['id']}/publish",headers={'x-role':'PUBLISHER'})
 fr=c.get('/public/findings',params={'limit':10}).json()
 assert fr['total'] >= 1 and len(fr['items']) >= 1
 sr=c.get('/public/search',params={'q':'finding','limit':5}).json()
 assert sr['query']=='finding' and 'counts' in sr

def test_document_chain_endpoint_and_internal_search():
 src=c.post('/sources',headers={'x-role':'ADMIN'},json={'name':'Chain src','url':'https://example.test/chain','interval_minutes':60}).json()
 c.post(f"/sources/{src['id']}/status",headers={'x-role':'ADMIN'},json={'status':'APPROVED'})
 coll=c.post(f"/sources/{src['id']}/collect-fixture?content=Full%20chain%20document%20with%20claims",headers={'x-role':'ADMIN'}).json()
 did=coll['document']['id']
 chain=c.get(f"/documents/{did}/chain",headers={'x-role':'ANALYST'}).json()
 assert 'source' in chain and 'document' in chain and 'claims' in chain and 'evidence_links' in chain and 'investigations' in chain
 assert c.get(f"/documents/{did}/chain").status_code==403
 isr=c.post('/internal/search',headers={'x-role':'ANALYST'},json={'q':'chain','limit':5}).json()
 assert 'documents' in isr and 'claims' in isr and 'evidence' in isr and 'investigations' in isr
 assert c.post('/internal/search',json={'q':'x'}).status_code==403
 inv_filter=c.post('/internal/search',headers={'x-role':'ANALYST'},json={'statuses':['PUBLISHED'],'limit':10}).json()
 assert all(i.get('status')=='PUBLISHED' for i in inv_filter['investigations'] if i)

def test_investigation_detail_and_finding_detail_endpoints():
 s=c.post('/citizen/submissions',json={'text':'Detail-view claim','consent':True}).json()
 i=c.post(f"/citizen/submissions/{s['id']}/escalations").json()
 ev=c.post('/evidence',headers={'x-role':'ANALYST'},json={'source_url':'https://example.test/det','excerpt':'Detail view evidence'}).json()
 c.post(f"/investigations/{i['id']}/evidence",headers={'x-role':'ANALYST'},json={'evidence_id':ev['id'],'rationale':'Related for test'})
 c.post(f"/investigations/{i['id']}/submit",headers={'x-role':'ANALYST'})
 c.post(f"/reviews/{i['id']}",headers={'x-role':'REVIEWER'},json={'decision':'APPROVE','comments':'done'})
 pr=c.post(f"/findings/{i['id']}/publish",headers={'x-role':'PUBLISHER'}).json()
 f=pr['finding']
 inv_view=c.get(f"/investigations/{i['id']}",headers={'x-role':'ANALYST'}).json()
 assert inv_view['investigation']['id']==i['id'] and 'submission' in inv_view and 'evidence' in inv_view and 'findings' in inv_view
 f_view=c.get(f"/findings/{f['id']}").json()
 assert f_view['finding']['id']==f['id'] and 'investigation' in f_view and 'evidence' in f_view
 ev_inv=c.get(f"/evidence/{ev['id']}/investigations",headers={'x-role':'ANALYST'}).json()
 assert len(ev_inv)>=1
 assert c.get(f"/investigations/{i['id']}").status_code==403

def test_room_overview_and_list_endpoint_filters():
 overview=c.get('/room/overview',headers={'x-role':'ANALYST'}).json()
 assert 'public_evidence' in overview and 'internal_evidence_unreviewed' in overview and 'published_findings' in overview and 'citizen_submissions' in overview and 'workflow' in overview
 assert 'sources' in overview and isinstance(overview['sources'],dict) and 'draft' in overview['sources'] and 'approved' in overview['sources']
 assert 'evidence_relations' in overview
 invs=c.get('/investigations',headers={'x-role':'ANALYST'},params={'status':'PUBLISHED'}).json()
 assert all(i['status']=='PUBLISHED' for i in invs)
 aud=c.get('/audit',headers={'x-role':'ADMIN'},params={'action':'SOURCE_CREATED'}).json()
 assert all(a['action']=='SOURCE_CREATED' for a in aud)
 evs=c.get('/evidence',headers={'x-role':'ANALYST'},params={'public':'true'}).json()
 assert all(e['public'] is True for e in evs)

def test_analyst_structured_search_rbac_and_facets():
 assert c.post('/analyst/search',json={'q':'x','limit':10}).status_code==403
 res=c.post('/analyst/search',headers={'x-role':'ANALYST'},json={'q':'','limit':5,'collections':['investigations','evidence','claims','documents','findings']}).json()
 assert 'query' in res and 'collections' in res and 'facets' in res and 'results' in res
 assert 'statuses' in res['facets'] and 'review_statuses' in res['facets'] and 'uncertainty' in res['facets'] and 'source_statuses' in res['facets']
 for col in ('investigations','evidence','claims','documents','findings'):
  assert col in res['results']
  assert 'items' in res['results'][col] and 'total' in res['results'][col]
 status_filtered=c.post('/analyst/search',headers={'x-role':'ANALYST'},json={'statuses':['PUBLISHED'],'collections':['investigations'],'limit':50}).json()
 for inv in status_filtered['results']['investigations']['items']:
  assert inv['status']=='PUBLISHED'

def test_evidence_citation_graph_and_relations():
 e1=c.post('/evidence',headers={'x-role':'ANALYST'},json={'source_url':'https://example.test/g1','excerpt':'Graph evidence one'}).json()
 e2=c.post('/evidence',headers={'x-role':'ANALYST'},json={'source_url':'https://example.test/g2','excerpt':'Graph evidence two'}).json()
 rel=c.post(f"/evidence/{e1['id']}/relations",headers={'x-role':'ANALYST'},json={'target_evidence_id':e2['id'],'relation_type':'CORROBORATES','rationale':'Test corroboration'}).json()
 assert rel['relation_type']=='CORROBORATES'
 dup=c.post(f"/evidence/{e1['id']}/relations",headers={'x-role':'ANALYST'},json={'target_evidence_id':e2['id'],'relation_type':'CORROBORATES'})
 assert dup.status_code==409
 view=c.get(f"/evidence/{e1['id']}/relations",headers={'x-role':'ANALYST'}).json()
 assert 'relations' in view and 'citation_counts' in view
 assert view['citation_counts']['cites']>=1 or view['citation_counts']['cited_by']>=1
 self_ref=c.post(f"/evidence/{e1['id']}/relations",headers={'x-role':'ANALYST'},json={'target_evidence_id':e1['id'],'relation_type':'CONTRADICTS'})
 assert self_ref.status_code==422
 graph=c.get('/graph/evidence',headers={'x-role':'ANALYST'}).json()
 assert 'nodes' in graph and 'edges' in graph and graph['edge_count']>=1

def test_publication_release_lifecycle_update_unpublish_versions():
 s=c.post('/citizen/submissions',json={'text':'Finding lifecycle claim','consent':True}).json()
 i=c.post(f"/citizen/submissions/{s['id']}/escalations").json()
 c.post(f"/investigations/{i['id']}/submit",headers={'x-role':'ANALYST'})
 c.post(f"/reviews/{i['id']}",headers={'x-role':'REVIEWER'},json={'decision':'APPROVE','comments':'good'})
 pub=c.post(f"/findings/{i['id']}/publish",headers={'x-role':'PUBLISHER'}).json()
 assert 'finding' in pub and 'version' in pub and pub['version']['version']==1
 upd=c.post(f"/findings/{pub['finding']['id']}/update",headers={'x-role':'PUBLISHER'},json={'label':'Updated finding label','status':'PUBLISHED','note':'Corrected label'}).json()
 assert upd['version']['version']==2 and upd['finding']['label']=='Updated finding label'
 unpub=c.post(f"/findings/{pub['finding']['id']}/unpublish",headers={'x-role':'PUBLISHER'},json={'note':'Retracted pending new analysis'}).json()
 assert unpub['finding']['status']=='UNPUBLISHED' and unpub['version']['version']==3
 fid=pub['finding']['id']
 detail=c.get(f"/findings/{fid}",headers={'x-role':'ANALYST'}).json()
 assert len(detail['versions'])>=3
 citizen_view=c.get(f"/findings/{fid}")
 assert citizen_view.status_code==403

def test_source_governance_approval_disable_and_ingestion_gating():
 draft=c.post('/sources',headers={'x-role':'ADMIN'},json={'name':'Governed source','url':'https://example.test/gov','interval_minutes':15}).json()
 assert draft['status']=='DRAFT'
 detail=c.get(f"/sources/{draft['id']}",headers={'x-role':'ANALYST'}).json()
 assert 'source' in detail and 'recent_documents' in detail and 'audit' in detail
 blocked=c.post(f"/sources/{draft['id']}/collect-fixture?content=should%20be%20blocked",headers={'x-role':'ADMIN'})
 assert blocked.status_code==409
 approved=c.post(f"/sources/{draft['id']}/status",headers={'x-role':'ADMIN'},json={'status':'APPROVED'}).json()
 assert approved['status']=='APPROVED'
 assert c.get('/sources',params={'status':'DRAFT'},headers={'x-role':'ANALYST'}).status_code==200
 fixture=c.post(f"/sources/{draft['id']}/collect-fixture?content=ingestion%20ok%20now",headers={'x-role':'ADMIN'})
 assert fixture.status_code==200
 disabled=c.post(f"/sources/{draft['id']}/status",headers={'x-role':'ADMIN'},json={'status':'DISABLED'}).json()
 assert disabled['status']=='DISABLED'
 blocked2=c.post(f"/sources/{draft['id']}/collect-fixture?content=still%20blocked",headers={'x-role':'ADMIN'})
 assert blocked2.status_code==409
 assert c.post('/sources',headers={'x-role':'ANALYST'},json={'name':'x','url':'https://y'}).status_code==403

def test_public_evidence_cited_sort_and_findings_version_visibility():
 ev=c.post('/evidence',headers={'x-role':'ANALYST'},json={'source_url':'https://example.test/pubcite','excerpt':'Sort public cited evidence'}).json()
 c.post(f"/evidence/{ev['id']}/public",headers={'x-role':'PUBLISHER'},json={'public':True,'release_note':'Test release'})
 s=c.post('/citizen/submissions',json={'text':'Cited finding claim','consent':True}).json()
 i=c.post(f"/citizen/submissions/{s['id']}/escalations").json()
 c.post(f"/investigations/{i['id']}/evidence",headers={'x-role':'ANALYST'},json={'evidence_id':ev['id'],'rationale':'Cited test'})
 c.post(f"/investigations/{i['id']}/submit",headers={'x-role':'ANALYST'})
 c.post(f"/reviews/{i['id']}",headers={'x-role':'REVIEWER'},json={'decision':'APPROVE','comments':'cited ok'})
 pub=c.post(f"/findings/{i['id']}/publish",headers={'x-role':'PUBLISHER'}).json()
 r=c.get('/public/evidence',params={'sort':'cited','limit':10}).json()
 first_item=r['items'][0]
 assert 'cited_by_count' in first_item and 'findings' in first_item
 cited_view=c.get(f"/evidence/{ev['id']}/relations",headers={'x-role':'PUBLISHER'}).json()
 assert 'citation_counts' in cited_view
 pf=c.get('/public/findings',params={'limit':10}).json()
 assert pf['total']>=1 and 'evidence_count' in pf['items'][0]

def test_verified_bearer_role_works_when_dev_header_is_disabled():
 old_secret,old_xrole=auth.JWT_SECRET,auth.X_ROLE_ENABLED
 try:
  auth.JWT_SECRET='test-production-secret';auth.X_ROLE_ENABLED=False
  token=auth.example_issue_token('admin@example.test',auth.Role.ADMIN,auth.JWT_SECRET)
  r=c.post('/sources',headers={'Authorization':f'Bearer {token}'},json={'name':'JWT source','url':'https://example.test/jwt','interval_minutes':15})
  assert r.status_code==200
  denied=c.post('/sources',headers={'x-role':'ADMIN'},json={'name':'Spoofed source','url':'https://example.test/spoof','interval_minutes':15})
  assert denied.status_code==403
 finally:
  auth.JWT_SECRET,auth.X_ROLE_ENABLED=old_secret,old_xrole

def test_auth0_rs256_access_token_role_is_verified_with_issuer_and_audience():
 """Auth0 tokens must be RS256, correctly scoped, and carry the roles claim."""
 from datetime import datetime, timedelta, timezone
 from cryptography.hazmat.primitives.asymmetric import rsa
 import jwt

 class SigningKey:
  def __init__(self,key): self.key=key
 class JWKS:
  def __init__(self,key): self.key=key
  def get_signing_key_from_jwt(self,token): return SigningKey(self.key)

 old=(auth.AUTH0_ENABLED,auth.AUTH0_AUDIENCE,auth.AUTH0_ISSUER,auth.AUTH0_ROLES_CLAIM,auth.X_ROLE_ENABLED,auth._AUTH0_JWK_CLIENT)
 try:
  private=rsa.generate_private_key(public_exponent=65537,key_size=2048)
  auth.AUTH0_ENABLED=True
  auth.AUTH0_AUDIENCE='https://api.aipeiisr.local'
  auth.AUTH0_ISSUER='https://dev-jfiniqd64sglft55.us.auth0.com/'
  auth.AUTH0_ROLES_CLAIM='https://api.aipeiisr.local/roles'
  auth.X_ROLE_ENABLED=False
  auth._AUTH0_JWK_CLIENT=JWKS(private.public_key())
  now=datetime.now(timezone.utc)
  token=jwt.encode({
   'sub':'auth0|test-admin','iss':auth.AUTH0_ISSUER,'aud':auth.AUTH0_AUDIENCE,
   'iat':now,'exp':now+timedelta(minutes=5),auth.AUTH0_ROLES_CLAIM:['admin']
  },private,algorithm='RS256',headers={'kid':'test-key'})
  created=c.post('/sources',headers={'Authorization':f'Bearer {token}'},json={'name':'Auth0 source','url':'https://example.test/auth0','interval_minutes':15})
  assert created.status_code==200
  wrong_audience=jwt.encode({
   'sub':'auth0|wrong-aud','iss':auth.AUTH0_ISSUER,'aud':'https://other.example','iat':now,'exp':now+timedelta(minutes=5),auth.AUTH0_ROLES_CLAIM:['admin']
  },private,algorithm='RS256',headers={'kid':'test-key'})
  denied=c.post('/sources',headers={'Authorization':f'Bearer {wrong_audience}'},json={'name':'Denied Auth0 source','url':'https://example.test/auth0-denied','interval_minutes':15})
  assert denied.status_code==403
 finally:
  auth.AUTH0_ENABLED,auth.AUTH0_AUDIENCE,auth.AUTH0_ISSUER,auth.AUTH0_ROLES_CLAIM,auth.X_ROLE_ENABLED,auth._AUTH0_JWK_CLIENT=old
