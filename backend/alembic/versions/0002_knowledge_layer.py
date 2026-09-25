"""evidence relations and finding version tracking tables

Revision ID: 0002_knowledge_layer
Revises: 0001_initial
Create Date: 2026-09-22 00:01:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = "0002_knowledge_layer"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "finding_versions",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("finding_id", sa.String(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("label", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("actor", sa.String(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_finding_versions_finding_id"), "finding_versions", ["finding_id"], unique=False)
    op.create_table(
        "evidence_relations",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("source_evidence_id", sa.String(), nullable=False),
        sa.Column("target_evidence_id", sa.String(), nullable=False),
        sa.Column("relation_type", sa.String(), nullable=False, server_default="CORROBORATES"),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_evidence_id", "target_evidence_id", "relation_type", name="uq_evidence_relations_unique"),
    )
    op.create_index(op.f("ix_evidence_relations_source_evidence_id"), "evidence_relations", ["source_evidence_id"], unique=False)
    op.create_index(op.f("ix_evidence_relations_target_evidence_id"), "evidence_relations", ["target_evidence_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_evidence_relations_target_evidence_id"), table_name="evidence_relations")
    op.drop_index(op.f("ix_evidence_relations_source_evidence_id"), table_name="evidence_relations")
    op.drop_table("evidence_relations")
    op.drop_index(op.f("ix_finding_versions_finding_id"), table_name="finding_versions")
    op.drop_table("finding_versions")
