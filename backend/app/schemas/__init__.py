"""Pydantic v2 schemas for the CMMS API.

Re-exports every public schema so callers can do::

    from app.schemas import WorkOrderCreate, UserResponse, ...
"""

from app.schemas.admin import AuditLogListResponse, AuditLogResponse
from app.schemas.area import AreaCreate, AreaResponse, AreaUpdate
from app.schemas.asset import AssetCreate, AssetResponse, AssetUpdate
from app.schemas.auth import (
    FCMTokenRequest,
    LoginRequest,
    LoginResponse,
    MFAConfirmRequest,
    MFASetupResponse,
    MFAVerifyRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
    RefreshRequest,
    TokenResponse,
    WSTokenResponse,
)
from app.schemas.budget import (
    AreaBudgetCreate,
    AreaBudgetResponse,
    AreaBudgetSummaryItem,
    BudgetSummaryResponse,
)
from app.schemas.common import MessageResponse, PaginationParams, SortParams
from app.schemas.dashboard import AreaDashboard, DashboardOverview, SiteDashboard
from app.schemas.incentive import (
    IncentiveMetric,
    IncentivePeriodType,
    IncentiveProgramCreate,
    IncentiveProgramResponse,
    IncentiveProgramUpdate,
    UserIncentiveScoreResponse,
)
from app.schemas.location import LocationCreate, LocationResponse, LocationUpdate
from app.schemas.org import OrgConfigUpdate, OrgResponse, OrgUpdate, SLAConfig
from app.schemas.part import (
    PartCreate,
    PartResponse,
    PartTransactionCreate,
    PartTransactionResponse,
    PartTransactionType,
    PartUpdate,
)
from app.schemas.pm import (
    PMScheduleResponse,
    PMScheduleSkip,
    PMScheduleStatus,
    PMTemplateCreate,
    PMTemplateResponse,
    PMTemplateUpdate,
    RecurrenceType,
)
from app.schemas.scan import (
    AssetScanResponse,
    LocationScanResponse,
    PartScanResponse,
    SiteScanResponse,
)
from app.schemas.shift import (
    ShiftScheduleCreate,
    ShiftScheduleResponse,
    ShiftScheduleUpdate,
    ShiftUserAssignment,
)
from app.schemas.site import SiteCreate, SiteResponse, SiteType, SiteUpdate
from app.schemas.user import (
    CertificationCreate,
    CertificationResponse,
    NotificationPrefUpdate,
    Permission,
    UserAreaUpdate,
    UserCreate,
    UserListResponse,
    UserPermissionUpdate,
    UserResponse,
    UserRole,
    UserUpdate,
)
from app.schemas.work_order import (
    AttachmentResponse,
    LaborLogCreate,
    LaborLogResponse,
    MessageCreate,
    MessageResponse as WOMessageResponse,
    TimelineEventCreate,
    TimelineEventResponse,
    TimelineEventType,
    WOPriority,
    WOStatus,
    WOType,
    WorkOrderAccept,
    WorkOrderAssign,
    WorkOrderCreate,
    WorkOrderEscalate,
    WorkOrderListResponse,
    WorkOrderPartCreate,
    WorkOrderPartResponse,
    WorkOrderReopen,
    WorkOrderResolve,
    WorkOrderResponse,
    WorkOrderUpdate,
)

__all__ = [
    # common
    "PaginationParams",
    "SortParams",
    "MessageResponse",
    # auth
    "LoginRequest",
    "LoginResponse",
    "RefreshRequest",
    "TokenResponse",
    "MFASetupResponse",
    "MFAVerifyRequest",
    "MFAConfirmRequest",
    "PasswordResetRequest",
    "PasswordResetConfirm",
    "WSTokenResponse",
    "FCMTokenRequest",
    # user
    "UserRole",
    "Permission",
    "UserCreate",
    "UserUpdate",
    "UserResponse",
    "UserListResponse",
    "UserAreaUpdate",
    "UserPermissionUpdate",
    "NotificationPrefUpdate",
    "CertificationCreate",
    "CertificationResponse",
    # org
    "OrgResponse",
    "OrgUpdate",
    "OrgConfigUpdate",
    "SLAConfig",
    # area
    "AreaCreate",
    "AreaUpdate",
    "AreaResponse",
    # location
    "LocationCreate",
    "LocationUpdate",
    "LocationResponse",
    # site
    "SiteType",
    "SiteCreate",
    "SiteUpdate",
    "SiteResponse",
    # asset
    "AssetCreate",
    "AssetUpdate",
    "AssetResponse",
    # work_order
    "WOType",
    "WOPriority",
    "WOStatus",
    "TimelineEventType",
    "WorkOrderCreate",
    "WorkOrderUpdate",
    "WorkOrderResponse",
    "WorkOrderListResponse",
    "WorkOrderAssign",
    "WorkOrderAccept",
    "WorkOrderResolve",
    "WorkOrderReopen",
    "WorkOrderEscalate",
    "TimelineEventCreate",
    "TimelineEventResponse",
    "AttachmentResponse",
    "WorkOrderPartCreate",
    "WorkOrderPartResponse",
    "LaborLogCreate",
    "LaborLogResponse",
    "MessageCreate",
    "WOMessageResponse",
    # part
    "PartTransactionType",
    "PartCreate",
    "PartUpdate",
    "PartResponse",
    "PartTransactionCreate",
    "PartTransactionResponse",
    # pm
    "RecurrenceType",
    "PMScheduleStatus",
    "PMTemplateCreate",
    "PMTemplateUpdate",
    "PMTemplateResponse",
    "PMScheduleResponse",
    "PMScheduleSkip",
    # budget
    "AreaBudgetCreate",
    "AreaBudgetResponse",
    "AreaBudgetSummaryItem",
    "BudgetSummaryResponse",
    # incentive
    "IncentiveMetric",
    "IncentivePeriodType",
    "IncentiveProgramCreate",
    "IncentiveProgramUpdate",
    "IncentiveProgramResponse",
    "UserIncentiveScoreResponse",
    # shift
    "ShiftScheduleCreate",
    "ShiftScheduleUpdate",
    "ShiftScheduleResponse",
    "ShiftUserAssignment",
    # admin
    "AuditLogResponse",
    "AuditLogListResponse",
    # dashboard
    "DashboardOverview",
    "AreaDashboard",
    "SiteDashboard",
    # scan
    "LocationScanResponse",
    "SiteScanResponse",
    "AssetScanResponse",
    "PartScanResponse",
]
