"""initial_tables

Revision ID: 001
Revises:
Create Date: 2024-01-01

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "jobs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("status", sa.String(), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("job_type", sa.String(), nullable=False),
        sa.Column("filename", sa.String(), nullable=False),
        sa.Column("file_path", sa.String(), nullable=False),
        sa.Column("file_size", sa.BigInteger(), nullable=False),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("celery_task_id", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.Column("user_id", sa.String(), nullable=True),
    )
    op.create_index("idx_jobs_status", "jobs", ["status"])
    op.create_index("idx_jobs_job_type", "jobs", ["job_type"])
    op.create_index("idx_jobs_created_at", "jobs", ["created_at"])
    op.create_index("idx_jobs_celery_task_id", "jobs", ["celery_task_id"])

    op.create_table(
        "transcription_results",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("job_id", UUID(as_uuid=True), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("language", sa.String(), nullable=True),
        sa.Column("duration", sa.Integer(), nullable=True),
        sa.Column("segments", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_transcription_job_id", "transcription_results", ["job_id"])

    op.create_table(
        "segmentation_results",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("job_id", UUID(as_uuid=True), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("segments", sa.JSON(), nullable=True),
        sa.Column("total_segments", sa.Integer(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_segmentation_job_id", "segmentation_results", ["job_id"])


def downgrade():
    op.drop_table("segmentation_results")
    op.drop_table("transcription_results")
    op.drop_table("jobs")
