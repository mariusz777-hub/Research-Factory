"""add optional Google research input

Revision ID: 0002_google_research_input
Revises: 0001
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_google_research_input"
down_revision = "0001"
branch_labels = None
depends_on = None


def _has_column(name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return name in {column["name"] for column in inspector.get_columns("projects")}


def upgrade() -> None:
    # 0001 tworzy schemat przez bieżące Base.metadata, dlatego świeża instalacja
    # może już zawierać kolumnę. Istniejąca baza 1.0.0 jej nie ma.
    if not _has_column("google_research_input"):
        op.add_column(
            "projects",
            sa.Column("google_research_input", sa.Text(), nullable=False, server_default=""),
        )


def downgrade() -> None:
    if _has_column("google_research_input"):
        op.drop_column("projects", "google_research_input")
