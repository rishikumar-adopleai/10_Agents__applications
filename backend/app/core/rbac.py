"""Role-Based Access Control (RBAC) and Authorization Engine."""

from enum import Enum
from typing import Callable, List, Set

from pydantic import BaseModel

from backend.app.core.exceptions import PermissionDeniedError


class RoleEnum(str, Enum):
    ADMINISTRATOR = "ADMINISTRATOR"
    SALES_REPRESENTATIVE = "SALES_REPRESENTATIVE"
    SALES_MANAGER = "SALES_MANAGER"
    MARKETING_MANAGER = "MARKETING_MANAGER"
    PARTNER_MANAGER = "PARTNER_MANAGER"
    SECURITY_REVIEWER = "SECURITY_REVIEWER"
    DELIVERY_OWNER = "DELIVERY_OWNER"


class Permission(str, Enum):
    # User & Org Management
    USER_CREATE = "user:create"
    USER_READ = "user:read"
    USER_UPDATE = "user:update"
    USER_DELETE = "user:delete"
    ORG_SETTINGS = "org:settings"

    # Sales & Outreach
    ACCOUNT_READ = "account:read"
    ACCOUNT_WRITE = "account:write"
    OUTREACH_DRAFT = "outreach:draft"
    OUTREACH_APPROVE = "outreach:approve"
    CONVERSATION_MANAGE = "conversation:manage"
    CONVERSATION_TAKEOVER = "conversation:takeover"

    # Deals & Proposals (Commercial Authority)
    DEAL_READ = "deal:read"
    DEAL_WRITE = "deal:write"
    PROPOSAL_CREATE = "proposal:create"
    PROPOSAL_APPROVE = "proposal:approve"  # Requires Sales Manager

    # Trust & Security Attestation (Security Reviewer Authority)
    SECURITY_READ = "security:read"
    SECURITY_ATTEST = "security:attest"  # Only Security Reviewer

    # Proof & Delivery
    DELIVERY_VERIFY = "delivery:verify"  # Delivery Owner
    PROOF_PUBLISH = "proof:publish"

    # Partner Management
    PARTNER_MANAGE = "partner:manage"

    # System & Audit
    AUDIT_READ = "audit:read"
    INTEGRATION_MANAGE = "integration:manage"


# Role-to-Permissions Mapping
# Note Rule: Administrator does NOT automatically get commercial proposal approval or security attestation!
ROLE_PERMISSIONS: dict[RoleEnum, Set[Permission]] = {
    RoleEnum.ADMINISTRATOR: {
        Permission.USER_CREATE,
        Permission.USER_READ,
        Permission.USER_UPDATE,
        Permission.USER_DELETE,
        Permission.ORG_SETTINGS,
        Permission.ACCOUNT_READ,
        Permission.AUDIT_READ,
        Permission.INTEGRATION_MANAGE,
    },
    RoleEnum.SALES_REPRESENTATIVE: {
        Permission.ACCOUNT_READ,
        Permission.ACCOUNT_WRITE,
        Permission.OUTREACH_DRAFT,
        Permission.CONVERSATION_MANAGE,
        Permission.CONVERSATION_TAKEOVER,
        Permission.DEAL_READ,
        Permission.DEAL_WRITE,
        Permission.PROPOSAL_CREATE,
        Permission.SECURITY_READ,
    },
    RoleEnum.SALES_MANAGER: {
        Permission.ACCOUNT_READ,
        Permission.ACCOUNT_WRITE,
        Permission.OUTREACH_DRAFT,
        Permission.OUTREACH_APPROVE,
        Permission.CONVERSATION_MANAGE,
        Permission.CONVERSATION_TAKEOVER,
        Permission.DEAL_READ,
        Permission.DEAL_WRITE,
        Permission.PROPOSAL_CREATE,
        Permission.PROPOSAL_APPROVE,  # Commercial sign-off authority
        Permission.AUDIT_READ,
    },
    RoleEnum.MARKETING_MANAGER: {
        Permission.ACCOUNT_READ,
        Permission.OUTREACH_DRAFT,
        Permission.PROOF_PUBLISH,
        Permission.DEAL_READ,
    },
    RoleEnum.PARTNER_MANAGER: {
        Permission.ACCOUNT_READ,
        Permission.PARTNER_MANAGE,
        Permission.DEAL_READ,
    },
    RoleEnum.SECURITY_REVIEWER: {
        Permission.ACCOUNT_READ,
        Permission.SECURITY_READ,
        Permission.SECURITY_ATTEST,  # Security sign-off authority
    },
    RoleEnum.DELIVERY_OWNER: {
        Permission.ACCOUNT_READ,
        Permission.DELIVERY_VERIFY,  # Proof measurement validation
    },
}


class CurrentUser(BaseModel):
    id: str
    email: str
    organization_id: str
    roles: List[RoleEnum]
    is_active: bool = True

    def has_role(self, *required_roles: RoleEnum) -> bool:
        return any(role in self.roles for role in required_roles)

    def has_permission(self, permission: Permission) -> bool:
        for role in self.roles:
            if permission in ROLE_PERMISSIONS.get(role, set()):
                return True
        return False


def require_roles(*allowed_roles: RoleEnum) -> Callable:
    """Dependency for role-based endpoint authorization."""

    async def role_checker(current_user: CurrentUser) -> CurrentUser:
        if not current_user.has_role(*allowed_roles):
            raise PermissionDeniedError(
                message=f"Access requires one of roles: {[r.value for r in allowed_roles]}",
                details={"user_roles": [r.value for r in current_user.roles]},
            )
        return current_user

    return role_checker


def require_permission(required_permission: Permission) -> Callable:
    """Dependency for granular permission authorization."""

    async def permission_checker(current_user: CurrentUser) -> CurrentUser:
        if not current_user.has_permission(required_permission):
            raise PermissionDeniedError(
                message=f"Access requires permission: {required_permission.value}",
                details={"required_permission": required_permission.value},
            )
        return current_user

    return permission_checker
