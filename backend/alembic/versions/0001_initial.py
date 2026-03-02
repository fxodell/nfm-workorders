"""Initial schema - all CMMS tables.

Revision ID: 0001
Revises: None
Create Date: 2026-03-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # organizations
    # ------------------------------------------------------------------
    op.create_table(
        "organizations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(255), nullable=False),
        sa.Column("logo_url", sa.Text(), nullable=True),
        sa.Column("currency_code", sa.String(3), nullable=False, server_default="USD"),
        sa.Column("config", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_organizations")),
        sa.UniqueConstraint("slug", name=op.f("uq_organizations_slug")),
    )

    # ------------------------------------------------------------------
    # wo_counters
    # ------------------------------------------------------------------
    op.create_table(
        "wo_counters",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("counter", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organizations.id"],
            name=op.f("fk_wo_counters_org_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_wo_counters")),
        sa.UniqueConstraint("org_id", "year", name="uq_wo_counter_org_year"),
    )
    op.create_index(op.f("ix_wo_counters_org_id"), "wo_counters", ["org_id"])

    # ------------------------------------------------------------------
    # areas
    # ------------------------------------------------------------------
    op.create_table(
        "areas",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "timezone", sa.String(50), nullable=False, server_default="America/Chicago"
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organizations.id"],
            name=op.f("fk_areas_org_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_areas")),
    )
    op.create_index(op.f("ix_areas_org_id"), "areas", ["org_id"])

    # ------------------------------------------------------------------
    # users
    # ------------------------------------------------------------------
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("phone", sa.String(30), nullable=True),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column(
            "role",
            sa.Enum(
                "SUPER_ADMIN",
                "ADMIN",
                "SUPERVISOR",
                "OPERATOR",
                "TECHNICIAN",
                "READ_ONLY",
                "COST_ANALYST",
                name="user_role",
                native_enum=False,
                length=20,
            ),
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("avatar_url", sa.Text(), nullable=True),
        sa.Column("totp_secret", sa.String(64), nullable=True),
        sa.Column("mfa_enabled", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("fcm_token", sa.Text(), nullable=True),
        sa.Column(
            "email_notifications_enabled",
            sa.Boolean(),
            nullable=False,
            server_default="true",
        ),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organizations.id"],
            name=op.f("fk_users_org_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
    )
    op.create_index(op.f("ix_users_org_id"), "users", ["org_id"])
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # ------------------------------------------------------------------
    # user_area_assignments
    # ------------------------------------------------------------------
    op.create_table(
        "user_area_assignments",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("area_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_user_area_assignments_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["area_id"],
            ["areas.id"],
            name=op.f("fk_user_area_assignments_area_id_areas"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "user_id", "area_id", name=op.f("pk_user_area_assignments")
        ),
    )

    # ------------------------------------------------------------------
    # user_permissions
    # ------------------------------------------------------------------
    op.create_table(
        "user_permissions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "permission",
            sa.Enum(
                "CAN_VIEW_COSTS",
                "CAN_MANAGE_BUDGET",
                "CAN_VIEW_INCENTIVES",
                "CAN_MANAGE_INVENTORY",
                "CAN_MANAGE_USERS",
                "CAN_VIEW_AUDIT_LOG",
                "CAN_MANAGE_PM_TEMPLATES",
                name="permission_type",
                native_enum=False,
                length=30,
            ),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_user_permissions_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_permissions")),
    )
    op.create_index(
        op.f("ix_user_permissions_user_id"), "user_permissions", ["user_id"]
    )

    # ------------------------------------------------------------------
    # technician_certifications
    # ------------------------------------------------------------------
    op.create_table(
        "technician_certifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("cert_name", sa.String(255), nullable=False),
        sa.Column("cert_number", sa.String(255), nullable=True),
        sa.Column("issued_by", sa.String(255), nullable=True),
        sa.Column("issued_date", sa.Date(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_technician_certifications_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_technician_certifications")),
    )
    op.create_index(
        op.f("ix_technician_certifications_user_id"),
        "technician_certifications",
        ["user_id"],
    )

    # ------------------------------------------------------------------
    # user_notification_prefs
    # ------------------------------------------------------------------
    op.create_table(
        "user_notification_prefs",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("area_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "push_enabled", sa.Boolean(), nullable=False, server_default="true"
        ),
        sa.Column(
            "email_enabled", sa.Boolean(), nullable=False, server_default="true"
        ),
        sa.Column("on_shift", sa.Boolean(), nullable=False, server_default="false"),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_user_notification_prefs_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["area_id"],
            ["areas.id"],
            name=op.f("fk_user_notification_prefs_area_id_areas"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "user_id", "area_id", name=op.f("pk_user_notification_prefs")
        ),
    )

    # ------------------------------------------------------------------
    # on_call_schedules
    # ------------------------------------------------------------------
    op.create_table(
        "on_call_schedules",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("area_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("start_dt", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_dt", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "priority",
            sa.Enum(
                "PRIMARY",
                "SECONDARY",
                name="on_call_priority",
                native_enum=False,
                length=15,
            ),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organizations.id"],
            name=op.f("fk_on_call_schedules_org_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["area_id"],
            ["areas.id"],
            name=op.f("fk_on_call_schedules_area_id_areas"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_on_call_schedules_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_on_call_schedules")),
    )
    op.create_index(
        op.f("ix_on_call_schedules_org_id"), "on_call_schedules", ["org_id"]
    )
    op.create_index(
        op.f("ix_on_call_schedules_area_id"), "on_call_schedules", ["area_id"]
    )
    op.create_index(
        op.f("ix_on_call_schedules_user_id"), "on_call_schedules", ["user_id"]
    )

    # ------------------------------------------------------------------
    # locations
    # ------------------------------------------------------------------
    op.create_table(
        "locations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("area_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("address", sa.String(500), nullable=True),
        sa.Column("gps_lat", sa.Numeric(precision=10, scale=7), nullable=True),
        sa.Column("gps_lng", sa.Numeric(precision=10, scale=7), nullable=True),
        sa.Column("qr_code_token", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organizations.id"],
            name=op.f("fk_locations_org_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["area_id"],
            ["areas.id"],
            name=op.f("fk_locations_area_id_areas"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_locations")),
        sa.UniqueConstraint(
            "qr_code_token", name=op.f("uq_locations_qr_code_token")
        ),
    )
    op.create_index(op.f("ix_locations_org_id"), "locations", ["org_id"])
    op.create_index(op.f("ix_locations_area_id"), "locations", ["area_id"])

    # ------------------------------------------------------------------
    # sites
    # ------------------------------------------------------------------
    op.create_table(
        "sites",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("location_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column(
            "type",
            sa.Enum(
                "WELL_SITE",
                "PLANT",
                "BUILDING",
                "APARTMENT",
                "LINE",
                "SUITE",
                "COMPRESSOR_STATION",
                "TANK_BATTERY",
                "SEPARATOR",
                "OTHER",
                name="site_type",
                native_enum=False,
                length=30,
            ),
            nullable=False,
        ),
        sa.Column("address", sa.String(500), nullable=True),
        sa.Column("gps_lat", sa.Numeric(precision=10, scale=7), nullable=True),
        sa.Column("gps_lng", sa.Numeric(precision=10, scale=7), nullable=True),
        sa.Column(
            "site_timezone",
            sa.String(50),
            nullable=False,
            server_default="America/Chicago",
        ),
        sa.Column("qr_code_token", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organizations.id"],
            name=op.f("fk_sites_org_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["location_id"],
            ["locations.id"],
            name=op.f("fk_sites_location_id_locations"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sites")),
        sa.UniqueConstraint("qr_code_token", name=op.f("uq_sites_qr_code_token")),
    )
    op.create_index(op.f("ix_sites_org_id"), "sites", ["org_id"])
    op.create_index(op.f("ix_sites_location_id"), "sites", ["location_id"])

    # ------------------------------------------------------------------
    # assets
    # ------------------------------------------------------------------
    op.create_table(
        "assets",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("site_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("asset_type", sa.String(100), nullable=True),
        sa.Column("manufacturer", sa.String(255), nullable=True),
        sa.Column("model", sa.String(255), nullable=True),
        sa.Column("serial_number", sa.String(255), nullable=True),
        sa.Column("install_date", sa.Date(), nullable=True),
        sa.Column("warranty_expiry", sa.Date(), nullable=True),
        sa.Column("qr_code_token", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organizations.id"],
            name=op.f("fk_assets_org_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["site_id"],
            ["sites.id"],
            name=op.f("fk_assets_site_id_sites"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_assets")),
        sa.UniqueConstraint("qr_code_token", name=op.f("uq_assets_qr_code_token")),
    )
    op.create_index(op.f("ix_assets_org_id"), "assets", ["org_id"])
    op.create_index(op.f("ix_assets_site_id"), "assets", ["site_id"])

    # ------------------------------------------------------------------
    # work_orders
    # ------------------------------------------------------------------
    op.create_table(
        "work_orders",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("area_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("location_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("site_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("human_readable_number", sa.String(30), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "type",
            sa.Enum(
                "REACTIVE",
                "PREVENTIVE",
                "INSPECTION",
                "CORRECTIVE",
                name="work_order_type",
                native_enum=False,
                length=20,
            ),
            nullable=False,
        ),
        sa.Column(
            "priority",
            sa.Enum(
                "IMMEDIATE",
                "URGENT",
                "SCHEDULED",
                "DEFERRED",
                name="work_order_priority",
                native_enum=False,
                length=10,
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "NEW",
                "ASSIGNED",
                "ACCEPTED",
                "IN_PROGRESS",
                "WAITING_ON_OPS",
                "WAITING_ON_PARTS",
                "RESOLVED",
                "VERIFIED",
                "CLOSED",
                "ESCALATED",
                name="work_order_status",
                native_enum=False,
                length=20,
            ),
            nullable=False,
        ),
        # People
        sa.Column("requested_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("assigned_to", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("accepted_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("verified_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("closed_by", postgresql.UUID(as_uuid=True), nullable=True),
        # Timestamps
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("in_progress_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("escalated_at", sa.DateTime(timezone=True), nullable=True),
        # SLA / scheduling
        sa.Column("ack_deadline", sa.DateTime(timezone=True), nullable=True),
        sa.Column("first_update_deadline", sa.DateTime(timezone=True), nullable=True),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("eta_minutes", sa.Integer(), nullable=True),
        # Resolution
        sa.Column("resolution_summary", sa.Text(), nullable=True),
        sa.Column("resolution_details", sa.Text(), nullable=True),
        # Safety
        sa.Column("safety_flag", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("safety_notes", sa.Text(), nullable=True),
        sa.Column("required_cert", sa.String(255), nullable=True),
        # GPS snapshots
        sa.Column(
            "gps_lat_accept", sa.Numeric(precision=10, scale=7), nullable=True
        ),
        sa.Column(
            "gps_lng_accept", sa.Numeric(precision=10, scale=7), nullable=True
        ),
        sa.Column(
            "gps_lat_start", sa.Numeric(precision=10, scale=7), nullable=True
        ),
        sa.Column(
            "gps_lng_start", sa.Numeric(precision=10, scale=7), nullable=True
        ),
        sa.Column(
            "gps_lat_resolve", sa.Numeric(precision=10, scale=7), nullable=True
        ),
        sa.Column(
            "gps_lng_resolve", sa.Numeric(precision=10, scale=7), nullable=True
        ),
        # Extensibility
        sa.Column("tags", sa.JSON(), nullable=True),
        sa.Column(
            "custom_fields",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("idempotency_key", sa.String(255), nullable=True),
        # Foreign keys
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organizations.id"],
            name=op.f("fk_work_orders_org_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["area_id"],
            ["areas.id"],
            name=op.f("fk_work_orders_area_id_areas"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["location_id"],
            ["locations.id"],
            name=op.f("fk_work_orders_location_id_locations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["site_id"],
            ["sites.id"],
            name=op.f("fk_work_orders_site_id_sites"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["asset_id"],
            ["assets.id"],
            name=op.f("fk_work_orders_asset_id_assets"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["requested_by"],
            ["users.id"],
            name=op.f("fk_work_orders_requested_by_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["assigned_to"],
            ["users.id"],
            name=op.f("fk_work_orders_assigned_to_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_work_orders")),
    )
    op.create_index("ix_work_orders_org_id", "work_orders", ["org_id"])
    op.create_index("ix_work_orders_area_id", "work_orders", ["area_id"])
    op.create_index("ix_work_orders_location_id", "work_orders", ["location_id"])
    op.create_index("ix_work_orders_site_id", "work_orders", ["site_id"])
    op.create_index("ix_work_orders_asset_id", "work_orders", ["asset_id"])
    op.create_index("ix_work_orders_assigned_to", "work_orders", ["assigned_to"])
    op.create_index("ix_work_orders_status", "work_orders", ["status"])
    op.create_index(
        "ix_work_orders_org_human_readable",
        "work_orders",
        ["org_id", "human_readable_number"],
        unique=True,
    )
    op.create_index(
        "ix_work_orders_idempotency_key",
        "work_orders",
        ["idempotency_key"],
        unique=True,
    )

    # ------------------------------------------------------------------
    # timeline_events
    # ------------------------------------------------------------------
    op.create_table(
        "timeline_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("work_order_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "event_type",
            sa.Enum(
                "STATUS_CHANGE",
                "MESSAGE",
                "ATTACHMENT",
                "PARTS_ADDED",
                "LABOR_LOGGED",
                "NOTE",
                "ASSIGNMENT_CHANGE",
                "SLA_BREACH",
                "ESCALATION",
                "GPS_SNAPSHOT",
                "SAFETY_FLAG_SET",
                name="timeline_event_type",
                native_enum=False,
                length=25,
            ),
            nullable=False,
        ),
        sa.Column(
            "payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["work_order_id"],
            ["work_orders.id"],
            name=op.f("fk_timeline_events_work_order_id_work_orders"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organizations.id"],
            name=op.f("fk_timeline_events_org_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_timeline_events_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_timeline_events")),
    )
    op.create_index(
        "ix_timeline_events_work_order_id", "timeline_events", ["work_order_id"]
    )
    op.create_index(
        "ix_timeline_events_org_id", "timeline_events", ["org_id"]
    )

    # ------------------------------------------------------------------
    # attachments
    # ------------------------------------------------------------------
    op.create_table(
        "attachments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("work_order_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("uploaded_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("s3_key", sa.Text(), nullable=False),
        sa.Column("s3_bucket", sa.String(255), nullable=False),
        sa.Column("filename", sa.String(500), nullable=False),
        sa.Column("mime_type", sa.String(255), nullable=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("caption", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["work_order_id"],
            ["work_orders.id"],
            name=op.f("fk_attachments_work_order_id_work_orders"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organizations.id"],
            name=op.f("fk_attachments_org_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["uploaded_by"],
            ["users.id"],
            name=op.f("fk_attachments_uploaded_by_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_attachments")),
    )
    op.create_index(
        "ix_attachments_work_order_id", "attachments", ["work_order_id"]
    )
    op.create_index("ix_attachments_org_id", "attachments", ["org_id"])

    # ------------------------------------------------------------------
    # labor_logs
    # ------------------------------------------------------------------
    op.create_table(
        "labor_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("work_order_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("minutes", sa.Integer(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "logged_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["work_order_id"],
            ["work_orders.id"],
            name=op.f("fk_labor_logs_work_order_id_work_orders"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organizations.id"],
            name=op.f("fk_labor_logs_org_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_labor_logs_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_labor_logs")),
    )
    op.create_index("ix_labor_logs_work_order_id", "labor_logs", ["work_order_id"])
    op.create_index("ix_labor_logs_org_id", "labor_logs", ["org_id"])
    op.create_index("ix_labor_logs_user_id", "labor_logs", ["user_id"])

    # ------------------------------------------------------------------
    # sla_events
    # ------------------------------------------------------------------
    op.create_table(
        "sla_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("work_order_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "event_type",
            sa.Enum(
                "ACK_BREACH",
                "FIRST_UPDATE_BREACH",
                "RESOLVE_BREACH",
                "MANUAL_ESCALATION",
                "ACKNOWLEDGED",
                name="sla_event_type",
                native_enum=False,
                length=25,
            ),
            nullable=False,
        ),
        sa.Column(
            "triggered_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("acknowledged_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["work_order_id"],
            ["work_orders.id"],
            name=op.f("fk_sla_events_work_order_id_work_orders"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organizations.id"],
            name=op.f("fk_sla_events_org_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["acknowledged_by"],
            ["users.id"],
            name=op.f("fk_sla_events_acknowledged_by_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sla_events")),
    )
    op.create_index(
        "ix_sla_events_work_order_id", "sla_events", ["work_order_id"]
    )
    op.create_index("ix_sla_events_org_id", "sla_events", ["org_id"])

    # ------------------------------------------------------------------
    # parts (must precede work_order_parts_used and part_transactions)
    # ------------------------------------------------------------------
    op.create_table(
        "parts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("part_number", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("unit_cost", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("barcode_value", sa.String(255), nullable=True),
        sa.Column("supplier_name", sa.String(255), nullable=True),
        sa.Column("supplier_part_number", sa.String(255), nullable=True),
        sa.Column("stock_quantity", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "reorder_threshold", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column("storage_location", sa.String(255), nullable=True),
        sa.Column("qr_code_token", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organizations.id"],
            name=op.f("fk_parts_org_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_parts")),
        sa.UniqueConstraint("qr_code_token", name=op.f("uq_parts_qr_code_token")),
        sa.UniqueConstraint(
            "org_id", "part_number", name="uq_parts_org_part_number"
        ),
    )
    op.create_index(op.f("ix_parts_org_id"), "parts", ["org_id"])

    # ------------------------------------------------------------------
    # work_order_parts_used (depends on work_orders and parts)
    # ------------------------------------------------------------------
    op.create_table(
        "work_order_parts_used",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("work_order_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("part_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("part_number", sa.String(100), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "unit_cost", sa.Numeric(precision=12, scale=2), nullable=True
        ),
        sa.ForeignKeyConstraint(
            ["work_order_id"],
            ["work_orders.id"],
            name=op.f("fk_work_order_parts_used_work_order_id_work_orders"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organizations.id"],
            name=op.f("fk_work_order_parts_used_org_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["part_id"],
            ["parts.id"],
            name=op.f("fk_work_order_parts_used_part_id_parts"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_work_order_parts_used")),
    )
    op.create_index(
        "ix_work_order_parts_used_work_order_id",
        "work_order_parts_used",
        ["work_order_id"],
    )
    op.create_index(
        "ix_work_order_parts_used_org_id",
        "work_order_parts_used",
        ["org_id"],
    )

    # ------------------------------------------------------------------
    # part_transactions
    # ------------------------------------------------------------------
    op.create_table(
        "part_transactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("part_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("work_order_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "transaction_type",
            sa.Enum(
                "IN",
                "OUT",
                "ADJUSTMENT",
                name="transaction_type",
                native_enum=False,
                length=15,
            ),
            nullable=False,
        ),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["part_id"],
            ["parts.id"],
            name=op.f("fk_part_transactions_part_id_parts"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organizations.id"],
            name=op.f("fk_part_transactions_org_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["work_order_id"],
            ["work_orders.id"],
            name=op.f("fk_part_transactions_work_order_id_work_orders"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name=op.f("fk_part_transactions_created_by_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_part_transactions")),
    )
    op.create_index(
        "ix_part_transactions_part_id", "part_transactions", ["part_id"]
    )
    op.create_index(
        "ix_part_transactions_org_id", "part_transactions", ["org_id"]
    )
    op.create_index(
        "ix_part_transactions_work_order_id",
        "part_transactions",
        ["work_order_id"],
    )

    # ------------------------------------------------------------------
    # pm_templates
    # ------------------------------------------------------------------
    op.create_table(
        "pm_templates",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("site_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "type", sa.String(20), nullable=False, server_default="PREVENTIVE"
        ),
        sa.Column(
            "priority",
            sa.Enum(
                "IMMEDIATE",
                "URGENT",
                "SCHEDULED",
                "DEFERRED",
                name="work_order_priority",
                native_enum=False,
                length=10,
                create_constraint=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "checklist_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "recurrence_type",
            sa.Enum(
                "DAILY",
                "WEEKLY",
                "BIWEEKLY",
                "MONTHLY",
                "QUARTERLY",
                "SEMI_ANNUAL",
                "ANNUAL",
                "CUSTOM_DAYS",
                name="recurrence_type",
                native_enum=False,
                length=15,
            ),
            nullable=False,
        ),
        sa.Column("recurrence_interval", sa.Integer(), nullable=True),
        sa.Column("required_cert", sa.String(255), nullable=True),
        sa.Column(
            "assigned_to_role",
            sa.Enum(
                "TECHNICIAN",
                "OPERATOR",
                "SUPERVISOR",
                name="pm_assigned_role",
                native_enum=False,
                length=15,
            ),
            nullable=True,
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organizations.id"],
            name=op.f("fk_pm_templates_org_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["asset_id"],
            ["assets.id"],
            name=op.f("fk_pm_templates_asset_id_assets"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["site_id"],
            ["sites.id"],
            name=op.f("fk_pm_templates_site_id_sites"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_pm_templates")),
    )
    op.create_index("ix_pm_templates_org_id", "pm_templates", ["org_id"])
    op.create_index("ix_pm_templates_asset_id", "pm_templates", ["asset_id"])
    op.create_index("ix_pm_templates_site_id", "pm_templates", ["site_id"])

    # ------------------------------------------------------------------
    # pm_schedules
    # ------------------------------------------------------------------
    op.create_table(
        "pm_schedules",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("pm_template_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column(
            "generated_work_order_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "PENDING",
                "GENERATED",
                "SKIPPED",
                name="pm_schedule_status",
                native_enum=False,
                length=12,
            ),
            nullable=False,
        ),
        sa.Column("skip_reason", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["pm_template_id"],
            ["pm_templates.id"],
            name=op.f("fk_pm_schedules_pm_template_id_pm_templates"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organizations.id"],
            name=op.f("fk_pm_schedules_org_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["generated_work_order_id"],
            ["work_orders.id"],
            name=op.f("fk_pm_schedules_generated_work_order_id_work_orders"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_pm_schedules")),
    )
    op.create_index(
        "ix_pm_schedules_pm_template_id", "pm_schedules", ["pm_template_id"]
    )
    op.create_index("ix_pm_schedules_org_id", "pm_schedules", ["org_id"])
    op.create_index("ix_pm_schedules_due_date", "pm_schedules", ["due_date"])

    # ------------------------------------------------------------------
    # area_budgets
    # ------------------------------------------------------------------
    op.create_table(
        "area_budgets",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("area_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("month", sa.Integer(), nullable=False),
        sa.Column(
            "budget_amount",
            sa.Numeric(precision=14, scale=2),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "actual_spend",
            sa.Numeric(precision=14, scale=2),
            nullable=False,
            server_default="0",
        ),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organizations.id"],
            name=op.f("fk_area_budgets_org_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["area_id"],
            ["areas.id"],
            name=op.f("fk_area_budgets_area_id_areas"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_area_budgets")),
        sa.UniqueConstraint(
            "org_id",
            "area_id",
            "year",
            "month",
            name="uq_area_budget_org_area_year_month",
        ),
    )
    op.create_index("ix_area_budgets_org_id", "area_budgets", ["org_id"])
    op.create_index("ix_area_budgets_area_id", "area_budgets", ["area_id"])

    # ------------------------------------------------------------------
    # incentive_programs
    # ------------------------------------------------------------------
    op.create_table(
        "incentive_programs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column(
            "metric",
            sa.Enum(
                "MTTR",
                "FIRST_TIME_FIX",
                "SLA_COMPLIANCE",
                "WO_COMPLETION_RATE",
                "SAFETY_SCORE",
                "CUSTOMER_SATISFACTION",
                name="incentive_metric",
                native_enum=False,
                length=25,
            ),
            nullable=False,
        ),
        sa.Column(
            "target_value", sa.Numeric(precision=12, scale=4), nullable=False
        ),
        sa.Column("bonus_description", sa.Text(), nullable=True),
        sa.Column(
            "period_type",
            sa.Enum(
                "WEEKLY",
                "MONTHLY",
                "QUARTERLY",
                "ANNUAL",
                name="incentive_period_type",
                native_enum=False,
                length=12,
            ),
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organizations.id"],
            name=op.f("fk_incentive_programs_org_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_incentive_programs")),
    )
    op.create_index(
        "ix_incentive_programs_org_id", "incentive_programs", ["org_id"]
    )

    # ------------------------------------------------------------------
    # user_incentive_scores
    # ------------------------------------------------------------------
    op.create_table(
        "user_incentive_scores",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("program_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("period_label", sa.String(50), nullable=False),
        sa.Column("score", sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column(
            "achieved", sa.Boolean(), nullable=False, server_default="false"
        ),
        sa.Column(
            "calculated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_user_incentive_scores_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["program_id"],
            ["incentive_programs.id"],
            name=op.f("fk_user_incentive_scores_program_id_incentive_programs"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_incentive_scores")),
    )
    op.create_index(
        "ix_user_incentive_scores_user_id",
        "user_incentive_scores",
        ["user_id"],
    )
    op.create_index(
        "ix_user_incentive_scores_program_id",
        "user_incentive_scores",
        ["program_id"],
    )

    # ------------------------------------------------------------------
    # shift_schedules
    # ------------------------------------------------------------------
    op.create_table(
        "shift_schedules",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("area_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column(
            "days_of_week", sa.JSON(), nullable=False
        ),
        sa.Column(
            "timezone",
            sa.String(50),
            nullable=False,
            server_default="America/Chicago",
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organizations.id"],
            name=op.f("fk_shift_schedules_org_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["area_id"],
            ["areas.id"],
            name=op.f("fk_shift_schedules_area_id_areas"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_shift_schedules")),
    )
    op.create_index(
        "ix_shift_schedules_org_id", "shift_schedules", ["org_id"]
    )
    op.create_index(
        "ix_shift_schedules_area_id", "shift_schedules", ["area_id"]
    )

    # ------------------------------------------------------------------
    # user_shift_assignments
    # ------------------------------------------------------------------
    op.create_table(
        "user_shift_assignments",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "shift_schedule_id", postgresql.UUID(as_uuid=True), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_user_shift_assignments_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["shift_schedule_id"],
            ["shift_schedules.id"],
            name=op.f("fk_user_shift_assignments_shift_schedule_id_shift_schedules"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "user_id",
            "shift_schedule_id",
            name=op.f("pk_user_shift_assignments"),
        ),
    )

    # ------------------------------------------------------------------
    # audit_logs
    # ------------------------------------------------------------------
    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("entity_type", sa.String(100), nullable=False),
        sa.Column("entity_id", sa.String(255), nullable=False),
        sa.Column(
            "old_value", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column(
            "new_value", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organizations.id"],
            name=op.f("fk_audit_logs_org_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name=op.f("fk_audit_logs_actor_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_logs")),
    )
    op.create_index("ix_audit_logs_org_id", "audit_logs", ["org_id"])
    op.create_index(
        "ix_audit_logs_actor_user_id", "audit_logs", ["actor_user_id"]
    )
    op.create_index(
        "ix_audit_logs_entity_type_entity_id",
        "audit_logs",
        ["entity_type", "entity_id"],
    )
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])


def downgrade() -> None:
    # Drop tables in reverse dependency order.
    op.drop_table("audit_logs")
    op.drop_table("user_shift_assignments")
    op.drop_table("shift_schedules")
    op.drop_table("user_incentive_scores")
    op.drop_table("incentive_programs")
    op.drop_table("area_budgets")
    op.drop_table("pm_schedules")
    op.drop_table("pm_templates")
    op.drop_table("part_transactions")
    op.drop_table("parts")
    op.drop_table("sla_events")
    op.drop_table("labor_logs")
    op.drop_table("work_order_parts_used")
    op.drop_table("attachments")
    op.drop_table("timeline_events")
    op.drop_table("work_orders")
    op.drop_table("assets")
    op.drop_table("sites")
    op.drop_table("locations")
    op.drop_table("on_call_schedules")
    op.drop_table("user_notification_prefs")
    op.drop_table("technician_certifications")
    op.drop_table("user_permissions")
    op.drop_table("user_area_assignments")
    op.drop_table("users")
    op.drop_table("areas")
    op.drop_table("wo_counters")
    op.drop_table("organizations")

    # Clean up enum types that may have been created (non-native enums
    # stored as VARCHAR don't create PG types, but we include this for
    # safety in case the configuration ever changes).
    for enum_name in [
        "user_role",
        "permission_type",
        "on_call_priority",
        "site_type",
        "work_order_type",
        "work_order_priority",
        "work_order_status",
        "timeline_event_type",
        "sla_event_type",
        "transaction_type",
        "recurrence_type",
        "pm_assigned_role",
        "pm_schedule_status",
        "incentive_metric",
        "incentive_period_type",
    ]:
        sa.Enum(name=enum_name).drop(op.get_bind(), checkfirst=True)
