import os
import math
from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import create_engine, String, Text, DateTime, Boolean, Integer, ForeignKey, UniqueConstraint, LargeBinary, JSON, Index, Column
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

URL=os.getenv("DATABASE_URL","sqlite:///./aipeiisr.db")
IS_SQLITE=URL.startswith("sqlite")
engine=create_engine(URL,connect_args={"check_same_thread":False} if IS_SQLITE else {})
Session=sessionmaker(bind=engine,autoflush=False,autocommit=False,expire_on_commit=False)
class Base(DeclarativeBase): pass
def uid(): return str(uuid4())
def now(): return datetime.now(timezone.utc)

def cosine_similarity(a:list[float], b:list[float]) -> float:
    if not a or not b or len(a)!=len(b): return 0.0
    dot=ab=bb=0.0
    for x,y in zip(a,b):
        dot+=x*y; ab+=x*x; bb+=y*y
    denom=math.sqrt(ab)*math.sqrt(bb)
    return dot/denom if denom>0 else 0.0
class Source(Base):
 __tablename__='sources'; id:Mapped[str]=mapped_column(String,primary_key=True,default=uid); name:Mapped[str]=mapped_column(String); url:Mapped[str]=mapped_column(String); collector_type:Mapped[str]=mapped_column(String); interval_minutes:Mapped[int]=mapped_column(); status:Mapped[str]=mapped_column(String,default='APPROVED'); last_success:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True); created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
class Submission(Base):
 __tablename__='citizen_submissions'; id:Mapped[str]=mapped_column(String,primary_key=True,default=uid); text:Mapped[str|None]=mapped_column(Text,nullable=True); url:Mapped[str|None]=mapped_column(String,nullable=True); media_reference:Mapped[str|None]=mapped_column(String,nullable=True); context:Mapped[str|None]=mapped_column(Text,nullable=True); consent:Mapped[bool]=mapped_column(Boolean); status:Mapped[str]=mapped_column(String,default='AI_ASSISTED_ANALYSIS'); analysis:Mapped[str]=mapped_column(Text); created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
class Investigation(Base):
 __tablename__='investigations'; id:Mapped[str]=mapped_column(String,primary_key=True,default=uid); submission_id:Mapped[str]=mapped_column(String,index=True); status:Mapped[str]=mapped_column(String,default='TRIAGED'); created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
class Finding(Base):
 __tablename__='findings'; id:Mapped[str]=mapped_column(String,primary_key=True,default=uid); investigation_id:Mapped[str]=mapped_column(String,index=True); status:Mapped[str]=mapped_column(String,default='PUBLISHED'); label:Mapped[str]=mapped_column(String); created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
class FindingVersion(Base):
 __tablename__='finding_versions'; id:Mapped[str]=mapped_column(String,primary_key=True,default=uid); finding_id:Mapped[str]=mapped_column(String,index=True); version:Mapped[int]=mapped_column(Integer,default=1); label:Mapped[str]=mapped_column(String); status:Mapped[str]=mapped_column(String); actor:Mapped[str]=mapped_column(String); note:Mapped[str|None]=mapped_column(Text,nullable=True); created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
class Audit(Base):
 __tablename__='audit_logs'; id:Mapped[str]=mapped_column(String,primary_key=True,default=uid); action:Mapped[str]=mapped_column(String); entity:Mapped[str]=mapped_column(String); actor:Mapped[str]=mapped_column(String); created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
class Document(Base):
 __tablename__='documents'; id:Mapped[str]=mapped_column(String,primary_key=True,default=uid); source_id:Mapped[str]=mapped_column(String,index=True); url:Mapped[str]=mapped_column(String); content:Mapped[str]=mapped_column(Text); content_hash:Mapped[str]=mapped_column(String,unique=True,index=True); status:Mapped[str]=mapped_column(String,default='NORMALIZED'); collected_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
class Claim(Base):
 __tablename__='claims'; id:Mapped[str]=mapped_column(String,primary_key=True,default=uid); document_id:Mapped[str]=mapped_column(String,index=True); text:Mapped[str]=mapped_column(Text); status:Mapped[str]=mapped_column(String,default='EXTRACTED'); uncertainty:Mapped[str]=mapped_column(String,default='high'); created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
class Evidence(Base):
 __tablename__='evidence_items'; id:Mapped[str]=mapped_column(String,primary_key=True,default=uid); claim_id:Mapped[str|None]=mapped_column(String,index=True,nullable=True); source_url:Mapped[str]=mapped_column(String); excerpt:Mapped[str]=mapped_column(Text); relation:Mapped[str]=mapped_column(String,default='REQUIRES_REVIEW'); review_status:Mapped[str]=mapped_column(String,default='UNREVIEWED'); public:Mapped[bool]=mapped_column(Boolean,default=False); created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
class EvidenceRelation(Base):
 __tablename__='evidence_relations'; id:Mapped[str]=mapped_column(String,primary_key=True,default=uid); source_evidence_id:Mapped[str]=mapped_column(String,index=True); target_evidence_id:Mapped[str]=mapped_column(String,index=True); relation_type:Mapped[str]=mapped_column(String,default='CORROBORATES'); rationale:Mapped[str|None]=mapped_column(Text,nullable=True); created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
 __table_args__=(UniqueConstraint('source_evidence_id','target_evidence_id','relation_type',name='uq_evidence_relations_unique'),)
class InvestigationEvidence(Base):
 __tablename__='investigation_evidence'; id:Mapped[str]=mapped_column(String,primary_key=True,default=uid); investigation_id:Mapped[str]=mapped_column(String,index=True); evidence_id:Mapped[str]=mapped_column(String,index=True); rationale:Mapped[str]=mapped_column(Text); created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
class OutboxEvent(Base):
 __tablename__='outbox_events'; id:Mapped[str]=mapped_column(String,primary_key=True,default=uid); event_type:Mapped[str]=mapped_column(String,index=True); entity_id:Mapped[str]=mapped_column(String,index=True); payload:Mapped[str]=mapped_column(Text,default='{}'); status:Mapped[str]=mapped_column(String,default='PENDING',index=True); attempts:Mapped[int]=mapped_column(default=0); created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
class Embedding(Base):
 __tablename__='embeddings'; id:Mapped[str]=mapped_column(String,primary_key=True,default=uid); collection:Mapped[str]=mapped_column(String,index=True); entity_id:Mapped[str]=mapped_column(String,index=True); provider:Mapped[str]=mapped_column(String); dim:Mapped[int]=mapped_column(Integer); vector:Mapped[list]=mapped_column(JSON); updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now,onupdate=now)
 __table_args__=(UniqueConstraint('collection','entity_id',name='uq_embeddings_collection_entity'),)
def init_db(): Base.metadata.create_all(engine)
