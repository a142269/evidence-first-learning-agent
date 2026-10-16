"""baseline - B backend 12 tables

Revision ID: 20260618_0001
Revises: None
Create Date: 2026-06-18 22:00:00

This is the initial migration capturing the full B-owned schema.
All 12 B tables + their indexes and unique constraints are created here.

B-owned tables:
  profiles, realtime_states, learner_archetypes, knowledge_points,
  kp_relations, dina_states, bkt_states, sm2_schedule,
  learning_paths, assessments, mistakes, gamification_profiles
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260618_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # -- profiles --
    op.create_table(
        "profiles",
        sa.Column("user_id", sa.String(128), primary_key=True),
        sa.Column("profile_data", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.Float(), nullable=False),
        sa.Column("updated_at", sa.Float(), nullable=False),
    )

    # -- realtime_states --
    op.create_table(
        "realtime_states",
        sa.Column("session_id", sa.String(128), primary_key=True),
        sa.Column("user_id", sa.String(128), nullable=False, index=True),
        sa.Column("state_data", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("updated_at", sa.Float(), nullable=False),
    )
    op.create_index("ix_rt_state_user", "realtime_states", ["user_id"])

    # -- learner_archetypes --
    op.create_table(
        "learner_archetypes",
        sa.Column("user_id", sa.String(128), primary_key=True),
        sa.Column("archetype_code", sa.String(64), nullable=False, index=True),
        sa.Column("archetype_data", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("updated_at", sa.Float(), nullable=False),
    )
    op.create_index("ix_archetype_code", "learner_archetypes", ["archetype_code"])

    # -- knowledge_points --
    op.create_table(
        "knowledge_points",
        sa.Column("id", sa.String(128), primary_key=True),
        sa.Column("course", sa.String(128), nullable=False, index=True),
        sa.Column("name", sa.String(256), nullable=False, index=True),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("metadata", sa.JSON(), nullable=False, server_default="{}"),
        sa.UniqueConstraint("course", "name", name="uq_kp_course_name"),
    )
    op.create_index("ix_kp_course", "knowledge_points", ["course"])
    op.create_index("ix_kp_name", "knowledge_points", ["name"])
    # Composite index: fast lookup by course+name
    op.create_index("ix_kp_course_name", "knowledge_points", ["course", "name"])

    # -- kp_relations --
    op.create_table(
        "kp_relations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("source_id", sa.String(128), sa.ForeignKey("knowledge_points.id"), nullable=False, index=True),
        sa.Column("target_id", sa.String(128), sa.ForeignKey("knowledge_points.id"), nullable=False, index=True),
        sa.Column("relation_type", sa.String(32), nullable=False, index=True),
        sa.Column("weight", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("metadata", sa.JSON(), nullable=False, server_default="{}"),
        sa.UniqueConstraint("source_id", "target_id", "relation_type", name="uq_kp_relation"),
    )
    op.create_index("ix_kpr_source", "kp_relations", ["source_id", "relation_type"])
    op.create_index("ix_kpr_target", "kp_relations", ["target_id", "relation_type"])

    # -- dina_states --
    op.create_table(
        "dina_states",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.String(128), nullable=False, index=True),
        sa.Column("knowledge_point_id", sa.String(128), nullable=False, index=True),
        sa.Column("mastery", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("slip", sa.Float(), nullable=False, server_default="0.1"),
        sa.Column("guess", sa.Float(), nullable=False, server_default="0.2"),
        sa.Column("evidence", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("updated_at", sa.Float(), nullable=False),
        sa.UniqueConstraint("user_id", "knowledge_point_id", name="uq_dina_user_kp"),
    )
    op.create_index("ix_dina_user_kp", "dina_states", ["user_id", "knowledge_point_id"])

    # -- bkt_states --
    op.create_table(
        "bkt_states",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.String(128), nullable=False, index=True),
        sa.Column("knowledge_point_id", sa.String(128), nullable=False, index=True),
        sa.Column("p_learned", sa.Float(), nullable=False, server_default="0.2"),
        sa.Column("p_transit", sa.Float(), nullable=False, server_default="0.1"),
        sa.Column("p_slip", sa.Float(), nullable=False, server_default="0.1"),
        sa.Column("p_guess", sa.Float(), nullable=False, server_default="0.2"),
        sa.Column("history", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("updated_at", sa.Float(), nullable=False),
        sa.UniqueConstraint("user_id", "knowledge_point_id", name="uq_bkt_user_kp"),
    )
    op.create_index("ix_bkt_user_kp", "bkt_states", ["user_id", "knowledge_point_id"])

    # -- sm2_schedule --
    op.create_table(
        "sm2_schedule",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.String(128), nullable=False, index=True),
        sa.Column("item_id", sa.String(128), nullable=False, index=True),
        sa.Column("item_type", sa.String(32), nullable=False, server_default="knowledge_point"),
        sa.Column("repetitions", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("interval_days", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("easiness", sa.Float(), nullable=False, server_default="2.5"),
        sa.Column("due_at", sa.Float(), nullable=False),
        sa.Column("updated_at", sa.Float(), nullable=False),
        sa.UniqueConstraint("user_id", "item_id", name="uq_sm2_user_item"),
    )
    # Composite index: fast lookup of due items for a user
    op.create_index("ix_sm2_user_due", "sm2_schedule", ["user_id", "due_at"])

    # -- learning_paths --
    op.create_table(
        "learning_paths",
        sa.Column("id", sa.String(128), primary_key=True),
        sa.Column("user_id", sa.String(128), nullable=False, index=True),
        sa.Column("title", sa.String(256), nullable=False, server_default="learning path"),
        sa.Column("stages", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("current_stage", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("progress", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("metadata", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.Float(), nullable=False, index=True),
        sa.Column("updated_at", sa.Float(), nullable=False),
    )
    op.create_index("ix_path_user_created", "learning_paths", ["user_id", "created_at"])

    # -- assessments --
    op.create_table(
        "assessments",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("external_id", sa.String(128), unique=True, nullable=True),
        sa.Column("user_id", sa.String(128), nullable=False, index=True),
        sa.Column("record_type", sa.String(32), nullable=False, server_default="activity", index=True),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("topic", sa.String(256), nullable=False, server_default=""),
        sa.Column("duration", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("metadata", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("timestamp", sa.Float(), nullable=False, index=True),
    )
    op.create_index("ix_assessment_user_time", "assessments", ["user_id", "timestamp"])
    op.create_index("ix_assessment_user_type", "assessments", ["user_id", "record_type"])

    # -- mistakes --
    op.create_table(
        "mistakes",
        sa.Column("id", sa.String(128), primary_key=True),
        sa.Column("user_id", sa.String(128), nullable=False, index=True),
        sa.Column("knowledge_point_id", sa.String(128), nullable=True),
        sa.Column("question_data", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("error_type", sa.String(32), nullable=False, server_default="unknown", index=True),
        sa.Column("analysis", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.Float(), nullable=False),
        sa.Column("resolved_at", sa.Float(), nullable=True),
    )
    op.create_index("ix_mistake_user_unresolved", "mistakes", ["user_id", "resolved_at"])
    op.create_index("ix_mistake_user_type", "mistakes", ["user_id", "error_type"])
    op.create_index("ix_mistake_user_kp", "mistakes", ["user_id", "knowledge_point_id"])

    # -- gamification_profiles --
    op.create_table(
        "gamification_profiles",
        sa.Column("user_id", sa.String(128), primary_key=True),
        sa.Column("xp", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("level", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("streak_days", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("achievements", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("updated_at", sa.Float(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("gamification_profiles")
    op.drop_table("mistakes")
    op.drop_table("assessments")
    op.drop_table("learning_paths")
    op.drop_table("sm2_schedule")
    op.drop_table("bkt_states")
    op.drop_table("dina_states")
    op.drop_table("kp_relations")
    op.drop_table("knowledge_points")
    op.drop_table("learner_archetypes")
    op.drop_table("realtime_states")
    op.drop_table("profiles")
