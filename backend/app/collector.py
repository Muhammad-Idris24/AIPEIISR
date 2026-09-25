"""Approved-source collection contract. Live network collection is intentionally disabled by default."""
from hashlib import sha256
from .db import Session,Source,Document,Claim,Audit
from .providers import MockLLMProvider

def collect_synthetic(source_id:str, content:str, url:str='synthetic://fixture'):
    """Development-only fixture path exercising normalize/dedupe/analyze provenance."""
    s=Session(); source=s.get(Source,source_id)
    if not source: raise ValueError('Source not found')
    h=sha256(content.encode()).hexdigest()
    existing=s.query(Document).filter_by(content_hash=h).first()
    if existing:return existing,False
    d=Document(source_id=source_id,url=url,content=content,content_hash=h);s.add(d);s.flush()
    analysis=MockLLMProvider().analyze(content,d.id)
    if analysis.claim:s.add(Claim(document_id=d.id,text=analysis.claim,uncertainty=analysis.uncertainty))
    s.add(Audit(action='DOCUMENT_CREATED',entity=d.id,actor='collector'));s.commit();return d,True
