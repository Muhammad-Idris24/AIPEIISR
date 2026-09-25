"""initial schema - sources, documents, claims, evidence, submissions, investigations, reviews, findings, audit, outbox

Revision ID: 0001_initial
Revises: 
Create Date: 2026-09-22 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "sources",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("url", sa.String(), nullable=False),
        sa.Column("collector_type", sa.String(), nullable=False),
        sa.Column("interval_minutes", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="APPROVED"),
        sa.Column("last_success", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "citizen_submissions",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("url", sa.String(), nullable=True),
        sa.Column("media_reference", sa.String(), nullable=True),
        sa.Column("context", sa.Text(), nullable=True),
        sa.Column("consent", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="AI_ASSISTED_ANALYSIS"),
        sa.Column("analysis", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "investigations",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("submission_id", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="TRIAGED"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_investigations_submission_id"), "investigations", ["submission_id"], unique=False)
    op.create_table(
        "findings",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("investigation_id", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="PUBLISHED"),
        sa.Column("label", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_findings_investigation_id"), "findings", ["investigation_id"], unique=False)
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("entity", sa.String(), nullable=False),
        sa.Column("actor", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "documents",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("source_id", sa.String(), nullable=False),
        sa.Column("url", sa.String(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="NORMALIZED"),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("content_hash"),
    )
    op.create_index(op.f("ix_documents_content_hash"), "documents", ["content_hash"], unique=True)
    op.create_index(op.f("ix_documents_source_id"), "documents", ["source_id"], unique=False)
    op.create_table(
        "claims",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("document_id", sa.String(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="EXTRACTED"),
        sa.Column("uncertainty", sa.String(), nullable=False, server_default="high"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_claims_document_id"), "claims", ["document_id"], unique=False)
    op.create_table(
        "evidence_items",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("claim_id", sa.String(), nullable=True),
        sa.Column("source_url", sa.String(), nullable=False),
        sa.Column("excerpt", sa.Text(), nullable=False),
        sa.Column("relation", sa.String(), nullable=False, server_default="REQUIRES_REVIEW"),
        sa.Column("review_status", sa.String(), nullable=False, server_default="UNREVIEWED"),
        sa.Column("public", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_evidence_items_claim_id"), "evidence_items", ["claim_id"], unique=False)
    op.create_table(
        "investigation_evidence",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("investigation_id", sa.String(), nullable=False),
        sa.Column("evidence_id", sa.String(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_investigation_evidence_evidence_id"), "investigation_evidence", ["evidence_id"], unique=False)
    op.create_index(op.f("ix_investigation_evidence_investigation_id"), "investigation_evidence", ["investigation_id"], unique=False)
    op.create_table(
        "outbox_events",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("entity_id", sa.String(), nullable=False),
        sa.Column("payload", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("status", sa.String(), nullable=False, server_default="PENDING"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_outbox_events_event_type"), "outbox_events", ["event_type"], unique=False)
    op.create_index(op.f("ix_outbox_events_entity_id"), "outbox_events", ["entity_id"], unique=False)
    op.create_index(op.f("ix_outbox_events_status"), "outbox_events", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_outbox_events_status"), table_name="outbox_events")
    op.drop_index(op.f("ix_outbox_events_entity_id"), table_name="outbox_events")
    op.drop_index(op.f("ix_outbox_events_event_type"), table_name="outbox_events")
    op.drop_table("outbox_events")
    op.drop_index(op.f("ix_investigation_evidence_investigation_id"), table_name="investigation_evidence")
    op.drop_index(op.f("ix_investigation_evidence_evidence_id"), table_name="investigation_evidence")
    op.drop_table("investigation_evidence")
    op.drop_index(op.f("ix_evidence_items_claim_id"), table_name="evidence_items")
    op.drop_table("evidence_items")
    op.drop_index(op.f("ix_claims_document_id"), table_name="claims")
    op.drop_table("claims")
    op.drop_index(op.f("ix_documents_source_id"), table_name="documents")
    op.drop_index(op.f("ix_documents_content_hash"), table_name="documents")
    op.drop_table("documents")
    op.drop_table("audit_logs")
    op.drop_index(op.f("ix_findings_investigation_id"), table_name="findings")
    op.drop_table("findings")
    op.drop_index(op.f("ix_investigations_submission_id"), table_name="investigations")
    op.drop_table("investigations")
    op.drop_table("citizen_submissions")
    op.drop_table("sources")
